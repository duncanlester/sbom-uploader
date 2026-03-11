#!/usr/bin/env python3
import json, re, sys
from datetime import datetime, timezone

def parse_plugins_txt(path: str):
    plugins = []
    for raw in open(path, "r", encoding="utf-8", errors="replace"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Accept "id:version" or "id version"
        if ":" in line and not line.startswith("http"):
            pid, ver = line.split(":", 1)
        else:
            parts = re.split(r"\s+", line, maxsplit=2)
            if len(parts) < 2:
                continue
            pid, ver = parts[0], parts[1]

        pid, ver = pid.strip(), ver.strip()
        if pid and ver:
            plugins.append((pid, ver))
    return plugins

def main():
    if len(sys.argv) < 3:
        print("Usage: plugins_txt_to_cyclonedx.py plugins.txt output.cdx.json [projectName] [projectVersion]", file=sys.stderr)
        sys.exit(2)

    plugins_txt = sys.argv[1]
    out = sys.argv[2]
    project_name = sys.argv[3] if len(sys.argv) >= 4 else "jenkins-plugins"
    project_version = sys.argv[4] if len(sys.argv) >= 5 else datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")

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
            for (pid, ver) in sorted(plugins)
        ],
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(bom, f, indent=2)
    print(f"Wrote {out} with {len(plugins)} plugins")

if __name__ == "__main__":
    main()
