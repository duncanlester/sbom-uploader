def call(String imageName, String outputFile, List grypeFlags = []) {

    def flags = grypeFlags ? grypeFlags.join(' ') : ''

    sh """
        set -e
        echo "Pulling image to ensure it exists locally..."
        docker pull ${imageName} || true

        echo "Running Grype vulnerability scan in container..."

        docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v \$PWD:/work \
            -w /work \
            anchore/grype:latest \
            ${imageName} -o cyclonedx-json ${flags} > ${outputFile}

        echo "Grype report generated: \$(wc -c < ${outputFile}) bytes"
    """
}
