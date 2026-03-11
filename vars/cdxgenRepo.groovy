#!/usr/bin/env groovy

/**
 * Generate SBOM for any source code repository using cdxgen (polyglot support)
 *
 * @param outputFile The output file path for the SBOM (e.g., 'sbom.json')
 * @param includeJavaSetup Set to true if repo contains Java/Maven/Gradle (default: false)
 * @param mavenArgs Optional Maven arguments (e.g., for snapshot repos or profiles)
 * @param javaVersion Java version to use (e.g., '11', '17', '21'). Uses latest if empty (default: '')
 * eg
    cdxgenRepo(env.SBOM_FILE, true, '', '11')

    Pin to specific version for stability
    cdxgenRepo(env.SBOM_FILE, true, '', '11', 'v12')

    Use latest main image
    cdxgenRepo(env.SBOM_FILE, true)

    Use specific version of main image
    cdxgenRepo(env.SBOM_FILE, true, '', '', 'v11.5.6')
 */
def call(String outputFile, Boolean includeJavaSetup = false, String mavenArgs = '', String javaVersion = '', String cdxgenVersion = 'latest') {
    sh "mkdir -p ${env.WORKSPACE}/tmp"

    def imageName = javaVersion ? "ghcr.io/cyclonedx/cdxgen-java${javaVersion}:${cdxgenVersion}" : "ghcr.io/cyclonedx/cdxgen:${cdxgenVersion}"
    def userId = sh(script: 'id -u', returnStdout: true).trim()
    def groupId = sh(script: 'id -g', returnStdout: true).trim()

    if (includeJavaSetup) {
        sh """
            docker run --rm --network=host \
                -u ${userId}:${groupId} \
                -v ${env.WORKSPACE}:${env.WORKSPACE} \
                -v ${env.WORKSPACE}/tmp:/tmp \
                --ulimit nofile=65536:65536 \
                -w ${env.WORKSPACE} \
                -e TMPDIR=${env.WORKSPACE}/tmp \
                -e TMP=${env.WORKSPACE}/tmp \
                -e TEMP=${env.WORKSPACE}/tmp \
                -e MAVEN_OPTS='-Dmaven.repo.local=${env.WORKSPACE}/.m2/repository -Duser.home=${env.WORKSPACE}' \
                -e MVN_ARGS='${mavenArgs}' \
                ${imageName} \
                -r -o ${outputFile} ${env.WORKSPACE}
        """
    } else {
        sh """
            docker run --rm --network=host \
                -u ${userId}:${groupId} \
                -v ${env.WORKSPACE}:${env.WORKSPACE} \
                -v ${env.WORKSPACE}/tmp:/tmp \
                -w ${env.WORKSPACE} \
                -e TMPDIR=${env.WORKSPACE}/tmp \
                -e TMP=${env.WORKSPACE}/tmp \
                -e TEMP=${env.WORKSPACE}/tmp \
                ${imageName} \
                -r -o ${outputFile} ${env.WORKSPACE}
        """
    }
}
