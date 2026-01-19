FROM aquasec/tracee:latest AS tracee

FROM ubuntu:22.04

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    auditd \
    ca-certificates \
    util-linux \
  && rm -rf /var/lib/apt/lists/*

COPY --from=tracee /tracee/tracee /usr/local/bin/tracee
COPY entrypoint.sh /usr/local/bin/collector-entrypoint.sh
COPY config/auditd.conf /etc/audit/auditd.conf
COPY config/rules.d/harness.rules /etc/audit/rules.d/harness.rules

RUN chmod +x /usr/local/bin/collector-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/collector-entrypoint.sh"]
