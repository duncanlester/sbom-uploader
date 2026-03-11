#!/usr/bin/env python3
"""
Convert Jenkins CLI `list-plugins` output into a CycloneDX SBOM (JSON) suitable for Dependency-Track.

Input format (from `java -jar jenkins-cli.jar ... list-plugins`):
  plugin-id version (optional flags...)
Examples:
  git 5.2.1
  workflow-api 2.43 (pinned)
  matrix-auth 3.1.5 (disabled)

Usage:
  python3 plugins_txt_to_cyclonedx.py plugins.txt jenkins-plugins.cdx.json [projectName] [projectVersion]

Notes:
  - This script intentionally keeps parsing strict and simple:
    first token = plugin id, second token = version.
  - Produces generic PURLs (pkg:generic/jenkins-plugin/<id>@<version>), which Dependency-Track can ingest.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

WS = re.compile(r"\s+")


def parse_plugins_txt(path: str) -> List[Tuple[str, str]]:
    plugins: List[Tuple[str, str]] = []
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = WS.split(line)
        if len(parts) < 2:
            continue
        plugin_id, version = parts[0].strip(), parts[1].strip()
        if not plugin_id or not version:
            continue
        plugins.append((plugin_id, version))
    # de-dup by plugin id (last one wins), then sort
    dedup = {}
    for pid, ver in plugins:
        dedup[pid] = ver
    return sorted(dedup.items(), key=lambda x: x[0])


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print(
            "Usage: plugins_txt_to_cyclonedx.py plugins.txt output.cdx.json [projectName] [projectVersion]",
            file=sys.stderr,
        )
        return 2

    plugins_txt = argv[1]
    out_path = argv[2]
    project_name = argv[3] if len(argv) >= 4 else "jenkins-plugins"
    project_version = argv[4] if len(argv) >= 5 else utc_stamp()

    plugins = parse_plugins_txt(plugins_txt)

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": "application",
                "name": project_name,
                "version": project_version,
                "purl": f"pkg:generic/{project_name}@{project_version}",
            },
        },
        "components": [
            {
                "type": "library",
                "name": pid,
                "version": ver,
                "purl": f"pkg:generic/jenkins-plugin/{pid}@{ver}",
            }
            for pid, ver in plugins
        ],
    }

    Path(out_path).write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote: {out_path}")
    print(f"Plugins: {len(plugins)}")
    print(f"Project: {project_name}@{project_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
