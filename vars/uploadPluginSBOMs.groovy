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
    def sbomGlob    = config.sbomGlob    ?: 'sboms/*.json'

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

    sbomFiles.each { sbom ->
        def pluginId = sbom.name.replaceAll(/\.json$/, '')
        def version  = pluginVersions.get(pluginId, 'unknown')

        echo "  → jenkins-plugin-${pluginId} @ ${version}"
        uploadSBOM(
            sbomFile:       sbom.path,
            projectName:    "jenkins-plugin-${pluginId}",
            projectVersion: version
        )
    }
}
