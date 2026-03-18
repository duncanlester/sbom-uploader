#!/usr/bin/env python3
"""
Generate a single combined CycloneDX SBOM for all installed Jenkins plugins.

Fetches the Jenkins Update Centre to build a plugin-to-plugin dependency graph,
so Dependency-Track can render the full dependency tree.

Usage:
    python3 plugins_to_sboms.py [plugins-list.txt] [output-file] [jenkins-version]

Defaults:
    plugins-list.txt  -> plugins-list.txt
    output-file       -> sboms/jenkins-plugins.json
    jenkins-version   -> unknown

Each line in plugins-list.txt must be:  <shortName> <version>

Output: a single CycloneDX 1.6 BOM where:
  - metadata.component  = the Jenkins instance
  - components          = all installed plugins
  - dependencies        = full plugin-to-plugin graph from the Update Centre
"""
import json
import os
import sys
import uuid
import urllib.request
from datetime import datetime, timezone

UPDATE_CENTER_URL = "https://updates.jenkins.io/update-center.actual.json"


def fetch_update_center():
    print(f"Fetching update centre metadata from {UPDATE_CENTER_URL}...")
    with urllib.request.urlopen(UPDATE_CENTER_URL, timeout=30) as resp:
        data = json.load(resp)
    return data.get("plugins", {})


def main():
    plugins_file    = sys.argv[1] if len(sys.argv) > 1 else "plugins-list.txt"
    output_file     = sys.argv[2] if len(sys.argv) > 2 else "sboms/jenkins-plugins.json"
    jenkins_version = sys.argv[3] if len(sys.argv) > 3 else "unknown"

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    # Load installed plugins: {plugin_id: version}
    installed = {}
    with open(plugins_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                print(f"WARNING: skipping malformed line: {line!r}")
                continue
            installed[parts[0]] = parts[1]

    # Fetch update centre dependency metadata
    try:
        uc_plugins = fetch_update_center()
    except Exception as e:
        print(f"WARNING: could not fetch update centre ({e}) — generating SBOM without dependency graph")
        uc_plugins = {}

    root_ref = f"jenkins@{jenkins_version}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build components list
    components = []
    for plugin_id, version in installed.items():
        components.append({
            "type": "library",
            "name": plugin_id,
            "version": version,
            "purl": f"pkg:jenkins/{plugin_id}@{version}",
            "bom-ref": f"pkg:jenkins/{plugin_id}@{version}",
        })

    # Build dependencies list
    # Root node depends on every installed plugin
    dependencies = [{
        "ref": root_ref,
        "dependsOn": [f"pkg:jenkins/{pid}@{ver}" for pid, ver in installed.items()],
    }]

    # Each plugin depends on its plugin-level dependencies from the Update Centre
    for plugin_id, version in installed.items():
        dep_purls = []
        for dep in uc_plugins.get(plugin_id, {}).get("dependencies", []):
            dep_name = dep.get("name", "")
            optional = dep.get("optional", False)
            if dep_name in installed:
                dep_purls.append(f"pkg:jenkins/{dep_name}@{installed[dep_name]}")
            elif not optional:
                dep_purls.append(f"pkg:jenkins/{dep_name}@{dep.get('version', 'unknown')}")
        dependencies.append({
            "ref": f"pkg:jenkins/{plugin_id}@{version}",
            "dependsOn": dep_purls,
        })

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "name": "jenkins",
                "version": jenkins_version,
                "bom-ref": root_ref,
            },
        },
        "components": components,
        "dependencies": dependencies,
    }

    with open(output_file, "w") as f:
        json.dump(bom, f, indent=2)

    print(f"Generated combined SBOM with {len(components)} plugin(s) -> {output_file}")


if __name__ == "__main__":
    main()
