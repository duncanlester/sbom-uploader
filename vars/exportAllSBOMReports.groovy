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
        sh 'mkdir -p reports boms'
        writeFile file: 'generate_sbom_report.py', text: libraryResource('scripts/generate_sbom_report.py')

        def collectionProjects = allProjects.findAll { it.collectionLogic && it.active }
        def collectionUUIDs    = collectionProjects.collect { it.uuid } as Set
        def childUUIDs         = allProjects.findAll { it.parent && collectionUUIDs.contains(it.parent?.uuid) }
                                            .collect { it.uuid } as Set

        def standaloneProjects = allProjects.findAll { p ->
            p.active && !p.collectionLogic && !childUUIDs.contains(p.uuid)
        }

        // ── Standalone projects — one report each ───────────────────────────
        standaloneProjects.each { project ->
            def projectName    = project.name
            def projectVersion = project.version ?: 'unknown'
            def safeFilename   = "${projectName}-${projectVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            echo "Generating SBOM report for: ${projectName} ${projectVersion}"
            try {
                sh """
                    curl -s -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${project.uuid}' \
                        -H "X-Api-Key: \$DT_API_KEY" \
                        -H "Accept: application/json" \
                        -o bom.json
                """

                sh """
                    docker run --rm --network=host \
                        -v ${env.WORKSPACE}:/workspace \
                        -w /workspace \
                        python:3.11-slim \
                        bash -c 'pip install -q fpdf2 && python3 generate_sbom_report.py "${projectName} ${projectVersion}"'
                """

                sh "mv sbom-component-report.pdf reports/${safeFilename}-sbom.pdf"
            } catch (Exception e) {
                echo "WARNING: Failed SBOM report for ${projectName} ${projectVersion}: ${e.message}"
            }
        }

        // ── Collection parents — one merged report per collection ────────────
        collectionProjects.each { parent ->
            def children = allProjects.findAll { p -> p.active && p.parent?.uuid == parent.uuid }
            if (!children) {
                echo "Skipping collection ${parent.name} — no active children"
                return
            }

            def parentName    = parent.name
            def parentVersion = parent.version ?: 'unknown'
            def safeFilename  = "${parentName}-${parentVersion}".replaceAll('[^a-zA-Z0-9.-]', '_')
            echo "Generating merged SBOM report for collection: ${parentName} ${parentVersion} (${children.size()} children)"

            try {
                sh 'rm -rf boms && mkdir -p boms'

                children.each { child ->
                    def childSafe = child.name.replaceAll('[^a-zA-Z0-9.-]', '_')
                    sh """
                        curl -s -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${child.uuid}' \
                            -H "X-Api-Key: \$DT_API_KEY" \
                            -H "Accept: application/json" \
                            -o "boms/${childSafe}.json"
                    """
                }

                sh """
                    docker run --rm --network=host \
                        -v ${env.WORKSPACE}:/workspace \
                        -w /workspace \
                        python:3.11-slim \
                        bash -c 'pip install -q fpdf2 && python3 generate_sbom_report.py "${parentName} ${parentVersion}"'
                """

                sh "mv sbom-component-report.pdf reports/${safeFilename}-sbom.pdf"
            } catch (Exception e) {
                echo "WARNING: Failed merged SBOM report for ${parentName} ${parentVersion}: ${e.message}"
            }
        }

        archiveArtifacts artifacts: 'reports/*-sbom.pdf', allowEmptyArchive: false
        echo "All SBOM Component Reports generated — download from Build Artifacts"
    }
}
