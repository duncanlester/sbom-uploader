#!/usr/bin/env groovy

/**
 * Upload per-plugin SBOMs to Dependency-Track.
 *
 * Reads plugins-list.txt to map plugin IDs to their installed versions,
 * then uploads every sboms/<id>.json as a separate DT project named
 * jenkins-plugin-<id>.
 *
 * @param pluginsFile  Path to the plugins-list.txt produced by list-plugins (default: 'plugins-list.txt')
 * @param sbomGlob     Glob for SBOM files to upload (default: 'sboms/*.json')
 */
def call(Map config = [:]) {
    def pluginsFile = config.pluginsFile ?: 'plugins-list.txt'
    def sbomGlob = config.sbomGlob ?: 'sboms/*.json'
    def jenkinsVersion = config.jenkinsVersion ?: 'unknown'
    def apiUrl = config.apiUrl ?: env.DEPENDENCY_TRACK_API_URL

    def pluginVersions = [:]
    readFile(pluginsFile).readLines().each { line ->
        def parts = line.trim().split(/\s+/)
        if (parts.size() >= 2) {
            def version = parts.findAll { !it.startsWith('(') }.last()
            pluginVersions[parts[0]] = version
        }
    }

    def sbomFiles = findFiles(glob: sbomGlob)
    echo "Uploading ${sbomFiles.size()} SBOMs to Dependency-Track..."

    // Create/update the collection parent project and capture its UUID
    def parentUUID = ''
    withCredentials([string(credentialsId: 'dependency-track-api-key', variable: 'DT_API_KEY')]) {
        def response = sh(script: """
            curl -s -X PUT "${apiUrl}/api/v1/project" \\
                -H "X-Api-Key: \$DT_API_KEY" \\
                -H "Content-Type: application/json" \\
                -d '{"name":"jenkins-plugins","version":"${jenkinsVersion}","classifier":"APPLICATION","active":true,"collectionLogic":"AGGREGATE_DIRECT_CHILDREN"}'
        """, returnStdout: true).trim()
        echo "Parent project response: ${response}"
        def json = readJSON text: response
        parentUUID = json.uuid
        echo "Parent project UUID: ${parentUUID}"
    }

    sbomFiles.each { sbom ->
        def pluginId = sbom.name.replaceAll(/\.json$/, '')
        def version  = pluginVersions.get(pluginId, 'unknown')

        echo "  → jenkins-plugin-${pluginId} @ ${version}"
        uploadSBOM(
            sbomFile:       sbom.path,
            projectName:    "jenkins-plugin-${pluginId}",
            projectVersion: version,
            parentUUID:     parentUUID,
            apiUrl:         apiUrl
        )
    }
}
