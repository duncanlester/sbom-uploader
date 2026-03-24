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

        // Paginate through all projects (DT caps at 100 per page)
        def allProjects = []
        def projectPage = 1
        def fetchMore = true
        while (fetchMore) {
            def pageJson = sh(script: """
                curl -s -X GET '${dtUrl}/api/v1/project?pageSize=100&pageNumber=${projectPage}' \
                    -H "X-Api-Key: \$DT_API_KEY"
            """, returnStdout: true).trim()

            if (!pageJson || pageJson == '[]' || pageJson == 'null') {
                fetchMore = false
            } else {
                def page = readJSON text: pageJson
                if (page instanceof List && page.size() > 0) {
                    allProjects.addAll(page)
                    fetchMore = (page.size() >= 100)
                    projectPage++
                } else {
                    fetchMore = false
                }
            }
        }
        echo "Fetched ${allProjects.size()} projects from Dependency-Track (${projectPage - 1} page(s))"
        allProjects.each { p ->
            echo "  Project: ${p.name} (version=${p.version}, active=${p.active}, uuid=${p.uuid})"
        }

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

        // ── Pass 1a: discover collections via /children API ─────────────
        def collectionMap = [:]   // parentUUID → [project:…, children:[…]]
        def childUUIDs    = [] as Set

        // Index projects by UUID for quick lookup
        def projectsByUUID = [:]
        allProjects.each { p -> projectsByUUID[p.uuid] = p }

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
                echo "Collection found via /children: ${project.name} (${activeChildren.size()} active children)"
                activeChildren.each { child ->
                    echo "  Child: ${child.name} (uuid=${child.uuid})"
                }
            }
        }

        echo "After /children pass: ${collectionMap.size()} collection(s), ${childUUIDs.size()} child(ren)"

        // ── Pass 1b: fallback — also check parent field from flat listing ──
        // DT includes parent.uuid on child projects in the flat listing.
        // This catches relationships that /children doesn't return (e.g.
        // parent set via API PATCH but not indexed for /children).
        allProjects.each { project ->
            def parentUUID = project.parent?.uuid
            if (parentUUID && project.active && !childUUIDs.contains(project.uuid)) {
                // This child wasn't found via /children — add it
                if (!collectionMap.containsKey(parentUUID)) {
                    def parentProject = projectsByUUID[parentUUID]
                    if (parentProject) {
                        collectionMap[parentUUID] = [project: parentProject, children: []]
                        echo "Collection found via parent field: ${parentProject.name} (uuid=${parentUUID})"
                    } else {
                        // Parent not in initial listing — fetch it
                        echo "Parent ${parentUUID} not in project list, fetching..."
                        def parentRaw = sh(script: """
                            curl -s '${dtUrl}/api/v1/project/${parentUUID}' \
                                -H "X-Api-Key: \$DT_API_KEY"
                        """, returnStdout: true).trim()
                        if (parentRaw && parentRaw.startsWith('{')) {
                            def fetchedParent = readJSON text: parentRaw
                            collectionMap[parentUUID] = [project: fetchedParent, children: []]
                            echo "Collection found via parent field (fetched): ${fetchedParent.name}"
                        }
                    }
                }
                if (collectionMap.containsKey(parentUUID)) {
                    collectionMap[parentUUID].children.add(project)
                    childUUIDs.add(project.uuid)
                    echo "  Child (from parent field): ${project.name} (uuid=${project.uuid})"
                }
            }
        }

        echo "Final: ${collectionMap.size()} collection(s), ${childUUIDs.size()} child project(s)"

        // ── Pass 2a: standalone projects — one report each ──────────────
        def standaloneProjects = allProjects.findAll { p ->
            p.active && !collectionMap.containsKey(p.uuid) && !childUUIDs.contains(p.uuid)
        }

        echo "Standalone projects (${standaloneProjects.size()}):"
        standaloneProjects.each { p -> echo "  Standalone: ${p.name} ${p.version ?: 'unknown'}" }

        // Log skipped projects
        def inactiveProjects = allProjects.findAll { !it.active }
        if (inactiveProjects) {
            echo "Skipped inactive projects (${inactiveProjects.size()}):"
            inactiveProjects.each { p -> echo "  Inactive: ${p.name} ${p.version ?: 'unknown'}" }
        }

        standaloneProjects.each { project ->
            def projectName    = project.name
            def projectVersion = project.version ?: 'unknown'
            def safeFilename   = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            echo "Generating SBOM report for standalone: ${projectName} ${projectVersion}"
            try {
                sh 'rm -rf boms bom.json'
                sh """
                    curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${project.uuid}' \
                        -H "X-Api-Key: \$DT_API_KEY" \
                        -H "Accept: application/vnd.cyclonedx+json" \
                        -o bom.json
                """
                runPython("${projectName} ${projectVersion}", safeFilename)
                echo "  -> OK: reports/${safeFilename}-sbom.pdf"
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
                def downloadedCount = 0
                children.each { child ->
                    def childSafe = child.name.replaceAll('[^a-zA-Z0-9.-]', '_')
                    try {
                        sh """
                            curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${child.uuid}' \
                                -H "X-Api-Key: \$DT_API_KEY" \
                                -H "Accept: application/vnd.cyclonedx+json" \
                                -o "boms/${childSafe}.json"
                        """
                        downloadedCount++
                    } catch (Exception childErr) {
                        echo "  WARNING: Could not download BOM for child ${child.name} (${child.uuid}): ${childErr.message}"
                    }
                }
                echo "  Downloaded ${downloadedCount}/${children.size()} child BOMs"
                if (downloadedCount > 0) {
                    runPython("${parentName} ${parentVersion}", safeFilename)
                    echo "  -> OK: reports/${safeFilename}-sbom.pdf"
                } else {
                    echo "  SKIPPED: No child BOMs available for ${parentName}"
                }
            } catch (Exception e) {
                echo "WARNING: Failed SBOM report for collection ${parentName} ${parentVersion}: ${e.message}"
            }
        }

        archiveArtifacts artifacts: 'reports/*-sbom.pdf', allowEmptyArchive: true
        echo "All SBOM Component Reports generated — download from Build Artifacts"
    }
}
