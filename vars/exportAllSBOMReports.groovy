#!/usr/bin/env groovy

/**
 * Export a SBOM Component Report (PDF) covering all active Dependency-Track projects.
 *
 * Uses /v1/project/{uuid}/children to detect collection vs standalone:
 *   - Has children → collection → one merged report from all children's BOMs
 *   - No children and not a child → standalone → individual report
 *
 * All PDFs are archived as build artifacts under reports/.
 *
 * @param dtUrl Dependency-Track API URL
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
        writeFile file: 'generate_sbom_report.py', text: libraryResource('scripts/generate_sbom_report.py')

        // Helper: run Python against whatever bom file(s) are present
        def runPython = { String title, String safeFilename ->
            sh """
                docker run --rm --network=host \
                    -v ${env.WORKSPACE}:/workspace \
                    -w /workspace \
                    python:3.11-slim \
                    bash -c 'pip install -q fpdf2 && python3 generate_sbom_report.py "${title}"'
            """
            sh "mv sbom-component-report.pdf reports/${safeFilename}-sbom.pdf"
        }

        // ── Pass 1: discover collections via /children API ──────────────
        def collectionMap = [:]   // parentUUID → [project:…, children:[…]]
        def childUUIDs    = [] as Set

        allProjects.each { project ->
            // Fetch all children (paginated) inline to avoid CPS issues
            def allChildren = []
            def pageNumber = 1
            def keepGoing = true
            while (keepGoing) {
                def childrenRaw = sh(script: """
                    curl -s '${dtUrl}/api/v1/project/${project.uuid}/children?pageSize=500&pageNumber=${pageNumber}' \
                        -H "X-Api-Key: \$DT_API_KEY"
                """, returnStdout: true).trim()

                if (!childrenRaw || childrenRaw == 'null' || childrenRaw == '') {
                    keepGoing = false
                } else {
                    def page = readJSON text: childrenRaw
                    if (page instanceof List && page.size() > 0) {
                        allChildren.addAll(page)
                        keepGoing = (page.size() >= 500)
                        pageNumber++
                    } else {
                        keepGoing = false
                    }
                }
            }

            def activeChildren = allChildren.findAll { it.active }
            if (activeChildren) {
                collectionMap[project.uuid] = [project: project, children: activeChildren]
                activeChildren.each { childUUIDs.add(it.uuid) }
                echo "Collection found: ${project.name} (${activeChildren.size()} active children)"
            }
        }

        echo "Discovered ${collectionMap.size()} collection(s), ${childUUIDs.size()} child project(s)"

        // ── Pass 2a: standalone projects — one report each ──────────────
        def standaloneProjects = allProjects.findAll { p ->
            p.active && !collectionMap.containsKey(p.uuid) && !childUUIDs.contains(p.uuid)
        }

        standaloneProjects.each { project ->
            def projectName    = project.name
            def projectVersion = project.version ?: 'unknown'
            def safeFilename   = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            echo "Generating SBOM report for: ${projectName} ${projectVersion}"
            try {
                sh 'rm -rf boms bom.json'
                sh """
                    curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${project.uuid}' \
                        -H "X-Api-Key: \$DT_API_KEY" \
                        -H "Accept: application/vnd.cyclonedx+json" \
                        -o bom.json
                """
                runPython("${projectName} ${projectVersion}", safeFilename)
            } catch (Exception e) {
                echo "WARNING: Failed SBOM report for ${projectName} ${projectVersion}: ${e.message}"
            }
        }

        // ── Pass 2b: collection parents — one merged report each ────────
        collectionMap.values().each { info ->
            def parent        = info.project
            def children      = info.children
            def parentName    = parent.name
            def parentVersion = parent.version ?: 'unknown'
            def safeFilename  = "${parentName}-${parentVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')

            echo "Generating SBOM report for collection: ${parentName} ${parentVersion} (${children.size()} children)"
            try {
                sh 'rm -rf boms bom.json'
                sh 'mkdir -p boms'
                children.each { child ->
                    def childSafe = child.name.replaceAll('[^a-zA-Z0-9.-]', '_')
                    sh """
                        curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${child.uuid}' \
                            -H "X-Api-Key: \$DT_API_KEY" \
                            -H "Accept: application/vnd.cyclonedx+json" \
                            -o "boms/${childSafe}.json"
                    """
                }
                runPython("${parentName} ${parentVersion}", safeFilename)
            } catch (Exception e) {
                echo "WARNING: Failed SBOM report for ${parentName} ${parentVersion}: ${e.message}"
            }
        }

        archiveArtifacts artifacts: 'reports/*-sbom.pdf', allowEmptyArchive: true
        echo "All SBOM Component Reports generated — download from Build Artifacts"
    }
}
