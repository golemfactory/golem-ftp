# Full python toolset for ease of development
# If you need something smaller, you can use ubuntu slim or alpine without python
FROM alpine:latest

RUN apk add --no-cache curl bash
# Download official installer
RUN curl -L https://join.golem.network/as-requestor --output as-requestor.sh
RUN chmod +x as-requestor.sh

# Installer is checking if binaries in in this PATH, so we need to add it beforehand
ENV PATH="${PATH}:/root/.local/bin"

# yagna installator normally asks for user input, so we need to set some environment variables to avoid that
RUN GOLEM_ACCEPT_TOS=yes BATCH_MODE=yes YA_INSTALLER_CORE=${YAGNA_VERSION} ./as-requestor.sh




