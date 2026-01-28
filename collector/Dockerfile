FROM rust:1.86-bookworm AS ebpf-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        clang \
        git \
        llvm \
        libelf-dev \
        pkg-config \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN rustup toolchain install nightly \
    && rustup component add rust-src --toolchain nightly
RUN cargo install bpf-linker --locked

WORKDIR /src
COPY ebpf /src

RUN cargo +nightly build -p collector-ebpf --release --target bpfel-unknown-none \
    -Z build-std=core -Z build-std-features=compiler-builtins-mem
RUN cargo +nightly build -p collector-ebpf-loader --release

FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        auditd \
        audispd-plugins \
        ca-certificates \
        python3 \
        python3-yaml \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/share/collector /etc/collector
COPY --from=ebpf-builder /src/target/release/collector-ebpf-loader /usr/local/bin/collector-ebpf-loader
COPY --from=ebpf-builder /src/target/bpfel-unknown-none/release/libcollector_ebpf.so /usr/local/share/collector/collector-ebpf.o
COPY entrypoint.sh /usr/local/bin/collector-entrypoint.sh
COPY scripts/filter_audit_logs.py /usr/local/bin/collector-audit-filter
COPY config/filtering.yaml /etc/collector/filtering.yaml
COPY config/auditd.conf /etc/audit/auditd.conf
COPY config/rules.d/harness.rules /etc/audit/rules.d/harness.rules

RUN chmod +x /usr/local/bin/collector-entrypoint.sh /usr/local/bin/collector-audit-filter

ENTRYPOINT ["/usr/local/bin/collector-entrypoint.sh"]
