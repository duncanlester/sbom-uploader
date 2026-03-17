#!/usr/bin/env groovy

/**
 * Query a remote Jenkins instance for its installed plugins and version.
 *
 * Writes plugins-list.txt (<shortName> <version> per line) and
 * jenkins-version.txt to the workspace.
 *
 * @param jenkinsUrl     Base URL of the target Jenkins instance (required)
 * @param credentialsId  Jenkins credentials ID (username + API token) for the target instance (required)
 * @param pluginsFile    Output path for the plugin list (default: 'plugins-list.txt')
 * @param versionFile    Output path for the Jenkins version (default: 'jenkins-version.txt')
 */
def call(Map config = [:]) {
    def jenkinsUrl    = config.jenkinsUrl    ?: error('listJenkinsPlugins: jenkinsUrl is required')
    def credentialsId = config.credentialsId ?: error('listJenkinsPlugins: credentialsId is required')
    def pluginsFile   = config.pluginsFile   ?: 'plugins-list.txt'
    def versionFile   = config.versionFile   ?: 'jenkins-version.txt'

    withCredentials([usernamePassword(
        credentialsId: credentialsId,
        usernameVariable: 'JENKINS_USER',
        passwordVariable: 'JENKINS_TOKEN'
    )]) {
        def response = sh(script: """
            curl -fsSL -u "\${JENKINS_USER}:\${JENKINS_TOKEN}" \
                "${jenkinsUrl}/pluginManager/api/json?depth=1"
        """, returnStdout: true).trim()

        def data = readJSON text: response
        def lines = data.plugins.collect { p -> "${p.shortName} ${p.version}" }.sort()
        writeFile file: pluginsFile, text: lines.join('\n') + '\n'
        echo "Found ${lines.size()} installed plugins"

        def jenkinsVersion = sh(script: """
            curl -sI "${jenkinsUrl}/" | grep -i 'X-Jenkins:' | awk '{print \$2}' | tr -d '\\r'
        """, returnStdout: true).trim()
        writeFile file: versionFile, text: jenkinsVersion
        echo "Jenkins version: ${jenkinsVersion}"
    }
}
