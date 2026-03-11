#!/usr/bin/env groovy

/**
 * Upload SBOM to Dependency Track
 *
 * @param sbomFile The SBOM file to upload
 * @param projectName The project name in Dependency Track
 * @param projectVersion The project version
 * @param apiUrl The Dependency Track API URL (default from env)
 * @param apiKeyCredId The Jenkins credential ID for Dependency Track API key
 */
def call(Map config) {
    def sbomFile = config.sbomFile
    def projectName = config.projectName
    def projectVersion = config.projectVersion
    def apiUrl = config.apiUrl ?: env.DEPENDENCY_TRACK_API_URL
    def apiKeyCredId = config.apiKeyCredId ?: 'dependency-track-api-key'

    withCredentials([string(credentialsId: apiKeyCredId, variable: 'DT_API_KEY')]) {
        sh """
            echo "Uploading SBOM to Dependency Track..."
            curl -s -X POST "${apiUrl}/api/v1/bom" \
                -H "X-Api-Key: \$DT_API_KEY" \
                -F "projectName=${projectName}" \
                -F "projectVersion=${projectVersion}" \
                -F "classifier=APPLICATION" \
                -F "autoCreate=true" \
                -F "bom=@${sbomFile}"
            echo ""
            echo "SBOM uploaded successfully"
        """
    }
}
