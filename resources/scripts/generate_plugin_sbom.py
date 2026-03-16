#!/usr/bin/env python3
"""
Generate a complete CycloneDX 1.4 SBOM for a Jenkins plugin (.jpi / .hpi).

What this script does in one pass:
  1. Opens the .jpi (a ZIP/WAR archive) and reads every JAR in WEB-INF/lib/.
  2. For each embedded JAR, reads META-INF/maven/<g>/<a>/pom.properties to
     get the exact Maven coordinates (groupId, artifactId, version).
     Falls back to filename parsing when pom.properties is absent.
  3. Looks up the plugin's own Maven groupId in the Jenkins Update Center JSON
     so the root-component PURL is correct (e.g. org.jenkins-ci.plugins.workflow
     for workflow-aggregator, not the wrong org.jenkins-ci.plugins default).
  4. Adds inter-plugin dependencies listed in the Update Center so
     Dependency-Track shows the full dependency graph.
  5. Writes a CycloneDX 1.4 JSON SBOM to --output.

Usage:
  python3 generate_plugin_sbom.py \\
      --jpi       /var/jenkins_home/plugins/git.jpi \\
      --plugin-id git \\
      --version   5.2.1 \\
      --uc        update-center.json \\
      --plugins   plugins-list.txt \\
      --output    sboms/git.json
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WS = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_installed_versions(plugins_list_path: str) -> dict[str, str]:
    """Parse jenkins-cli list-plugins output into {plugin-id: version}."""
    versions: dict[str, str] = {}
    for raw in Path(plugins_list_path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = WS.split(line)
        if len(parts) >= 2:
            non_paren = [p for p in parts if not p.startswith("(")]
            versions[parts[0]] = non_paren[-1]
    return versions


def get_group_id(uc: dict, plugin_id: str) -> str:
    """Return the Maven groupId from Update Center, falling back to the
    catch-all org.jenkins-ci.plugins only when the plugin is absent."""
    entry = uc.get("plugins", {}).get(plugin_id, {})
    return entry.get("groupId") or "org.jenkins-ci.plugins"


def parse_pom_properties(data: bytes) -> dict[str, str]:
    """Parse a pom.properties byte string into a key→value dict."""
    result: dict[str, str] = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def coords_from_jar(jar_bytes: bytes) -> Optional[dict]:
    """Extract {groupId, artifactId, version} from a JAR's pom.properties."""
    try:
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as jar:
            candidates = [
                n for n in jar.namelist()
                if re.match(r"META-INF/maven/[^/]+/[^/]+/pom\.properties$", n)
            ]
            if not candidates:
                return None
            props = parse_pom_properties(jar.read(candidates[0]))
            g, a, v = props.get("groupId"), props.get("artifactId"), props.get("version")
            if g and a and v:
                return {"groupId": g, "artifactId": a, "version": v}
    except Exception:
        pass
    return None


def coords_from_filename(jar_name: str) -> Optional[dict]:
    """Last-resort: parse 'commons-lang3-3.12.0.jar' → artifactId + version."""
    stem = re.sub(r"\.jar$", "", jar_name, flags=re.IGNORECASE)
    m = re.match(r"^(.+?)-(\d+[\d.].*)$", stem)
    if m:
        return {"groupId": "unknown", "artifactId": m.group(1), "version": m.group(2)}
    return None


def make_component(group_id: str, artifact_id: str, version: str) -> dict:
    purl = f"pkg:maven/{group_id}/{artifact_id}@{version}"
    return {
        "type":    "library",
        "bom-ref": purl,
        "group":   group_id,
        "name":    artifact_id,
        "version": version,
        "purl":    purl,
    }


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_sbom(
    jpi_path: str,
    plugin_id: str,
    plugin_version: str,
    uc: dict,
    installed: dict[str, str],
) -> dict:
    group_id  = get_group_id(uc, plugin_id)
    root_purl = f"pkg:maven/{group_id}/{plugin_id}@{plugin_version}"
    root_cpe  = f"cpe:2.3:a:jenkins:{plugin_id}:{plugin_version}:*:*:*:*:jenkins:*:*"

    components: list[dict] = []
    seen_purls: set[str]   = set()

    # ------------------------------------------------------------------
    # 1. Embedded library JARs from WEB-INF/lib/
    # ------------------------------------------------------------------
    jar_errors = 0
    try:
        with zipfile.ZipFile(jpi_path) as jpi:
            jar_entries = [
                n for n in jpi.namelist()
                if re.match(r"WEB-INF/lib/[^/]+\.jar$", n, re.IGNORECASE)
            ]
            for jar_entry in jar_entries:
                jar_name = jar_entry.rsplit("/", 1)[-1]
                try:
                    jar_bytes = jpi.read(jar_entry)
                except Exception as e:
                    print(f"  [warn] cannot read {jar_entry}: {e}", file=sys.stderr)
                    jar_errors += 1
                    continue

                coords = coords_from_jar(jar_bytes) or coords_from_filename(jar_name)
                if not coords:
                    print(f"  [warn] no coords for {jar_name}", file=sys.stderr)
                    continue

                comp = make_component(coords["groupId"], coords["artifactId"], coords["version"])
                if comp["purl"] not in seen_purls:
                    seen_purls.add(comp["purl"])
                    components.append(comp)
    except zipfile.BadZipFile as e:
        print(f"[error] {jpi_path} is not a valid ZIP: {e}", file=sys.stderr)
        return {}

    # ------------------------------------------------------------------
    # 2. Inter-plugin dependencies from Update Center
    # ------------------------------------------------------------------
    uc_entry = uc.get("plugins", {}).get(plugin_id, {})
    for dep in uc_entry.get("dependencies", []):
        dep_id: Optional[str] = dep.get("name") or dep.get("shortName")
        if not dep_id:
            continue
        dep_version = installed.get(dep_id)
        if not dep_version:
            continue  # not installed (optional / transitive)
        dep_group_id = get_group_id(uc, dep_id)
        comp = make_component(dep_group_id, dep_id, dep_version)
        if comp["purl"] not in seen_purls:
            seen_purls.add(comp["purl"])
            comp["properties"] = [{"name": "jenkins:dependency-type", "value": "plugin"}]
            components.append(comp)

    # ------------------------------------------------------------------
    # 3. Assemble the CycloneDX document
    # ------------------------------------------------------------------
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    serial = str(uuid.uuid4())

    bom = {
        "bomFormat":    "CycloneDX",
        "specVersion":  "1.4",
        "serialNumber": f"urn:uuid:{serial}",
        "version":      1,
        "metadata": {
            "timestamp": now,
            "tools": [{"vendor": "sbom-uploader", "name": "generate_plugin_sbom", "version": "2.0.0"}],
            "component": {
                "type":    "library",
                "bom-ref": root_purl,
                "group":   group_id,
                "name":    plugin_id,
                "version": plugin_version,
                "purl":    root_purl,
                "cpe":     root_cpe,
            },
        },
        "components": components,
        "dependencies": [
            {"ref": root_purl, "dependsOn": [c["bom-ref"] for c in components]},
            *[{"ref": c["bom-ref"], "dependsOn": []} for c in components],
        ],
    }

    n_embedded = sum(1 for c in components if "jenkins:dependency-type" not in str(c.get("properties", "")))
    n_plugin   = len(components) - n_embedded
    print(
        f"[sbom] {plugin_id}@{plugin_version} (groupId={group_id}): "
        f"{n_embedded} embedded JARs, {n_plugin} plugin-deps  →  {len(components)} total components"
    )
    if jar_errors:
        print(f"  [warn] {jar_errors} JAR(s) could not be read", file=sys.stderr)

    return bom


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a CycloneDX 1.4 SBOM from a Jenkins .jpi/.hpi plugin file"
    )
    parser.add_argument("--jpi",       required=True, help="Path to the .jpi or .hpi file")
    parser.add_argument("--plugin-id", required=True, help="Plugin short name (e.g. 'git')")
    parser.add_argument("--version",   required=True, help="Installed version (e.g. '5.2.1')")
    parser.add_argument("--uc",        required=True, help="update-center.json (JSONP wrapper stripped)")
    parser.add_argument("--plugins",   required=True, help="jenkins-cli list-plugins output file")
    parser.add_argument("--output",    required=True, help="Output SBOM JSON file path")
    args = parser.parse_args(argv[1:])

    jpi_path = args.jpi
    if not Path(jpi_path).exists():
        print(f"[error] JPI file not found: {jpi_path}", file=sys.stderr)
        return 1

    uc        = json.loads(Path(args.uc).read_text("utf-8"))
    installed = load_installed_versions(args.plugins)

    bom = generate_sbom(
        jpi_path=jpi_path,
        plugin_id=args.plugin_id,
        plugin_version=args.version,
        uc=uc,
        installed=installed,
    )
    if not bom:
        return 1

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(bom, indent=2) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
