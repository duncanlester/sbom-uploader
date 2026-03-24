#!/usr/bin/env groovy

/**
 * Export a SBOM Component Report (PDF) for a single Dependency-Track project.
 *
 * If the project has collectionLogic set, all active child BOMs are merged into
 * one report (matching the behaviour of exportAllSBOMReports for collections).
 * Otherwise the project's own BOM is used.
 *
 * @param projectName    Project name in Dependency-Track
 * @param projectVersion Project version in Dependency-Track
 * @param dtUrl          Dependency-Track API URL
 */
def call(String projectName, String projectVersion, String dtUrl = 'http://w-work-19.rdmz.isridev.com:8081') {
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {

        sh """
            curl -s -X GET '${dtUrl}/api/v1/project?pageSize=1000' \
                -H "X-Api-Key: \$DT_API_KEY" \
                -o projects.json
        """

        def projects        = readJSON file: 'projects.json'
        def matchingProject = projects.find { it.name == projectName && it.version == projectVersion }

        if (!matchingProject) {
            def matching = projects.findAll { it.name == projectName }
            error "Project '${projectName}' version '${projectVersion}' not found in Dependency-Track.\n" +
                  (matching ? "Available versions for '${projectName}':\n" + matching.collect { "  - ${it.version}" }.join('\n')
                            : "No projects found with name '${projectName}'")
        }

        echo "Project UUID: ${matchingProject.uuid}"
        writeFile file: 'generate_sbom_report.py', text: libraryResource('scripts/generate_sbom_report.py')
        sh 'rm -rf boms bom.json && mkdir -p reports'

        if (matchingProject.collectionLogic) {
            // ── Collection project: merge all active children into one report ──
            def children = projects.findAll { p -> p.active && p.parent?.uuid == matchingProject.uuid }
            echo "Collection project detected — ${children.size()} active children"

            if (children) {
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
                // No children — fall back to the collection parent's own BOM
                sh """
                    curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${matchingProject.uuid}' \
                        -H "X-Api-Key: \$DT_API_KEY" \
                        -H "Accept: application/vnd.cyclonedx+json" \
                        -o bom.json
                """
            }
        } else {
            // ── Standalone project: single BOM ────────────────────────────────
            sh """
                curl -sSf -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${matchingProject.uuid}' \
                    -H "X-Api-Key: \$DT_API_KEY" \
                    -H "Accept: application/vnd.cyclonedx+json" \
                    -o bom.json
            """
        }

        sh """
            docker run --rm --network=host \
                -v ${env.WORKSPACE}:/workspace \
                -w /workspace \
                python:3.11-slim \
                bash -c 'pip install -q fpdf2 && python3 generate_sbom_report.py "${projectName} ${projectVersion}"'
        """

        archiveArtifacts artifacts: 'sbom-component-report.pdf', allowEmptyArchive: false
        echo "SBOM Component Report generated — download from Build Artifacts"
    }
}
