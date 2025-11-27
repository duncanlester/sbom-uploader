// Jenkinsfile
pipeline {
    agent {
        docker {
            image 'image:node:18'
            args '--network dtrack-network'
        }
    }

    parameters {
        string(name: 'REPO_URL', defaultValue: 'https://github.com/duncanlester/testcafe-api.git', description: 'Git repository URL to checkout')
        string(name: 'REPO_BRANCH', defaultValue: 'main', description: 'Branch to checkout')
        string(name: 'REPO_CREDENTIALS_ID', defaultValue: '', description: 'Credentials ID for private repos (optional)')
        string(name: 'PROJECT_NAME', defaultValue: 'sbom-uploader', description: 'Project name for Dependency Track')
    }

    environment {
        DEPENDENCY_TRACK_API_KEY = credentials('dependency-track-api-key')
        DEPENDENCY_TRACK_URL = "${DEPENDENCY_TRACK_URL ?: 'http://dtrack-apiserver:8080'}"
        PROJECT_VERSION = "1.0.0"
        SBOM_FILE = 'sbom.json'
    }

    stages {
        stage('Checkout Source') {
            steps {
                script {
                    if (params.REPO_CREDENTIALS_ID) {
                        git url: params.REPO_URL, branch: params.REPO_BRANCH, credentialsId: params.REPO_CREDENTIALS_ID
                    } else {
                        git url: params.REPO_URL, branch: params.REPO_BRANCH
                    }
                }
            }
        }
        stage('Install CycloneDX') {
            steps {
                sh 'npm install -g @cyclonedx/bom'
            }
        }
        stage('Generate SBOM') {
            steps {
                sh "cyclonedx-bom -o ${env.SBOM_FILE} -f json"
            }
        }
        stage('Upload SBOM to Dependency Track') {
            steps {
                sh '''
                curl -X POST -H "Content-Type: application/xml" \
                     -H "X-Api-Key: $DEPENDENCY_TRACK_API_KEY" \
                     --data-binary "@${SBOM_FILE}" \
                     $DEPENDENCY_TRACK_URL
                '''
            }
        }
        stage('Show Dependency Track Link') {
            steps {
                echo "View your SBOM and vulnerabilities in the Dependency Track UI."
            }
        }
    }
}
