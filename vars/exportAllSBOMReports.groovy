#!/usr/bin/env groovy

/**
 * Export a SBOM Component Report (PDF) covering all active Dependency-Track projects.
 *
 * - Collection parents (e.g. jenkins-plugins): iterates each active child,
 *   downloads their BOM, and generates one merged report per collection.
 * - Standalone projects: each gets its own report.
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

        // Derive parent/child relationships from the 'parent' field DT reliably
        // includes on child projects in the flat listing.  We deliberately avoid
        // relying on 'collectionLogic', which is often absent from the list response.
        def childProjects      = allProjects.findAll { it.parent?.uuid }
        def collectionUUIDs    = childProjects.collect { it.parent.uuid } as Set
        def childUUIDs         = childProjects.collect { it.uuid } as Set
        def collectionProjects = allProjects.findAll { collectionUUIDs.contains(it.uuid) }

        def standaloneProjects = allProjects.findAll { p ->
            p.active && !collectionUUIDs.contains(p.uuid) && !childUUIDs.contains(p.uuid)
        }

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

        // ── Standalone projects — one report each ───────────────────────────
        standaloneProjects.each { project ->
            def projectName    = project.name
            def projectVersion = project.version ?: 'unknown'
            def safeFilename   = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            echo "Generating SBOM report for: ${projectName} ${projectVersion}"
            try {
                // Clean up any leftover boms/ so Python falls through to bom.json
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

        // ── Collection parents — one merged report per collection ────────────
        collectionProjects.each { parent ->
            def children      = childProjects.findAll { it.active && it.parent?.uuid == parent.uuid }
            def parentName    = parent.name
            def parentVersion = parent.version ?: 'unknown'
            def safeFilename  = "${parentName}-${parentVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')

            echo "Generating SBOM report for collection: ${parentName} ${parentVersion} (${children.size()} children)"
            try {
                sh 'rm -rf boms bom.json'

                if (children) {
                    // Merged: one BOM file per child in boms/
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
                } else {
                    // No children — report on the parent's own BOM
                    sh """
                        curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${parent.uuid}' \
                            -H "X-Api-Key: \$DT_API_KEY" \
                            -H "Accept: application/vnd.cyclonedx+json" \
                            -o bom.json
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
