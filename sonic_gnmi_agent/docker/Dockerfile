FROM docker-sonic-gnmi
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update

COPY \
    debs/libdashapi_1.0.0_amd64.deb \
    /debs/

RUN dpkg_apt() { [ -f $1 ] && { dpkg -i $1 || apt-get -y install -f; } || return 1; }; \
    dpkg_apt /debs/libdashapi_1.0.0_amd64.deb 

RUN apt-get install -y python3-protobuf

RUN apt-get clean -y      && \
    apt-get autoclean -   && \
    apt-get autoremove -y && \
    rm -rf /debs

RUN mkdir -p /usr/lib/python3/dist-packages/gnmi_agent
RUN mkdir -p /sonic/templates
COPY ["src/__init__.py", "src/proto_utils.py", "src/go_gnmi_utils.py", "/usr/lib/python3/dist-packages/gnmi_agent/"]
COPY ["src/gnmi_client.py", "/usr/sbin"]
COPY ["templates/*", "/sonic/templates/"]
RUN chmod a+x /usr/sbin/gnmi_client.py
RUN rm /etc/supervisor/conf.d/supervisord.conf

ENTRYPOINT ["/bin/bash"]
