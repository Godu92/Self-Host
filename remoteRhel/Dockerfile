ARG IMAGE_NAME=registry.access.redhat.com/ubi8/ubi
ARG IMAGE_TAG=latest
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

# Username and password for the user
ARG USER=user
ARG PASS=password
# Set the timezone (from: /usr/share/zoneinfo)
ARG TZ=America/New_York
# Set the subject of the self-signed SSL-certificate
ARG KEYSUBJECT=/C=NL/ST=NAme/L=Location/O=Corp/OU=MyOU/CN=jump
# Set to "true" to force encryption on TigerVNC-server over TCP/5901. Note: this breaks noVNC and some VNC clients.
ARG VNCTLS=false
# Configure timezone
RUN rm /etc/localtime && ln -s /usr/share/zoneinfo/${TZ} /etc/localtime

RUN yum -y update && yum -y install yum-utils && \
  yum-config-manager --enable rhel-8-for-x86_64-supplementary-rpms && \
  yum-config-manager --enable codeready-builder-for-rhel-8-x86_64-rpms && \
  yum -y install \
  https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm

RUN yum install --nodocs -y \
  tigervnc-server \
  xrdp \
  xorgxrdp \
  supervisor \
  nodejs \
  openbox \
  rxvt-unicode \
  sudo \
  chromium\
  nmap-ncat \
  telnet \
  tcpdump \
  openssh-clients \
  bind-utils\
  novnc \
  python3-websockify

# Create user and set password
# Add to wheel for sudo use
RUN useradd -m -s /bin/bash ${USER}
RUN echo "${USER}:${PASS}" | chpasswd
RUN usermod -aG wheel ${USER}

# Fix to be allowed to start X for xrdp when not running on a physical TTY.
RUN echo "allowed_users = anybody" >> /etc/X11/Xwrapper.config

# Fix for Chromium browser to not use CGROUP sandboxing which does not work in containers.
RUN if [ ${BROWSER} = "chromium" ] ; then sed -i 's/--auto-ssl-client-auth "/--auto-ssl-client-auth --no-sandbox "/' /usr/lib64/chromium-browser/chromium-browser.sh; fi

# Copy configuration files for Supervisord.
COPY etc/xrdp/xrdp.ini     /etc/xrdp/xrdp.ini
COPY etc/xrdp/sesman.ini   /etc/xrdp/sesman.ini
COPY etc/supervisord.conf  /etc/supervisord.conf
COPY etc/supervisord.d/*   /etc/supervisord.d/

# Set username in Supervisord configuration for TigerVNC.
RUN sed -i s/USERNAME/${USER}/g /etc/supervisord.d/vncserver.ini

# If VNCTLS is set to true, force use of encryption by TigerVNC server.
RUN if ${VNCTLS} ; then sed -i 's/-fg/-fg -SecurityTypes=VeNCrypt,TLSVnc/' /etc/supervisord.d/vncserver.ini; fi

# Create self-signed certificate for noVNC.
RUN openssl req -x509 -nodes -newkey rsa:4096 -days 3650 \
  -keyout /etc/pki/tls/certs/novnc.pem -out /etc/pki/tls/certs/novnc.pem  \
  -subj "${KEYSUBJECT}"

# Set openbox background to gray instead of solid black.
RUN echo "xsetroot -gray" >> /etc/xdg/openbox/autostart

# Run commands as non-root user to prevent having to set a lot of permissions and ownership
USER ${USER}

# Configure password for TigerVNC and start openbox on TigerVNC startup
RUN mkdir ~/.vnc && echo "${PASS}" | /usr/bin/vncpasswd -f > ~/.vnc/passwd && chmod 600 ~/.vnc/passwd
RUN echo "openbox-session" > ~/.vnc/xstartup && chmod +x ~/.vnc/xstartup

# Configure xrdp to start openbox on user login
RUN echo "exec openbox-session" > ~/startwm.sh && chmod +x ~/startwm.sh

# Start supervisord as root.
USER root

# VNC, RDP, noVNC
EXPOSE 5901
EXPOSE 3389
EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]