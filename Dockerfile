FROM jenkins/jenkins:lts
USER root

RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs maven && \
    apt-get install -y docker.io && \
    # Install the docker compose v2 CLI plugin so 'docker compose' works inside the container
    mkdir -p /usr/local/lib/docker/cli-plugins && \
    COMPOSE_VERSION=$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest \
    | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/') && \
    curl -fsSL "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose && \
    curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin && \
    usermod -aG docker jenkins

RUN jenkins-plugin-cli --plugins docker-plugin docker-workflow
USER jenkins
