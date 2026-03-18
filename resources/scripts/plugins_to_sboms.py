#!/usr/bin/env python3
"""
Generate one CycloneDX JSON SBOM per Jenkins plugin from plugins-list.txt.

Fetches the Jenkins Update Centre to build a plugin-to-plugin dependency graph,
so Dependency-Track can render the full dependency tree for each plugin.

Usage:
    python3 plugins_to_sboms.py [plugins-list.txt] [output-dir]

Defaults:
    plugins-list.txt  -> plugins-list.txt
    output-dir        -> sboms/

Each line in plugins-list.txt must be:  <shortName> <version>

Output: sboms/<shortName>.json  — a CycloneDX 1.4 BOM with components and
        a dependencies section built from Update Centre metadata.
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


def make_bom(plugin_id, version, dep_purls):
    purl = f"pkg:jenkins/{plugin_id}@{version}"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "library",
                "name": plugin_id,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
            },
        },
        "components": [
            {
                "type": "library",
                "name": plugin_id,
                "version": version,
                "purl": purl,
                "bom-ref": purl,
            }
        ],
        "dependencies": [
            {
                "ref": purl,
                "dependsOn": dep_purls,
            }
        ],
    }


def main():
    plugins_file = sys.argv[1] if len(sys.argv) > 1 else "plugins-list.txt"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "sboms"
    os.makedirs(out_dir, exist_ok=True)

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
        print(f"WARNING: could not fetch update centre ({e}) — generating SBOMs without dependency graph")
        uc_plugins = {}

    count = 0
    for plugin_id, version in installed.items():
        dep_purls = []
        for dep in uc_plugins.get(plugin_id, {}).get("dependencies", []):
            dep_name = dep.get("name", "")
            optional = dep.get("optional", False)
            if dep_name in installed:
                # Resolve against the actually-installed version
                dep_purls.append(f"pkg:jenkins/{dep_name}@{installed[dep_name]}")
            elif not optional:
                # Non-optional dep not in our install list — include with UC version as fallback
                dep_purls.append(f"pkg:jenkins/{dep_name}@{dep.get('version', 'unknown')}")

        bom = make_bom(plugin_id, version, dep_purls)
        out_path = os.path.join(out_dir, f"{plugin_id}.json")
        with open(out_path, "w") as fout:
            json.dump(bom, fout, indent=2)
        count += 1

    print(f"Generated {count} SBOM(s) in {out_dir}/")


if __name__ == "__main__":
    main()
