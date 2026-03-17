#!/usr/bin/env groovy

/**
 * Create or update a Dependency-Track collection parent project and return its UUID.
 *
 * @param name        Project name (required)
 * @param version     Project version (required)
 * @param apiUrl      DT API base URL (default: env.DEPENDENCY_TRACK_API_URL)
 * @param classifier  DT classifier (default: 'APPLICATION')
 * @return            UUID string of the created/updated project
 */
def call(Map config = [:]) {
    def name       = config.name       ?: error('createDTCollectionProject: name is required')
    def version    = config.version    ?: error('createDTCollectionProject: version is required')
    def apiUrl     = config.apiUrl     ?: env.DEPENDENCY_TRACK_API_URL
    def classifier = config.classifier ?: 'APPLICATION'

    def parentUUID = ''
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {
        def response = sh(script: """
            curl -s -X PUT "${apiUrl}/api/v1/project" \\
                -H "X-Api-Key: \$DT_API_KEY" \\
                -H "Content-Type: application/json" \\
                -d '{"name":"${name}","version":"${version}","classifier":"${classifier}","active":true,"collectionLogic":"AGGREGATE_DIRECT_CHILDREN"}'
        """, returnStdout: true).trim()
        echo "Collection project response: ${response}"
        def json = readJSON text: response
        parentUUID = json.uuid
        echo "Collection project UUID for '${name}': ${parentUUID}"
    }
    return parentUUID
}
