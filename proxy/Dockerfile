FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        squid \
        python3 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/spool/squid /var/log/squid /var/run/squid

COPY squid.conf /etc/squid/squid.conf
COPY parse_squid_access.py /usr/local/bin/parse_squid_access.py
COPY proxy_auth_helper.py /usr/local/bin/proxy_auth_helper.py
COPY entrypoint.sh /usr/local/bin/proxy-entrypoint.sh
RUN chmod +x /usr/local/bin/parse_squid_access.py /usr/local/bin/proxy_auth_helper.py /usr/local/bin/proxy-entrypoint.sh

EXPOSE 3128
ENTRYPOINT ["/usr/local/bin/proxy-entrypoint.sh"]
