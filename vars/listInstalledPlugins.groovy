#!/usr/bin/env groovy

/**
 * Download jenkins-cli.jar from the target Jenkins and use it to produce
 * plugins-list.txt containing all installed plugin IDs and versions.
 *
 * @param jenkinsUrl  Base URL of the Jenkins to query (default: env.TARGET_JENKINS_URL)
 */
def call(Map config = [:]) {
    def jenkinsUrl = config.jenkinsUrl ?: env.TARGET_JENKINS_URL

    sh """
        set -euo pipefail
        curl -fsSL '${jenkinsUrl}/jnlpJars/jenkins-cli.jar' -o jenkins-cli.jar

        java -jar jenkins-cli.jar \
            -s '${jenkinsUrl}' \
            list-plugins > plugins-list.txt

        echo "Found \$(wc -l < plugins-list.txt | tr -d ' ') installed plugins"
    """
}
