FROM ubuntu:22.04

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
COPY asciinema.py /usr/local/bin/asciinema.py
COPY entrypoint.sh /usr/local/bin/harness-entrypoint.sh
RUN chmod +x /usr/local/bin/harness-entrypoint.sh

USER harness

ENTRYPOINT ["/usr/local/bin/harness-entrypoint.sh"]
