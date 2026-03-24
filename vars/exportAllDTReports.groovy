#!/usr/bin/env groovy

/**
 * Export Dependency Track vulnerability reports for all active projects.
 *
 * Uses /v1/project/{uuid}/children to detect collection vs standalone:
 *   - Has children → collection → single grouped report from all children
 *   - No children and not a child → standalone → individual report
 *
 * @param dtUrl Dependency Track API URL (default: 'http://w-work-19.rdmz.isridev.com:8081')
 */
def call(String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {

        def allProjects = fetchAllDTProjects(dtUrl)
        sh 'mkdir -p reports'eta
        writeFile file: 'generate_vuln_report.py', text: libraryResource('scripts/generate_vuln_report.py')

        // ── Pass 1: discover collections ──────────────────────────────
        // Check EVERY project (including inactive) for children so we
        // don't miss a collection parent that happens to be inactive.
        def collectionMap = [:]   // parentUUID → [project:…, children:[…]]
        def childUUIDs    = [] as Set

        allProjects.each { project ->
            echo "DEBUG: Checking /children for: ${project.name} (uuid=${project.uuid}, active=${project.active})"

            // Fetch children inline (paginated) — no separate method to avoid CPS issues
            def allChildren = []
            def pageNumber = 1
            def keepGoing = true
            while (keepGoing) {
                def childrenRaw = sh(script: """
                    curl -s '${dtUrl}/api/v1/project/${project.uuid}/children?pageSize=500&pageNumber=${pageNumber}' \
                        -H "X-Api-Key: \$DT_API_KEY"
                """, returnStdout: true).trim()

                echo "DEBUG:   /children page ${pageNumber} raw length: ${childrenRaw.length()} chars"
                if (!childrenRaw || childrenRaw == 'null' || childrenRaw == '') {
                    echo "DEBUG:   /children returned empty/null — breaking"
                    keepGoing = false
                } else {
                    def page = readJSON text: childrenRaw
                    echo "DEBUG:   /children page ${pageNumber} returned ${page instanceof List ? page.size() : 'non-list: ' + page.getClass()} items"
                    if (page instanceof List && page.size() > 0) {
                        allChildren.addAll(page)
                        if (page.size() < 500) {
                            keepGoing = false
                        } else {
                            pageNumber++
                        }
                    } else {
                        keepGoing = false
                    }
                }
            }

            def activeChildren = allChildren.findAll { it.active }
            echo "DEBUG:   Total children: ${allChildren.size()}, active: ${activeChildren.size()}"

            if (activeChildren) {
                collectionMap[project.uuid] = [project: project, children: activeChildren]
                activeChildren.each { childUUIDs.add(it.uuid) }
                echo "COLLECTION FOUND: ${project.name} → ${activeChildren.size()} active children"
            }
        }

        echo "=== DISCOVERY SUMMARY ==="
        echo "Collections: ${collectionMap.size()}"
        echo "Child UUIDs: ${childUUIDs.size()}"
        collectionMap.each { uuid, info ->
            echo "  Collection: ${info.project.name} (${info.children.size()} children)"
        }

        // ── Pass 2a: grouped reports for each collection ──────────────
        collectionMap.values().each { info ->
            def parent   = info.project
            def children = info.children
            def projectName    = parent.name
            def projectVersion = parent.version ?: 'unknown'

            echo "Generating grouped report for: ${projectName} ${projectVersion} (${children.size()} children)"
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
                    aggMetrics.vulnerabilities += (metrics.vulnerabilities ?: 0)
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
                        bash -c 'pip install -q fpdf2 && python3 generate_vuln_report.py "${projectName}" "${projectVersion}"'
                """

                def safeFilename = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
                sh """
                    mv vulnerability-report.pdf reports/${safeFilename}.pdf
                    mv findings.json reports/${safeFilename}-findings.json
                    mv metrics.json reports/${safeFilename}-metrics.json
                """
            } catch (Exception e) {
                echo "WARNING: Failed to generate grouped report for ${projectName} ${projectVersion}: ${e.message}"
            }
        }

        // ── Pass 2b: standalone reports (not a collection, not a child) ──
        def standaloneProjects = allProjects.findAll { p ->
            p.active && !collectionMap.containsKey(p.uuid) && !childUUIDs.contains(p.uuid)
        }

        echo "=== STANDALONE PROJECTS (${standaloneProjects.size()}) ==="
        standaloneProjects.each { echo "  Standalone: ${it.name} ${it.version}" }

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

        archiveArtifacts artifacts: 'reports/*.pdf,reports/*.json', allowEmptyArchive: false
        echo "All project reports generated and archived"
        echo "Download from: Build page -> Artifacts section"
    }
}
