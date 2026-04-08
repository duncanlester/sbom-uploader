#!/usr/bin/env groovy

/**
 * Export Dependency Track vulnerability reports for all active projects.
 *
 * Uses the parent field on project objects to detect collection vs standalone
 * (no extra API calls needed):
 *   - Has children → collection → single grouped report from all children
 *   - No children and not a child → standalone → individual report
 *
 * @param dtUrl Dependency Track API URL (default: 'http://w-work-19.rdmz.isridev.com:8081')
 */
def call(String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {

        def allProjects = fetchAllDTProjects(dtUrl)
        sh 'mkdir -p reports tmp'
        writeFile file: 'generate_vuln_report.py', text: libraryResource('scripts/generate_vuln_report.py')

        // Build a local Docker image with fpdf2 pre-installed once, reused for every project
        writeFile file: 'Dockerfile.vuln-report', text: 'FROM python:3.11-slim\nRUN pip install -q fpdf2\n'
        sh 'docker build -t vuln-report-builder:local -f Dockerfile.vuln-report .'

        // ── Discovery: derive collections from parent field ───────────────
        // DT returns the parent field on every project object — no extra API calls needed.
        def collectionMap = [:]   // parentUUID → [project:…, children:[…]]
        def childUUIDs    = [] as Set

        allProjects.each { project ->
            if (project.parent && project.parent.uuid) {
                def parentUuid = project.parent.uuid
                if (!collectionMap.containsKey(parentUuid)) {
                    def parentProject = allProjects.find { it.uuid == parentUuid }
                    if (parentProject) {
                        collectionMap[parentUuid] = [project: parentProject, children: []]
                    }
                }
                if (collectionMap.containsKey(parentUuid) && project.active) {
                    collectionMap[parentUuid].children << project
                    childUUIDs.add(project.uuid)
                }
            }
        }

        echo "=== DISCOVERY SUMMARY ==="
        echo "Collections: ${collectionMap.size()}, children: ${childUUIDs.size()}"
        collectionMap.each { uuid, info ->
            echo "  Collection: ${info.project.name} → ${info.children.size()} active children"
        }

        // ── Build parallel report tasks ───────────────────────────────────
        def reportTasks = [failFast: false]

        // Grouped reports for each collection
        collectionMap.values().each { collectionInfo ->
            def parent         = collectionInfo.project
            def children       = collectionInfo.children
            def projectName    = parent.name
            def projectVersion = parent.version ?: 'unknown'
            def safeFilename   = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            def taskWorkDir    = "tmp/${parent.uuid}"

            reportTasks["grouped-${safeFilename}"] = {
                echo "Generating grouped report: ${projectName} ${projectVersion} (${children.size()} children)"
                try {
                    sh "mkdir -p ${taskWorkDir}"
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

                        findings.each { f -> f.sourceName = sourceName; f.projectUuid = child.uuid }
                        allFindings.addAll(findings)

                        aggMetrics.critical        += (metrics.critical        ?: 0)
                        aggMetrics.high            += (metrics.high            ?: 0)
                        aggMetrics.medium          += (metrics.medium          ?: 0)
                        aggMetrics.low             += (metrics.low             ?: 0)
                        aggMetrics.unassigned      += (metrics.unassigned      ?: 0)
                        aggMetrics.vulnerabilities += (metrics.vulnerabilities ?: 0)
                    }

                    writeJSON file: "${taskWorkDir}/findings.json", json: allFindings
                    writeJSON file: "${taskWorkDir}/metrics.json",  json: aggMetrics

                    sh """
                        docker run --rm --network=host \
                            -v ${env.WORKSPACE}:/workspace:ro \
                            -v ${env.WORKSPACE}/${taskWorkDir}:/data \
                            -w /data \\
                            -e DT_API_URL='${dtUrl}' \\
                            -e DT_API_KEY="\$DT_API_KEY" \\
                            vuln-report-builder:local \\
                            python3 /workspace/generate_vuln_report.py "${projectName}" "${projectVersion}"
                    """

                    sh """
                        mv ${taskWorkDir}/vulnerability-report.pdf reports/${safeFilename}.pdf
                        mv ${taskWorkDir}/findings.json reports/${safeFilename}-findings.json
                        mv ${taskWorkDir}/metrics.json reports/${safeFilename}-metrics.json
                    """
                } catch (Exception e) {
                    echo "WARNING: Failed grouped report for ${projectName} ${projectVersion}: ${e.message}"
                }
            }
        }

        // Individual reports for collection children + standalones
        def projectsToReport = []
        collectionMap.values().each { info -> projectsToReport.addAll(info.children) }
        def standaloneProjects = allProjects.findAll { p ->
            p.active && !collectionMap.containsKey(p.uuid) && !childUUIDs.contains(p.uuid)
        }
        projectsToReport.addAll(standaloneProjects)

        echo "=== INDIVIDUAL REPORTS: ${projectsToReport.size()} projects ==="

        projectsToReport.each { projectEntry ->
            def pName        = projectEntry.name
            def pVersion     = projectEntry.version ?: 'unknown'
            def pUuid        = projectEntry.uuid
            def safeFilename = "${pName}-${pVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            def taskWorkDir  = "tmp/${pUuid}"

            reportTasks["report-${safeFilename}"] = {
                echo "Generating report: ${pName} ${pVersion}"
                try {
                    sh "mkdir -p ${taskWorkDir}"

                    def findingsJson = sh(script: """
                        curl -s '${dtUrl}/api/v1/finding/project/${pUuid}?suppressed=true' \
                            -H "X-Api-Key: \$DT_API_KEY"
                    """, returnStdout: true).trim()

                    def metricsJson = sh(script: """
                        curl -s '${dtUrl}/api/v1/metrics/project/${pUuid}/current' \
                            -H "X-Api-Key: \$DT_API_KEY"
                    """, returnStdout: true).trim()

                    def findings = readJSON text: (findingsJson ?: '[]')
                    findings.each { f -> f.projectUuid = pUuid }
                    writeJSON file: "${taskWorkDir}/findings.json", json: findings
                    writeFile file: "${taskWorkDir}/metrics.json", text: (metricsJson ?: '{}')

                    sh """
                        docker run --rm --network=host \
                            -v ${env.WORKSPACE}:/workspace:ro \
                            -v ${env.WORKSPACE}/${taskWorkDir}:/data \
                            -w /data \\
                            -e DT_API_URL='${dtUrl}' \\
                            -e DT_API_KEY="\$DT_API_KEY" \\
                            vuln-report-builder:local \\
                            python3 /workspace/generate_vuln_report.py "${pName}" "${pVersion}"
                    """

                    sh """
                        mv ${taskWorkDir}/vulnerability-report.pdf reports/${safeFilename}.pdf
                        mv ${taskWorkDir}/findings.json reports/${safeFilename}-findings.json
                        mv ${taskWorkDir}/metrics.json reports/${safeFilename}-metrics.json
                    """
                } catch (Exception e) {
                    echo "WARNING: Failed report for ${pName} ${pVersion}: ${e.message}"
                }
            }
        }

        parallel reportTasks

        sh 'rm -rf tmp Dockerfile.vuln-report'
        archiveArtifacts artifacts: 'reports/*.pdf,reports/*.json', allowEmptyArchive: false
        echo "All project reports generated and archived"
        echo "Download from: Build page -> Artifacts section"
    }
}
