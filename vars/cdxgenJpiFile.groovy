#!/usr/bin/env groovy

/**
 * Generate a CycloneDX SBOM for a single Jenkins plugin (.jpi / .hpi) file
 * using cdxgen with Java type analysis.
 *
 * cdxgen reads META-INF/maven/<groupId>/<artifactId>/pom.properties from every
 * embedded JAR, emitting exact pkg:maven/groupId/artifactId@version PURLs that
 * Dependency-Track can match against NVD / OSV.
 *
 * @param pluginFile  Absolute path to the .jpi / .hpi file to scan
 * @param outputFile  Absolute path to write the CycloneDX JSON SBOM to
 * @param cdxgenVersion  cdxgen image tag (default: 'latest')
 */
def call(String pluginFile, String outputFile, String cdxgenVersion = 'latest') {
    def pluginDir  = pluginFile.substring(0, pluginFile.lastIndexOf('/'))
    def pluginName = pluginFile.substring(pluginFile.lastIndexOf('/') + 1)
    def outputDir  = outputFile.substring(0, outputFile.lastIndexOf('/'))
    def outputName = outputFile.substring(outputFile.lastIndexOf('/') + 1)

    def userId  = sh(script: 'id -u', returnStdout: true).trim()
    def groupId = sh(script: 'id -g', returnStdout: true).trim()

    sh """
        mkdir -p "${outputDir}"
        docker run --rm \\
            -u ${userId}:${groupId} \\
            -v "${pluginDir}":/plugins:ro \
            -v "${outputDir}":/sboms \
            ghcr.io/cyclonedx/cdxgen:${cdxgenVersion} \
            -t java \
            --no-recurse \
            -o "/sboms/${outputName}" \
            "/plugins/${pluginName}"
    """
}
