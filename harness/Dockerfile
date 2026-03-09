FROM ubuntu:22.04@sha256:c7eb020043d8fc2ae0793fb35a37bff1cf33f156d4d4b12ccc7f3ef8706c38b1

LABEL org.opencontainers.image.title="lux-harness" \
      org.opencontainers.image.source="https://github.com/scottmaran/lux" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        openssh-client \
        python3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1002 -s /bin/bash harness \
    && mkdir -p /harness/keys /logs /work \
    && chown -R harness:harness /harness/keys /work \
    && chmod 700 /harness/keys

COPY harness.py /usr/local/bin/harness.py
COPY entrypoint.sh /usr/local/bin/harness-entrypoint.sh
RUN chmod +x /usr/local/bin/harness-entrypoint.sh

USER harness

ENTRYPOINT ["/usr/local/bin/harness-entrypoint.sh"]
