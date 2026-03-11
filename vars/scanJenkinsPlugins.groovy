import groovy.json.JsonSlurper

def call(Map config = [:]) {

    def pluginLimit = config.get('limit', 20)
    def workspace = pwd()

    sh """
        mkdir -p plugins sboms vulns reports
    """

    echo "Fetching Jenkins Update Center metadata..."

    sh """
        curl -s https://updates.jenkins.io/current/update-center.json \
        | sed '1d;\$d' > update-center.json
    """

    def json = new JsonSlurper().parse(new File("${workspace}/update-center.json"))
    def plugins = json.plugins.keySet().take(pluginLimit)

    echo "Scanning ${plugins.size()} plugins..."

    plugins.each { plugin ->

        echo "Downloading ${plugin}"

        sh """
        curl -sL -o plugins/${plugin}.hpi \
        https://updates.jenkins.io/latest/${plugin}.hpi
        """

        echo "Generating SBOM for ${plugin}"

        sh """
        docker run --rm \
          -v ${workspace}:/workspace \
          -w /workspace \
          anchore/syft:latest \
          dir:plugins/${plugin}.hpi \
          -o cyclonedx-json > sboms/${plugin}.json
        """

        echo "Scanning vulnerabilities for ${plugin}"

        sh """
        docker run --rm \
          -v ${workspace}:/workspace \
          -w /workspace \
          anchore/grype:latest \
          sbom:sboms/${plugin}.json \
          -o json > vulns/${plugin}.json
        """
    }

    echo "Aggregating vulnerability results..."

    sh """
    jq -s '.' vulns/*.json > reports/all-plugin-vulns.json
    """

    archiveArtifacts artifacts: 'reports/*.json'

    echo "Plugin vulnerability scan complete."
}
