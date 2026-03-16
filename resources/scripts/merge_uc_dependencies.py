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
        # list-plugins format: "short-id  Display Name  1.2.3  (pinned)"
        # version is the last token that is not a parenthetical like "(pinned)"
        if len(parts) >= 2:
            non_paren = [p for p in parts if not p.startswith("(")]
            versions[parts[0]] = non_paren[-1]
    return versions


def get_group_id(uc: dict, plugin_id: str) -> str:
    """Return the Maven groupId for a plugin from the Update Center JSON.

    The UC JSON includes a 'groupId' field for every listed plugin, e.g.:
      workflow-aggregator -> org.jenkins-ci.plugins.workflow
      blueocean           -> io.jenkins.blueocean
      kubernetes          -> org.csanchez.jenkins.plugins
    Falling back to 'org.jenkins-ci.plugins' only when the plugin is absent
    from the UC (private/renamed) or the field is missing.
    """
    entry = uc.get("plugins", {}).get(plugin_id, {})
    return entry.get("groupId") or "org.jenkins-ci.plugins"


def plugin_purl(group_id: str, plugin_id: str, version: str) -> str:
    return f"pkg:maven/{group_id}/{plugin_id}@{version}"


def plugin_cpe(plugin_id: str, version: str) -> str:
    # NVD CPE format for Jenkins plugins (used for CVE matching alongside PURL):
    #   cpe:2.3:a:jenkins:{plugin_id}:{version}:*:*:*:*:jenkins:*:*
    # e.g. cpe:2.3:a:jenkins:git:5.2.1:*:*:*:*:jenkins:*:*
    # Note: NVD sometimes uses the plugin's artifactId, sometimes a different
    # identifier; the PURL match (which uses the exact Maven coordinates) is
    # the primary matching mechanism in Dependency-Track.
    return f"cpe:2.3:a:jenkins:{plugin_id}:{version}:*:*:*:*:jenkins:*:*"


def find_root_ref(bom: dict) -> Optional[str]:
    """Return the existing bom-ref from Syft's metadata.component, or None."""
    meta = bom.get("metadata", {}).get("component", {})
    return meta.get("bom-ref") or meta.get("purl") or None


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
        group_id = get_group_id(uc, args.plugin)
        correct_purl = plugin_purl(group_id, args.plugin, installed_ver)
        meta_component = bom.setdefault("metadata", {}).setdefault("component", {})
        meta_component.update({
            "type":    "library",
            "purl":    correct_purl,
            "name":    args.plugin,
            "version": installed_ver,
            "cpe":     plugin_cpe(args.plugin, installed_ver),
        })
        if meta_component.get("bom-ref", "").startswith("pkg:") or not meta_component.get("bom-ref"):
            meta_component["bom-ref"] = correct_purl
        print(
            f"[merge_uc] '{args.plugin}' not found in Update Center — PURL patched (groupId: {group_id}), no dep enrichment",
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
    # Capture the OLD bom-ref (typically a UUID from Syft) before patching,
    # so we can update the matching entry in the `dependencies` array below.
    old_root_ref = find_root_ref(bom)

    # ------------------------------------------------------------------
    # Patch the root component to have a proper pkg:maven PURL so that
    # Dependency-Track can match plugin-level CVEs.
    # The groupId comes from the Update Center JSON — it is the actual Maven
    # groupId published to the Jenkins update site, e.g.:
    #   git                  -> org.jenkins-ci.plugins
    #   workflow-aggregator  -> org.jenkins-ci.plugins.workflow
    #   blueocean            -> io.jenkins.blueocean
    #   kubernetes           -> org.csanchez.jenkins.plugins
    # Hardcoding org.jenkins-ci.plugins would cause a PURL mismatch in DT
    # for any plugin whose real groupId differs, resulting in zero CVE matches.
    # ------------------------------------------------------------------
    group_id = get_group_id(uc, args.plugin)
    correct_purl = plugin_purl(group_id, args.plugin, installed_ver)
    meta_component = bom.setdefault("metadata", {}).setdefault("component", {})
    meta_component["type"]    = "library"
    meta_component["purl"]    = correct_purl
    meta_component["name"]    = args.plugin
    meta_component["version"] = installed_ver
    meta_component["cpe"]     = plugin_cpe(args.plugin, installed_ver)
    # Keep bom-ref stable: if it was already a PURL-like string, update it too
    if meta_component.get("bom-ref", "").startswith("pkg:") or not meta_component.get("bom-ref"):
        meta_component["bom-ref"] = correct_purl
    root_ref = correct_purl

    # ------------------------------------------------------------------
    # Add inter-plugin dep components (if not already in the SBOM)
    # ------------------------------------------------------------------
    components: list[dict] = bom.setdefault("components", [])
    existing_purls: set[str] = {c.get("purl", "") for c in components}

    new_dep_purls: list[str] = []
    for dep_id, dep_ver in inter_deps:
        dep_group_id = get_group_id(uc, dep_id)
        purl = plugin_purl(dep_group_id, dep_id, dep_ver)
        new_dep_purls.append(purl)
        if purl not in existing_purls:
            components.append({
                "type":    "library",
                "bom-ref": purl,
                "name":    dep_id,
                "version": dep_ver,
                "purl":    purl,
                "cpe":     plugin_cpe(dep_id, dep_ver),
            })

    # ------------------------------------------------------------------
    # Add dependency edges from root → inter-plugin deps
    # ------------------------------------------------------------------
    dependencies: list[dict] = bom.setdefault("dependencies", [])
    # Find the Syft-generated root entry using the OLD bom-ref (a UUID or the
    # original file-path PURL).  If found, update its ref to the corrected
    # PURL so the dependency tree in Dependency-Track is fully connected.
    root_entry = next((d for d in dependencies if old_root_ref and d.get("ref") == old_root_ref), None)
    if root_entry is not None:
        root_entry["ref"] = root_ref
    else:
        # Also try the already-correct PURL in case the script is re-run.
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
