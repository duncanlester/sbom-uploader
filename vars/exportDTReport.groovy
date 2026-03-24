#!/usr/bin/env groovy

/**
 * Export Dependency Track vulnerability report as shareable PDF
 *
 * @param projectName The project name in Dependency Track
 * @param projectVersion The project version in Dependency Track
 * @param dtUrl Dependency Track API URL (default: 'http://w-work-19.rdmz.isridev.com:8081')
 */
def call(String projectName, String projectVersion, String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {
        // Look up the specific project by name + version
        def lookupJson = sh(script: """
            curl -s '${dtUrl}/api/v1/project/lookup?name=${URLEncoder.encode(projectName, 'UTF-8')}&version=${URLEncoder.encode(projectVersion, 'UTF-8')}' \
                -H "X-Api-Key: \$DT_API_KEY"
        """, returnStdout: true).trim()

        // Load Python script for PDF generation from library resources
        writeFile file: 'generate_vuln_report.py', text: libraryResource('scripts/generate_vuln_report.py')

        if (!lookupJson || !lookupJson.startsWith('{')) {
            error "Project '${projectName}' version '${projectVersion}' not found in Dependency Track."
        }
        def matchingProject = readJSON text: lookupJson

        def projectUuid = matchingProject.uuid
        echo "Project UUID: ${projectUuid}"

        // Get vulnerability metrics
        sh """
            curl -s -X GET '${dtUrl}/api/v1/metrics/project/${projectUuid}/current' \
                -H "X-Api-Key: \$DT_API_KEY" \
                -o metrics.json
        """

        // Validate metrics.json
        def metrics = readJSON file: 'metrics.json'
        if (!metrics || metrics.toString() == '{}') {
            error "Failed to fetch metrics from Dependency Track. The project may not be fully processed yet."
        }

        // Get findings
        sh """
            curl -s -X GET '${dtUrl}/api/v1/finding/project/${projectUuid}?suppressed=true' \
                -H "X-Api-Key: \$DT_API_KEY" \
                -o findings.json
        """

        // Validate findings.json
        def findings = readJSON file: 'findings.json'
        if (findings == null) {
            error "Failed to fetch findings from Dependency Track."
        }

        // Stamp each finding with projectUuid so the Python script can call /api/v1/analysis
        findings.each { f -> f.projectUuid = projectUuid }
        writeJSON file: 'findings.json', json: findings

        // Generate PDF using external Python script
        sh """
            docker run --rm --network=host \
                -v ${env.WORKSPACE}:/workspace \
                -w /workspace \
                -e DT_API_URL='${dtUrl}' \
                -e DT_API_KEY="\$DT_API_KEY" \
                python:3.11-slim \
                bash -c 'pip install -q fpdf2 && python3 generate_vuln_report.py "${projectName}" "${projectVersion}"'
        """

        // Archive artifacts
        archiveArtifacts artifacts: 'vulnerability-report.pdf,findings.json,metrics.json', allowEmptyArchive: false

        echo "Reports generated and archived as Jenkins build artifacts"
        echo ""
        echo "vulnerability-report.pdf - Executive summary (shareable)"
        echo "findings.json - Detailed findings export"
        echo "metrics.json - Project metrics"
        echo ""
        echo "Download from: Build page -> Artifacts section"
    }
}
