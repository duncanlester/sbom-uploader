#!/usr/bin/env groovy

/**
 * Export a SBOM Component Report (PDF) covering all active Dependency-Track projects.
 *
 * Uses the parent field on project objects to detect collection vs standalone
 * (no extra API calls needed):
 *   - Has children → collection → one merged report from all children's BOMs
 *   - No children and not a child → standalone → individual report
 *
 * All PDFs are archived as build artifacts under reports/.
 *
 * @param dtUrl Dependency-Track API URL
 */
def call(String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {

        def allProjects = fetchAllDTProjects(dtUrl)
        sh 'mkdir -p reports tmp'
        writeFile file: 'generate_sbom_report.py', text: libraryResource('scripts/generate_sbom_report.py')

        // Build a local Docker image with fpdf2 pre-installed once, reused for every project
        writeFile file: 'Dockerfile.sbom-report', text: 'FROM python:3.11-slim\nRUN pip install -q fpdf2\n'
        sh 'docker build -t sbom-report-builder:local -f Dockerfile.sbom-report .'

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

        // ── Pass 2a: grouped (merged BOM) reports for each collection ────
        collectionMap.values().each { info ->
            def parent        = info.project
            def children      = info.children
            def parentName    = parent.name
            def parentVersion = parent.version ?: 'unknown'
            def safeFilename  = "${parentName}-${parentVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')

            echo "Generating grouped SBOM report: ${parentName} ${parentVersion} (${children.size()} children)"
            try {
                sh 'rm -rf boms bom.json && mkdir -p boms'
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
                        echo "  WARNING: Could not download BOM for ${child.name}: ${childErr.message}"
                    }
                }
                echo "  Downloaded ${downloadedCount}/${children.size()} child BOMs"
                if (downloadedCount > 0) {
                    sh """
                        docker run --rm --network=host \
                            -v ${env.WORKSPACE}:/workspace \
                            -w /workspace \\
                            sbom-report-builder:local \\
                            python3 generate_sbom_report.py "${parentName} ${parentVersion}"
                    """
                    sh "mv sbom-component-report.pdf reports/${safeFilename}-sbom.pdf"
                    echo "  -> OK: reports/${safeFilename}-sbom.pdf"
                } else {
                    echo "  SKIPPED: No child BOMs available for ${parentName}"
                }
            } catch (Exception e) {
                echo "WARNING: Failed grouped SBOM report for ${parentName} ${parentVersion}: ${e.message}"
            }
        }

        // ── Pass 2b: individual reports for collection children ──────────
        def allChildren = []
        collectionMap.values().each { info -> allChildren.addAll(info.children) }

        echo "=== COLLECTION CHILDREN (${allChildren.size()}) ==="
        allChildren.each { project ->
            def projectName    = project.name
            def projectVersion = project.version ?: 'unknown'
            def safeFilename   = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            echo "Generating SBOM report for child: ${projectName} ${projectVersion}"
            try {
                sh 'rm -rf boms bom.json'
                sh """
                    curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${project.uuid}' \
                        -H "X-Api-Key: \$DT_API_KEY" \
                        -H "Accept: application/vnd.cyclonedx+json" \
                        -o bom.json
                """
                sh """
                    docker run --rm --network=host \
                        -v ${env.WORKSPACE}:/workspace \
                        -w /workspace \\
                        sbom-report-builder:local \\
                        python3 generate_sbom_report.py "${projectName} ${projectVersion}"
                """
                sh "mv sbom-component-report.pdf reports/${safeFilename}-sbom.pdf"
                echo "  -> OK: reports/${safeFilename}-sbom.pdf"
            } catch (Exception e) {
                echo "WARNING: Failed SBOM report for ${projectName} ${projectVersion}: ${e.message}"
            }
        }

        // ── Pass 2c: standalone reports (not a collection, not a child) ──
        def standaloneProjects = allProjects.findAll { p ->
            p.active && !collectionMap.containsKey(p.uuid) && !childUUIDs.contains(p.uuid)
        }

        echo "=== STANDALONE PROJECTS (${standaloneProjects.size()}) ==="
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
                sh """
                    docker run --rm --network=host \
                        -v ${env.WORKSPACE}:/workspace \
                        -w /workspace \\
                        sbom-report-builder:local \\
                        python3 generate_sbom_report.py "${projectName} ${projectVersion}"
                """
                sh "mv sbom-component-report.pdf reports/${safeFilename}-sbom.pdf"
                echo "  -> OK: reports/${safeFilename}-sbom.pdf"
            } catch (Exception e) {
                echo "WARNING: Failed SBOM report for ${projectName} ${projectVersion}: ${e.message}"
            }
        }

        sh 'rm -f Dockerfile.sbom-report'
        archiveArtifacts artifacts: 'reports/*-sbom.pdf', allowEmptyArchive: true
        echo "All SBOM Component Reports generated — download from Build Artifacts"
    }
}
