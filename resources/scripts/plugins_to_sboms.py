#!/usr/bin/env python3
"""
Generate one CycloneDX JSON SBOM per Jenkins plugin from plugins-list.txt.

Usage:
    python3 plugins_to_sboms.py [plugins-list.txt] [output-dir]

Defaults:
    plugins-list.txt  -> plugins-list.txt
    output-dir        -> sboms/

Each line in plugins-list.txt must be:  <shortName> <version>

Output: sboms/<shortName>.json  — a minimal CycloneDX 1.4 BOM containing
        one component with a pkg:jenkins PURL, suitable for Dependency-Track.
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone


def make_bom(plugin_id: str, version: str) -> dict:
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
                "purl": f"pkg:jenkins/{plugin_id}@{version}",
                "bom-ref": f"pkg:jenkins/{plugin_id}@{version}",
            },
        },
        "components": [
            {
                "type": "library",
                "name": plugin_id,
                "version": version,
                "purl": f"pkg:jenkins/{plugin_id}@{version}",
                "bom-ref": f"pkg:jenkins/{plugin_id}@{version}",
            }
        ],
    }


def main():
    plugins_file = sys.argv[1] if len(sys.argv) > 1 else "plugins-list.txt"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "sboms"
    os.makedirs(out_dir, exist_ok=True)

    count = 0
    with open(plugins_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                print(f"WARNING: skipping malformed line: {line!r}")
                continue
            plugin_id, version = parts[0], parts[1]
            bom = make_bom(plugin_id, version)
            out_path = os.path.join(out_dir, f"{plugin_id}.json")
            with open(out_path, "w") as fout:
                json.dump(bom, fout, indent=2)
            count += 1

    print(f"Generated {count} SBOM(s) in {out_dir}/")


if __name__ == "__main__":
    main()
