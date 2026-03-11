#!/usr/bin/env groovy

/**
 * Export Dependency Track vulnerability reports for all active projects
 *
 * @param dtUrl Dependency Track API URL (default: 'http://w-work-19.rdmz.isridev.com:8081')
 */
def call(String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {
        // Get all active projects
        sh """
            curl -s -X GET '${dtUrl}/api/v1/project' \
                -H "X-Api-Key: \$DT_API_KEY" \
                -o all-projects.json
        """

        def projectList = sh(
            script: """
                python3 << 'PYTHON_EOF'
import json

with open('all-projects.json') as f:
    projects = json.load(f)

active_projects = [p for p in projects if p.get('active', True)]
print(f"Found {len(active_projects)} active projects")

for p in active_projects:
    print(f"{p['name']}|{p['version']}|{p['uuid']}")
PYTHON_EOF
            """,
            returnStdout: true
        ).trim()

        def lines = projectList.split('\n')
        def projectCount = lines[0]
        echo projectCount

        // Create reports directory
        sh "mkdir -p reports"

        // Generate report for each project
        for (int i = 1; i < lines.size(); i++) {
            def parts = lines[i].split('\\|')
            if (parts.size() == 3) {
                def projectName = parts[0]
                def projectVersion = parts[1]
                def projectUuid = parts[2]

                echo "Generating report for: ${projectName} ${projectVersion}"

                try {
                    // Generate report for this project
                    exportDTReport(projectName, projectVersion, dtUrl)

                    // Move to reports directory with sanitized filename
                    def safeFilename = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
                    sh """
                        mv vulnerability-report.pdf reports/${safeFilename}.pdf
                        mv findings.json reports/${safeFilename}-findings.json
                        mv metrics.json reports/${safeFilename}-metrics.json
                    """
                } catch (Exception e) {
                    echo "WARNING: Failed to generate report for ${projectName} ${projectVersion}: ${e.message}"
                }
            }
        }

        // Archive all reports
        archiveArtifacts artifacts: 'reports/*.pdf,reports/*.json', allowEmptyArchive: false

        echo ""
        echo "All project reports generated and archived"
        echo "Download from: Build page -> Artifacts section"
    }
}
