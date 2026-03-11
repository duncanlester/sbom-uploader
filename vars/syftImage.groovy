#!/usr/bin/env groovy

/**
 * Generate SBOM for Docker images using Syft
 *
 * @param imageName The Docker image name to scan (e.g., 'atlassian/jira:latest')
 * @param outputFile The output file path for the SBOM (e.g., 'sbom-jira.json')
 * @param syftFlags Optional list of Syft flags (e.g., ['--quiet'])
 * @param scanPath Optional path within the image to scan (e.g., '/opt/atlassian/confluence')
 */
def call(String imageName, String outputFile, List syftFlags = [], String scanPath = '') {
    def flags = syftFlags.join(' ')
    def pathFlag = scanPath ? "--base-path '${scanPath}'" : ''

    sh """
        echo "Pulling Docker image: ${imageName}"
        docker pull ${imageName}

        echo "Generating SBOM with Syft..."
        /usr/local/bin/syft ${imageName} -o cyclonedx-json ${flags} ${pathFlag} > ${outputFile}

        echo "SBOM generated: \$(wc -c < ${outputFile}) bytes"
    """
}
