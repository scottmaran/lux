FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        openssh-server \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @openai/codex \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1001 -s /bin/bash agent \
    && passwd -d agent \
    && mkdir -p /home/agent/.ssh /home/agent/.codex /work /logs /var/run/sshd /config \
    && chown -R agent:agent /home/agent /work \
    && chmod 700 /home/agent/.ssh \
    && chown root:root /logs \
    && chmod 755 /logs

COPY sshd_config /etc/ssh/sshd_config
COPY entrypoint.sh /usr/local/bin/agent-entrypoint.sh
RUN chmod +x /usr/local/bin/agent-entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
