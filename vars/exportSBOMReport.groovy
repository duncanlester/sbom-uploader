#!/usr/bin/env groovy

/**
 * Export a SBOM Component Report (PDF) for a single Dependency-Track project.
 *
 * Downloads the CycloneDX BOM from DT and generates a PDF table of all
 * components with their version, type, PURL, and licenses.
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

        def projects       = readJSON file: 'projects.json'
        def matchingProject = projects.find { it.name == projectName && it.version == projectVersion }

        if (!matchingProject) {
            def matching = projects.findAll { it.name == projectName }
            error "Project '${projectName}' version '${projectVersion}' not found in Dependency-Track.\n" +
                  (matching ? "Available versions for '${projectName}':\n" + matching.collect { "  - ${it.version}" }.join('\n')
                            : "No projects found with name '${projectName}'")
        }

        def projectUuid = matchingProject.uuid
        echo "Project UUID: ${projectUuid}"

        // Download the CycloneDX BOM for this project as JSON
        sh """
            curl -s -X GET '${dtUrl}/api/v1/bom/cyclonedx/project/${projectUuid}' \
                -H "X-Api-Key: \$DT_API_KEY" \
                -H "Accept: application/json" \
                -o bom.json
        """

        writeFile file: 'generate_sbom_report.py', text: libraryResource('scripts/generate_sbom_report.py')

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
