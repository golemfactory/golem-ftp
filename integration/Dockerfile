# Full python toolset for ease of development
# If you need something smaller, you can use ubuntu slim or alpine without python
FROM alpine:latest

RUN apk add --no-cache curl bash iproute2 iputils
# Download official installer
RUN curl -L https://join.golem.network/as-requestor --output as-requestor.sh
RUN chmod +x as-requestor.sh

# Installer is checking if binaries in in this PATH, so we need to add it beforehand
ENV PATH="${PATH}:/root/.local/bin"

# yagna installator normally asks for user input, so we need to set some environment variables to avoid that
RUN GOLEM_ACCEPT_TOS=yes BATCH_MODE=yes YA_INSTALLER_CORE=${YAGNA_VERSION} ./as-requestor.sh

RUN wget https://github.com/golemfactory/ya-relay/releases/download/v0.3.0/ya-relay-server && chmod +x ya-relay-server && mv ya-relay-server /usr/local/bin/
RUN wget https://github.com/golemfactory/ya-service-bus/releases/download/v0.7.2/ya-sb-router-linux-v0.7.2.tar.gz && tar -xvf ya-sb-router-linux-v0.7.2.tar.gz && mv ya-sb-router-linux-v0.7.2/ya-sb-router /usr/local/bin/



