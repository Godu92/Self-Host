ARG IMAGE_NAME=debian
ARG IMAGE_TAG=jessie
FROM ${IMAGE_NAME}:${IMAGE_TAG}

## Add these lines to dockerfiles for consistent labeling
ARG MAINTAINER=""
ARG APP_NAME=""
ARG DESC=""
ARG APP_VERSION=""
ARG BUILD_DATE=""
ARG DOCS=""
ARG LICENSES=""
ARG REF_NAME=${IMAGE_NAME}:${IMAGE_TAG}
ARG REVISION=""
ARG SOURCE=""
ARG URL=""
ARG VENDOR=""

LABEL \
  org.opencontainers.image.authors=${MAINTAINER} \
  org.opencontainers.image.created=${BUILD_DATE} \
  org.opencontainers.image.description=${DESC} \
  org.opencontainers.image.documentation=${DOCS} \
  org.opencontainers.image.licenses=${LICENSES} \
  org.opencontainers.image.ref.name=${REF_NAME} \
  org.opencontainers.image.revision=${REVISION} \
  org.opencontainers.image.source=${SOURCE} \
  org.opencontainers.image.title=${APP_NAME} \
  org.opencontainers.image.url=${URL} \
  org.opencontainers.image.vendor=${VENDOR} \
  org.opencontainers.image.version=${APP_VERSION}

# Source working/installation directory
ENV INSTALL=/usr/local/src
WORKDIR ${INSTALL}
RUN echo '[ ! -z "${TERM}" -a -r /etc/motd ] && cat /etc/issue && cat /etc/motd' \
  >> /etc/bash.bashrc \
  ; echo "\
  ===================================================================\n\
  = ${APP_NAME} Docker container : ${APP_VERSION}                       =\n\
  ===================================================================\n\
  \n\
  ${APP_NAME}: ${DESC}\n\
  (c) ${MAINTAINER} - ${BUILD_DATE}\n\
  \n\
  Source directory is ${INSTALL}\n"\
  > /etc/motd

