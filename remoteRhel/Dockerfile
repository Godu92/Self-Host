FROM registry.access.redhat.com/ubi8-minimal

ADD ./jump-rhel/rpm/epel-release-latest-8.noarch.rpm .
# RUN subscription-manager repos --enable codeready-builder-for-rhel-8-$(arch)-rpms
# RUN microdnf config-manager --set-enabled crb
# RUN crb enable
RUN rpm -i epel-release-latest-8.noarch.rpm
# RUN rpm -ivh https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
RUN microdnf install openvpn