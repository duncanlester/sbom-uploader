pipeline {
    agent any

    parameters {
        string(name: 'REPO_URL', defaultValue: 'https://github.com/apache/kafka.git', description: 'Git repository URL to checkout')
        string(name: 'REPO_REF', defaultValue: 'main', description: 'Branch or tag to checkout (e.g., main or refs/tags/4.1.0)')
    }

    environment {
        DEPENDENCY_TRACK_API_KEY = credentials('dependency-track-api-key')
        DEPENDENCY_TRACK_URL = "${DEPENDENCY_TRACK_URL ?: 'http://dtrack-apiserver:8080'}"
        PROJECT_VERSION = "1.0.0"
        SBOM_FILE = 'target/sbom.json'
        PROJECT_NAME = "java-sbom-uploader"
    }

    stages {
        stage('Checkout Source') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: params.REPO_REF]],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [],
                    userRemoteConfigs: [[
                        url: params.REPO_URL,
                        credentialsId: 'duncanlester',
                        refspec: '+refs/heads/*:refs/remotes/origin/* +refs/tags/*:refs/tags/*'
                    ]]
                ])
            }
        }
        stage('Install jq') {
            steps {
                sh 'which jq || (apt-get update && apt-get install -y jq)'
            }
        }
        stage('Generate SBOM (JSON)') {
            steps {
                script {
                    def hasPom = fileExists('pom.xml')
                    def hasGradle = fileExists('build.gradle')
                    if (hasPom) {
                        sh 'mvn org.cyclonedx:cyclonedx-maven-plugin:2.7.9:makeAggregateBom -Dcyclonedx.outputFormat=json -Dcyclonedx.outputName=sbom'
                    } else if (hasGradle) {
                        writeFile file: 'cyclonedx.init.gradle', text: '''
                        initscript {
                            repositories {
                                mavenCentral()
                            }
                            dependencies {
                                classpath 'org.cyclonedx:cyclonedx-gradle-plugin:1.7.5'
                            }
                        }
                        rootProject {
                            apply plugin: 'org.cyclonedx.bom'
                        }
                        '''
                        sh './gradlew -I cyclonedx.init.gradle cyclonedxBom -Dcyclonedx.outputFormat=json'
                        sh 'cp build/reports/bom.json target/sbom.json'
                    } else {
                        error 'No pom.xml or build.gradle found in the workspace.'
                    }
                }
            }
        }
        stage('Create Dependency Track Project') {
            steps {
                withEnv(["DT_API_KEY=${DEPENDENCY_TRACK_API_KEY}"]) {
                    sh """
                        curl -X PUT "$DEPENDENCY_TRACK_URL/api/v1/project" \
                        -H "Content-Type: application/json" \
                        -H "X-Api-Key: $DT_API_KEY" \
                        -d '{
                            "name": "${PROJECT_NAME}",
                            "version": "${PROJECT_VERSION}",
                            "active": true
                        }'
                    """
                }
            }
        }
        stage('Get Dependency Track Project UUID') {
            steps {
                withEnv(["DT_API_KEY=${DEPENDENCY_TRACK_API_KEY}"]) {
                    script {
                        def response = sh(
                            script: """
                                curl -s -H "X-Api-Key: $DT_API_KEY" "$DEPENDENCY_TRACK_URL/api/v1/project?name=${PROJECT_NAME}&version=${PROJECT_VERSION}"
                            """,
                            returnStdout: true
                        )
                        def uuid = sh(
                            script: "echo '$response' | jq -r '.[0].uuid'",
                            returnStdout: true
                        ).trim()
                        env.DT_PROJECT_UUID = uuid
                    }
                }
            }
        }
        stage('Upload SBOM to Dependency Track') {
            steps {
                withEnv(["DT_API_KEY=${DEPENDENCY_TRACK_API_KEY}"]) {
                    sh 'ls -l target/sbom.json'
                    sh '''
                        curl -X POST "$DEPENDENCY_TRACK_URL/api/v1/bom" \
                        -H "X-Api-Key: $DT_API_KEY" \
                        -F "projectName=${PROJECT_NAME}" \
                        -F "projectVersion=${PROJECT_VERSION}" \
                        -F "bom=@target/sbom.json"
                    '''
                }
            }
        }
        stage('Show Dependency Track Link') {
            steps {
                echo "View your SBOM and vulnerabilities at: ${DEPENDENCY_TRACK_URL}/project/${env.DT_PROJECT_UUID}"
            }
        }
        stage('Debug Workspace') {
            steps {
                sh 'ls -al'
                sh 'find . -name pom.xml'
            }
        }
    }
}
