FROM ghcr.io/cdxgen/cdxgen:latest

ARG GRADLE_VERSION=latest

USER root

RUN source "/opt/.sdkman/bin/sdkman-init.sh" && \
    sdk install gradle ${GRADLE_VERSION} && \
    sdk default gradle ${GRADLE_VERSION} && \
    sdk list gradle | grep installed && \
    gradle --version

USER cyclonedx
