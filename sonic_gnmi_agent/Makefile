
TOP_DIR := $(abspath ../../..)
BLDENV := bookworm
CONFIGURED_ARCH := amd64
include $(TOP_DIR)/rules/sonic-dash-api.mk
include $(TOP_DIR)/rules/protobuf.mk
TARGET_DIR := $(TOP_DIR)/target
SRCS := $(shell find src/ -type f)
ifeq ($(BLDENV),bookworm)
  DEBS := $(PROTOBUF) $(PROTOBUF_LITE) $(PYTHON3_PROTOBUF)
endif
DEBS += $(LIB_SONIC_DASH_API)
#protobuf is builtin in bookworm. N

all: $(TARGET_DIR)/docker-sonic-gnmi-agent.gz

$(TARGET_DIR)/docker-sonic-gnmi-agent.gz: $(TARGET_DIR)/docker-sonic-gnmi.gz $(SRCS) docker/Dockerfile $(addprefix debs/,$(DEBS))
	docker load -i $(TARGET_DIR)/docker-sonic-gnmi.gz && \
		docker build --build-arg http_proxy=$(http_proxy) --build-arg https_proxy=$(https_proxy) --build-arg no_proxy=$(no_proxy) -t sonic-gnmi-agent:latest -f docker/Dockerfile . && \
		docker save -o $(TARGET_DIR)/docker-sonic-gnmi-agent.gz sonic-gnmi-agent:latest && \
		docker image rm -f docker-sonic-gnmi && \
		docker image rm -f sonic-gnmi-agent

debs/%: $(TARGET_DIR)/debs/$(BLDENV)/%
	@mkdir -p debs
	@cp $< $@

clean:
	rm -f $(TARGET_DIR)/docker-sonic-gnmi-agent.gz
	rm -f docker/Dockerfile
	rm -rf debs

docker/Dockerfile: docker/Dockerfile.j2
	$(eval export docker_sonic_gnmi_agent_debs=$(DEBS))
	j2 docker/Dockerfile.j2 > docker/Dockerfile

