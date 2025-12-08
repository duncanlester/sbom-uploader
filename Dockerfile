FROM jenkins/jenkins:lts
USER root
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs maven && \
    apt-get install -y docker.io && \
    usermod -aG docker jenkins
USER jenkins
RUN jenkins-plugin-cli --plugins docker-plugin:1.26 docker-workflow:1.28
