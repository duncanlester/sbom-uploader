#!/usr/bin/env python3
"""
Enrich a Syft-generated CycloneDX SBOM with inter-plugin dependency edges
sourced from the Jenkins Update Center JSON.

For each plugin that the target plugin declares as a dependency in the Update
Center metadata, this script:
  1. Adds the dependent plugin as a component in the SBOM (if not already
     present), using the *installed* version from plugins-list.txt.
  2. Adds a dependency edge from the root component to the dependent plugin
     in the CycloneDX `dependencies` section.

This gives Dependency-Track a full dependency graph for each plugin project:
  plugin-git
    ├── git-client (inter-plugin, from Update Center)
    │     └── ... (git-client's own SBOM covers its embedded JARs)
    ├── scm-api   (inter-plugin, from Update Center)
    └── jackson-databind-2.14.x (embedded JAR, from Syft)

Usage:
  python3 merge_uc_dependencies.py \\
    --sbom    <syft-output.cdx.json>  \\
    --uc      <update-center.json>    \\
    --plugins <plugins-list.txt>      \\
    --plugin  <plugin-id>             \\
    [--output <patched.cdx.json>]     # defaults to overwriting --sbom

Notes:
  - plugins-list.txt is the raw output of `jenkins-cli list-plugins`:
      git 5.2.1 (pinned)
      workflow-api 2.43
  - update-center.json must have the JSONP wrapper stripped (sed '1d;$d').
  - Only installed dependencies are added; uninstalled optional dependencies
    are silently skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

WS = re.compile(r"\s+")


def load_installed_versions(plugins_list_path: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw in Path(plugins_list_path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = WS.split(line)
        if len(parts) >= 2:
            versions[parts[0]] = parts[1]
    return versions


def plugin_purl(plugin_id: str, version: str) -> str:
    # org.jenkins-ci.plugins is the groupId for the vast majority of community
    # plugins.  Edge cases (e.g. workflow-*, blueocean) would need overrides,
    # but Syft already handles those correctly for the embedded-JAR components.
    return f"pkg:maven/org.jenkins-ci.plugins/{plugin_id}@{version}"


def plugin_cpe(plugin_id: str, version: str) -> str:
    # NVD CPE format for Jenkins plugins:
    #   cpe:2.3:a:jenkins:{plugin_id}:{version}:*:*:*:*:jenkins:*:*
    # This is what NVD uses for plugin-level CVEs, e.g.:
    #   cpe:2.3:a:jenkins:git:5.2.1:*:*:*:*:jenkins:*:*
    return f"cpe:2.3:a:jenkins:{plugin_id}:{version}:*:*:*:*:jenkins:*:*"


def find_root_ref(bom: dict, plugin_id: str, installed_version: str) -> str:
    """
    Return the bom-ref to use as the root node in the dependency graph.

    Syft sets metadata.component with a bom-ref (often a UUID or the PURL of
    the scanned file).  We prefer that so the edges attach to the same node
    Syft already created, falling back to constructing the expected PURL.
    """
    meta = bom.get("metadata", {}).get("component", {})
    ref: Optional[str] = meta.get("bom-ref") or meta.get("purl")
    if ref:
        return ref
    return plugin_purl(plugin_id, installed_version)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enrich a Syft CycloneDX SBOM with inter-plugin dependency edges from the Jenkins Update Center."
    )
    parser.add_argument("--sbom",    required=True, help="Syft CycloneDX JSON file to enrich")
    parser.add_argument("--uc",      required=True, help="update-center.json (JSONP wrapper stripped)")
    parser.add_argument("--plugins", required=True, help="jenkins-cli list-plugins output file")
    parser.add_argument("--plugin",  required=True, help="Plugin ID this SBOM represents")
    parser.add_argument("--output",  default=None,  help="Output path (default: overwrite --sbom)")
    args = parser.parse_args(argv[1:])

    out_path = args.output or args.sbom

    # ------------------------------------------------------------------
    # Load inputs
    # ------------------------------------------------------------------
    bom      = json.loads(Path(args.sbom).read_text("utf-8"))
    uc       = json.loads(Path(args.uc).read_text("utf-8"))
    installed = load_installed_versions(args.plugins)

    # ------------------------------------------------------------------
    # Resolve inter-plugin dependencies from the Update Center
    # ------------------------------------------------------------------
    uc_entry = uc.get("plugins", {}).get(args.plugin)
    if not uc_entry:
        # Plugin is private / very new / renamed — not in Update Center.
        # Still patch the root PURL so DT can match plugin-level CVEs.
        installed_ver = installed.get(args.plugin, "unknown")
        correct_purl = plugin_purl(args.plugin, installed_ver)
        meta_component = bom.setdefault("metadata", {}).setdefault("component", {})
        meta_component.update({
            "purl":    correct_purl,
            "name":    args.plugin,
            "version": installed_ver,
            "cpe":     plugin_cpe(args.plugin, installed_ver),
        })
        meta_component.setdefault("type", "library")
        if meta_component.get("bom-ref", "").startswith("pkg:") or not meta_component.get("bom-ref"):
            meta_component["bom-ref"] = correct_purl
        print(
            f"[merge_uc] '{args.plugin}' not found in Update Center — PURL patched, no dep enrichment",
            file=sys.stderr,
        )
        Path(out_path).write_text(json.dumps(bom, indent=2) + "\n", "utf-8")
        return 0

    inter_deps: list[tuple[str, str]] = []
    for dep in uc_entry.get("dependencies", []):
        dep_id: Optional[str] = dep.get("name") or dep.get("shortName")
        if not dep_id:
            continue
        dep_installed_ver = installed.get(dep_id)
        if not dep_installed_ver:
            # Not installed (optional dep or transitive not pinned) — skip.
            continue
        inter_deps.append((dep_id, dep_installed_ver))

    if not inter_deps:
        print(f"[merge_uc] '{args.plugin}': no installed inter-plugin deps — PURL patched only")

    # ------------------------------------------------------------------
    # Locate the root component bom-ref
    # ------------------------------------------------------------------
    installed_ver = installed.get(args.plugin, "unknown")
    root_ref = find_root_ref(bom, args.plugin, installed_ver)

    # ------------------------------------------------------------------
    # Patch the root component to have a proper pkg:maven PURL so that
    # Dependency-Track can match plugin-level CVEs (e.g. CVEs filed against
    # pkg:maven/org.jenkins-ci.plugins/git rather than embedded JARs).
    # Syft sets the root component to the scanned file path; we replace it.
    # ------------------------------------------------------------------
    correct_purl = plugin_purl(args.plugin, installed_ver)
    meta_component = bom.setdefault("metadata", {}).setdefault("component", {})
    meta_component["purl"]    = correct_purl
    meta_component["name"]    = args.plugin
    meta_component["version"] = installed_ver
    meta_component["cpe"]     = plugin_cpe(args.plugin, installed_ver)
    meta_component.setdefault("type", "library")
    # Keep bom-ref stable: if it was already a PURL-like string, update it too
    if meta_component.get("bom-ref", "").startswith("pkg:") or not meta_component.get("bom-ref"):
        meta_component["bom-ref"] = correct_purl
    # root_ref may now differ — re-resolve so dependency edges attach correctly
    root_ref = correct_purl

    # ------------------------------------------------------------------
    # Add inter-plugin dep components (if not already in the SBOM)
    # ------------------------------------------------------------------
    components: list[dict] = bom.setdefault("components", [])
    existing_purls: set[str] = {c.get("purl", "") for c in components}

    new_dep_purls: list[str] = []
    for dep_id, dep_ver in inter_deps:
        purl = plugin_purl(dep_id, dep_ver)
        new_dep_purls.append(purl)
        if purl not in existing_purls:
            components.append({
                "type":    "library",
                "bom-ref": purl,
                "name":    dep_id,
                "version": dep_ver,
                "purl":    purl,
            })

    # ------------------------------------------------------------------
    # Add dependency edges from root → inter-plugin deps
    # ------------------------------------------------------------------
    dependencies: list[dict] = bom.setdefault("dependencies", [])
    root_entry = next((d for d in dependencies if d.get("ref") == root_ref), None)
    if root_entry is None:
        root_entry = {"ref": root_ref, "dependsOn": []}
        dependencies.append(root_entry)

    existing_depends_on: set[str] = set(root_entry.setdefault("dependsOn", []))
    added = 0
    for purl in new_dep_purls:
        if purl not in existing_depends_on:
            root_entry["dependsOn"].append(purl)
            added += 1

    Path(out_path).write_text(json.dumps(bom, indent=2) + "\n", "utf-8")
    print(
        f"[merge_uc] Enriched '{args.plugin}' SBOM: "
        f"{added} inter-plugin dependency edge(s) added "
        f"({len(inter_deps)} total declared, {len(inter_deps) - added} already present)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
