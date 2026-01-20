FROM rust:1.78-bookworm AS ebpf-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        clang \
        llvm \
        libelf-dev \
        pkg-config \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN rustup toolchain install nightly \
    && rustup target add bpfel-unknown-none --toolchain nightly
RUN cargo install bpf-linker

WORKDIR /src
COPY ebpf /src

RUN cargo +nightly build -p collector-ebpf --release --target bpfel-unknown-none
RUN cargo +nightly build -p collector-ebpf-loader --release

FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        auditd \
        audispd-plugins \
        ca-certificates \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/share/collector
COPY --from=ebpf-builder /src/target/release/collector-ebpf-loader /usr/local/bin/collector-ebpf-loader
COPY --from=ebpf-builder /src/target/bpfel-unknown-none/release/collector-ebpf /usr/local/share/collector/collector-ebpf.o
COPY entrypoint.sh /usr/local/bin/collector-entrypoint.sh
COPY config/auditd.conf /etc/audit/auditd.conf
COPY config/rules.d/harness.rules /etc/audit/rules.d/harness.rules

RUN chmod +x /usr/local/bin/collector-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/collector-entrypoint.sh"]
