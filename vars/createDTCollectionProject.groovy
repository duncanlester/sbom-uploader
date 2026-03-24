#!/usr/bin/env groovy

/**
 * Create or update a Dependency-Track collection parent project and return its UUID.
 *
 * @param name        Project name (required)
 * @param version     Project version (required)
 * @param apiUrl      DT API base URL (default: env.DEPENDENCY_TRACK_API_URL)
 * @param apiUrl      DT API base URL (default: env.DEPENDENCY_TRACK_API_URL)
 * @return            UUID string of the created/updated project
 */
def call(Map config = [:]) {
    def name       = config.name       ?: error('createDTCollectionProject: name is required')
    def version    = config.version    ?: error('createDTCollectionProject: version is required')
    def apiUrl     = config.apiUrl     ?: env.DEPENDENCY_TRACK_API_URL

    def parentUUID = ''
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {
        def response = sh(script: """
            curl -s -X PUT "${apiUrl}/api/v1/project" \\
                -H "X-Api-Key: \$DT_API_KEY" \\
                -H "Content-Type: application/json" \\
                -d '{"name":"${name}","version":"${version}","active":true,"collectionLogic":"AGGREGATE_DIRECT_CHILDREN"}'
        """, returnStdout: true).trim()
        echo "Collection project response: ${response}"

        // DT returns plain text (not JSON) when the project already exists —
        // fall back to a lookup by name + version to get the UUID.
        if (response.startsWith('{')) {
            def json = readJSON text: response
            parentUUID = json.uuid
        } else {
            echo "Project '${name}' already exists — looking up UUID..."
            def lookup = sh(script: """
                curl -s -X GET "${apiUrl}/api/v1/project/lookup?name=${URLEncoder.encode(name, 'UTF-8')}&version=${URLEncoder.encode(version, 'UTF-8')}" \\
                    -H "X-Api-Key: \$DT_API_KEY"
            """, returnStdout: true).trim()
            def json = readJSON text: lookup
            parentUUID = json.uuid
        }
        echo "Collection project UUID for '${name}': ${parentUUID}"
    }
    return parentUUID
}
