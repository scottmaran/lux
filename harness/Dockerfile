FROM ubuntu:22.04@sha256:c7eb020043d8fc2ae0793fb35a37bff1cf33f156d4d4b12ccc7f3ef8706c38b1

ENV DEBIAN_FRONTEND=noninteractive
ARG CA_CERTS_VERSION=20240203~22.04.1
ARG CURL_VERSION=7.81.0-1ubuntu1.21
ARG OPENSSH_CLIENT_VERSION=1:8.9p1-3ubuntu0.13
ARG PYTHON3_VERSION=3.10.6-1~22.04.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates=${CA_CERTS_VERSION} \
        curl=${CURL_VERSION} \
        openssh-client=${OPENSSH_CLIENT_VERSION} \
        python3=${PYTHON3_VERSION} \
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
