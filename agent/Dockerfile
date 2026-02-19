FROM ubuntu:22.04@sha256:c7eb020043d8fc2ae0793fb35a37bff1cf33f156d4d4b12ccc7f3ef8706c38b1

LABEL org.opencontainers.image.title="lux-agent" \
      org.opencontainers.image.source="https://github.com/scottmaran/lux" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV DEBIAN_FRONTEND=noninteractive
ARG CA_CERTS_VERSION=20240203~22.04.1
ARG CURL_VERSION=7.81.0-1ubuntu1.21
ARG GIT_VERSION=1:2.34.1-1ubuntu1.15
ARG OPENSSH_SERVER_VERSION=1:8.9p1-3ubuntu0.13
ARG NODE_VERSION=20.11.1
ARG NODE_SHA256_ARM64=e34ab2fc2726b4abd896bcbff0250e9b2da737cbd9d24267518a802ed0606f3b
ARG NODE_SHA256_X64=bf3a779bef19452da90fb88358ec2c57e0d2f882839b20dc6afc297b6aafc0d7
ARG CODEX_VERSION=0.94.0
ARG CLAUDE_CODE_VERSION=2.1.39

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates=${CA_CERTS_VERSION} \
        curl=${CURL_VERSION} \
        git=${GIT_VERSION} \
        openssh-server=${OPENSSH_SERVER_VERSION} \
    && rm -rf /var/lib/apt/lists/*

RUN ARCH="$(dpkg --print-architecture)" \
    && case "$ARCH" in \
        amd64) NODE_ARCH="x64"; NODE_SHA="${NODE_SHA256_X64}" ;; \
        arm64) NODE_ARCH="arm64"; NODE_SHA="${NODE_SHA256_ARM64}" ;; \
        *) echo "Unsupported architecture: ${ARCH}" >&2; exit 1 ;; \
    esac \
    && NODE_TAR="node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.gz" \
    && curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/${NODE_TAR}" \
    && echo "${NODE_SHA}  ${NODE_TAR}" | sha256sum -c - \
    && tar -xzf "${NODE_TAR}" -C /usr/local --strip-components=1 \
    && rm "${NODE_TAR}"

RUN npm install -g @openai/codex@${CODEX_VERSION} @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

RUN useradd -m -u 1001 -s /bin/bash agent \
    && passwd -d agent \
    && mkdir -p /home/agent/.ssh /home/agent/.codex /home/agent/.claude /home/agent/.config/claude-code /work /logs /var/run/sshd /config \
    && chown -R agent:agent /home/agent /work \
    && chmod 700 /home/agent/.ssh \
    && chown 1002:1002 /config \
    && chmod 700 /config \
    && chown root:root /logs \
    && chmod 755 /logs

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /usr/local/bin/agent-entrypoint.sh
RUN chmod +x /usr/local/bin/agent-entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
