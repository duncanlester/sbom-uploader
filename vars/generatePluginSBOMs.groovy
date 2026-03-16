#!/usr/bin/env groovy

/**
 * Generate CycloneDX SBOMs for all installed Jenkins plugins.
 *
 * Fetches the Jenkins Update Centre, runs generate_plugin_sbom.py in batch
 * mode, then prints a diagnostic PURL summary for the first fat plugin found.
 *
 * @param pluginsDir  Path to the Jenkins plugins directory (default: '/var/jenkins_home/plugins')
 * @param outputDir   Directory to write SBOM JSON files into (default: 'sboms')
 * @param pluginsFile Path to plugins-list.txt (default: 'plugins-list.txt')
 */
def call(Map config = [:]) {
    def pluginsDir  = config.pluginsDir  ?: '/var/jenkins_home/plugins'
    def outputDir   = config.outputDir   ?: 'sboms'
    def pluginsFile = config.pluginsFile ?: 'plugins-list.txt'

    sh """
        set -euo pipefail
        mkdir -p '${outputDir}'

        curl -fsSL https://updates.jenkins.io/current/update-center.json \
            | sed '1d;\$d' > update-center.json

        python3 resources/scripts/generate_plugin_sbom.py \
            --batch \
            --plugins-dir '${pluginsDir}' \
            --output-dir  '${outputDir}' \
            --uc          update-center.json \
            --plugins     '${pluginsFile}'

        for probe in git jackson2-api docker-commons kubernetes credentials; do
          f="${outputDir}/\${probe}.json"
          [ -f "\$f" ] || continue
          echo "=== PROBE: \${probe} ==="
          python3 - "\$f" <<'PYEOF'
import json, sys
bom = json.load(open(sys.argv[1]))
root = bom['metadata']['component']
print('  root purl : ' + str(root.get('purl')))
comps = bom.get('components', [])
print('  components: ' + str(len(comps)))
for c in comps[:20]:
    print('    ' + str(c.get('purl')))
if len(comps) > 20:
    print('    ... (' + str(len(comps) - 20) + ' more)')
PYEOF
          break
        done
    """
}
