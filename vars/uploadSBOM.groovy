#!/usr/bin/env groovy

/**
 * Upload SBOM to Dependency Track
 *
 * @param sbomFile The SBOM file to upload
 * @param projectName The project name in Dependency Track
 * @param projectVersion The project version
 * @param apiUrl The Dependency Track API URL (default from env)
 * @param apiKeyCredId The Jenkins credential ID for Dependency Track API key
 * @param parentUUID UUID of the parent (collection) project — sets the parent/child relationship
 */
def call(Map config) {
    def sbomFile       = config.sbomFile
    def projectName    = config.projectName
    def projectVersion = config.projectVersion
    def apiUrl         = config.apiUrl ?: env.DEPENDENCY_TRACK_API_URL
    def apiKeyCredId   = config.apiKeyCredId ?: 'dependency-track-api-key'
    def parentUUID     = config.parentUUID ?: ''

    withCredentials([string(credentialsId: apiKeyCredId, variable: 'DT_API_KEY')]) {

        // Step 1: create or look up the child project to get its UUID
        def parentJson = parentUUID ? """, \\"parent\\": {\\"uuid\\": \\"${parentUUID}\\"}""" : ''
        def projectResponse = sh(script: """
            curl -s -X PUT "${apiUrl}/api/v1/project" \\
                -H "X-Api-Key: \$DT_API_KEY" \\
                -H "Content-Type: application/json" \\
                -d "{\\"name\\": \\"${projectName}\\", \\"version\\": \\"${projectVersion}\\", \\"classifier\\": \\"APPLICATION\\", \\"active\\": true${parentJson}}"
        """, returnStdout: true).trim()

        def projectUUID = ''
        if (projectResponse.startsWith('{')) {
            projectUUID = readJSON(text: projectResponse).uuid
        } else {
            // Project already exists and PUT did not return JSON — look it up by name+version
            def lookup = sh(script: """
                curl -s "${apiUrl}/api/v1/project/lookup?name=${URLEncoder.encode(projectName, 'UTF-8')}&version=${URLEncoder.encode(projectVersion, 'UTF-8')}" \\
                    -H "X-Api-Key: \$DT_API_KEY"
            """, returnStdout: true).trim()
            projectUUID = readJSON(text: lookup).uuid
        }

        // Step 2: PATCH the project to ensure the parent is set (PUT only sets parent on creation)
        if (parentUUID) {
            sh """
                curl -s -X PATCH "${apiUrl}/api/v1/project/${projectUUID}" \\
                    -H "X-Api-Key: \$DT_API_KEY" \\
                    -H "Content-Type: application/json" \\
                    -d "{\\"parent\\": {\\"uuid\\": \\"${parentUUID}\\"}}"
            """
        }

        echo "  Uploading SBOM for ${projectName} (UUID: ${projectUUID})..."

        // Step 3: upload the BOM to the specific project UUID
        sh """
            curl -s -X POST "${apiUrl}/api/v1/bom" \\
                -H "X-Api-Key: \$DT_API_KEY" \\
                -F "project=${projectUUID}" \\
                -F "bom=@${sbomFile}"
            echo ""
        """
    }
}
