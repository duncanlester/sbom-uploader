#!/usr/bin/env groovy

/**
 * Export Dependency Track vulnerability reports for all active projects.
 * Projects that are children of a collection project are merged into a
 * single grouped report per collection parent.
 *
 * @param dtUrl Dependency Track API URL (default: 'http://w-work-19.rdmz.isridev.com:8081')
 */
def call(String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {

        sh """
            curl -s -X GET '${dtUrl}/api/v1/project?pageSize=1000' \
                -H "X-Api-Key: \$DT_API_KEY" \
                -o all-projects.json
        """

        def allProjects = readJSON file: 'all-projects.json'
        sh 'mkdir -p reports'
        writeFile file: 'generate_vuln_report.py', text: libraryResource('scripts/generate_vuln_report.py')

        // Identify collection projects and which projects are their children
        def collectionProjects = allProjects.findAll { it.collectionLogic && it.active }
        def collectionUUIDs    = collectionProjects.collect { it.uuid } as Set
        def childUUIDs         = allProjects.findAll { it.parent && collectionUUIDs.contains(it.parent?.uuid) }.collect { it.uuid } as Set

        // Standalone: active, not a collection, not a child of a collection
        def standaloneProjects = allProjects.findAll { p ->
            p.active && !p.collectionLogic && !childUUIDs.contains(p.uuid)
        }

        // --- Individual reports for standalone projects ---
        standaloneProjects.each { project ->
            def projectName    = project.name
            def projectVersion = project.version ?: 'unknown'
            echo "Generating report for: ${projectName} ${projectVersion}"
            try {
                exportDTReport(projectName, projectVersion, dtUrl)
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

        // --- Grouped reports for each collection parent ---
        collectionProjects.each { parent ->
            def children = allProjects.findAll { p -> p.active && p.parent?.uuid == parent.uuid }
            if (!children) {
                echo "Skipping collection ${parent.name} - no active children"
                return
            }

            def parentName    = parent.name
            def parentVersion = parent.version ?: 'unknown'
            echo "Generating grouped report for: ${parentName} ${parentVersion} (${children.size()} children)"

            try {
                def allFindings = []
                def aggMetrics  = [critical: 0, high: 0, medium: 0, low: 0, unassigned: 0, vulnerabilities: 0]

                children.each { child ->
                    def sourceName = child.name

                    def findingsJson = sh(script: """
                        curl -s '${dtUrl}/api/v1/finding/project/${child.uuid}?suppressed=true' \
                            -H "X-Api-Key: \$DT_API_KEY"
                    """, returnStdout: true).trim()

                    def metricsJson = sh(script: """
                        curl -s '${dtUrl}/api/v1/metrics/project/${child.uuid}/current' \
                            -H "X-Api-Key: \$DT_API_KEY"
                    """, returnStdout: true).trim()

                    def findings = readJSON text: (findingsJson ?: '[]')
                    def metrics  = readJSON text: (metricsJson  ?: '{}')

                    findings.each { f ->
                        f.sourceName  = sourceName
                        f.projectUuid = child.uuid
                    }
                    allFindings.addAll(findings)

                    aggMetrics.critical        += (metrics.critical        ?: 0)
                    aggMetrics.high            += (metrics.high            ?: 0)
                    aggMetrics.medium          += (metrics.medium          ?: 0)
                    aggMetrics.low             += (metrics.low             ?: 0)
                    aggMetrics.unassigned      += (metrics.unassigned      ?: 0)
                    aggMetrics.vulnerabilities += (metrics.vulnerabilities  ?: 0)
                }

                writeJSON file: 'findings.json', json: allFindings
                writeJSON file: 'metrics.json',  json: aggMetrics

                sh """
                    docker run --rm --network=host \
                        -v ${env.WORKSPACE}:/workspace \
                        -w /workspace \\
                        -e DT_API_URL='${dtUrl}' \\
                        -e DT_API_KEY="\$DT_API_KEY" \\
                        python:3.11-slim \\
                        bash -c 'pip install -q fpdf2 && python3 generate_vuln_report.py "${parentName}" "${parentVersion}"'
                """

                def safeFilename = "${parentName}-${parentVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
                sh """
                    mv vulnerability-report.pdf reports/${safeFilename}.pdf
                    mv findings.json reports/${safeFilename}-findings.json
                    mv metrics.json reports/${safeFilename}-metrics.json
                """
            } catch (Exception e) {
                echo "WARNING: Failed to generate grouped report for ${parentName} ${parentVersion}: ${e.message}"
            }
        }

        archiveArtifacts artifacts: 'reports/*.pdf,reports/*.json', allowEmptyArchive: false
        echo "All project reports generated and archived"
        echo "Download from: Build page -> Artifacts section"
    }
}
