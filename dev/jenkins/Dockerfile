FROM jenkins/jenkins:2.528.1-jdk21
USER root

# Copy the system CA bundle
# COPY certs/ca-bundle.crt /tmp/ca-bundle.crt

# # Install tools
# RUN apt-get update && \
#     apt-get install -y ca-certificates curl && \
#     apt-get clean && rm -rf /var/lib/apt/lists/*

# # Split the bundle and import each certificate into Java truststore
# RUN csplit -sz -f /tmp/cert- /tmp/ca-bundle.crt '/-----BEGIN CERTIFICATE-----/' '{*}' && \
#     for cert in /tmp/cert-*; do \
#     if [ -s "$cert" ] && grep -q "BEGIN CERTIFICATE" "$cert"; then \
#     keytool -import -trustcacerts -noprompt \
#     -alias "cert-$(basename $cert)" \
#     -file "$cert" \
#     -cacerts \
#     -storepass changeit 2>/dev/null || true; \
#     fi \
#     done && \
#     rm -f /tmp/cert-* /tmp/ca-bundle.crt

# # List imported certs to verify
# RUN keytool -list -cacerts -storepass changeit | grep -i "cert-" | head -20

USER jenkins

# ENV JAVA_OPTS="-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts -Djavax.net.ssl.trustStorePassword=changeit"
RUN jenkins-plugin-cli --plugins "blueocean pipeline-graph-view docker-workflow json-path-api"
