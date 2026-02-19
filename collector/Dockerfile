FROM rust:1.88.0-bookworm@sha256:af306cfa71d987911a781c37b59d7d67d934f49684058f96cf72079c3626bfe0 AS ebpf-builder

ENV DEBIAN_FRONTEND=noninteractive
ARG CLANG_VERSION=1:14.0-55.7~deb12u1
ARG GIT_VERSION=1:2.39.5-0+deb12u3
ARG LLVM_VERSION=1:14.0-55.7~deb12u1
ARG LIBELF_DEV_VERSION=0.188-2.1
ARG PKG_CONFIG_VERSION=1.8.1-1
ARG ZLIB1G_DEV_VERSION=1:1.2.13.dfsg-1
ARG RUST_NIGHTLY=nightly-2025-07-15
ARG BPF_LINKER_VERSION=0.10.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        clang=${CLANG_VERSION} \
        git=${GIT_VERSION} \
        llvm=${LLVM_VERSION} \
        libelf-dev=${LIBELF_DEV_VERSION} \
        pkg-config=${PKG_CONFIG_VERSION} \
        zlib1g-dev=${ZLIB1G_DEV_VERSION} \
    && rm -rf /var/lib/apt/lists/*

RUN rustup toolchain install ${RUST_NIGHTLY} --profile minimal -c rust-src
RUN cargo install bpf-linker --version ${BPF_LINKER_VERSION} --locked

WORKDIR /src
COPY ebpf /src

RUN cargo +${RUST_NIGHTLY} build -p collector-ebpf --release --locked --target bpfel-unknown-none \
    -Z build-std=core -Z build-std-features=compiler-builtins-mem
RUN cargo build -p collector-ebpf-loader --release --locked

FROM ubuntu:22.04@sha256:c7eb020043d8fc2ae0793fb35a37bff1cf33f156d4d4b12ccc7f3ef8706c38b1

LABEL org.opencontainers.image.title="lux-collector" \
      org.opencontainers.image.source="https://github.com/scottmaran/lux" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        auditd=1:3.0.7-1build1 \
        audispd-plugins=1:3.0.7-1build1 \
        ca-certificates=20240203~22.04.1 \
        python3=3.10.6-1~22.04.1 \
        python3-yaml=5.4.1-1ubuntu1 \
        util-linux=2.37.2-4ubuntu3.4 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/local/share/collector /etc/collector
COPY --from=ebpf-builder /src/target/release/collector-ebpf-loader /usr/local/bin/collector-ebpf-loader
COPY --from=ebpf-builder /src/target/bpfel-unknown-none/release/libcollector_ebpf.so /usr/local/share/collector/collector-ebpf.o
COPY entrypoint.sh /usr/local/bin/collector-entrypoint.sh
COPY scripts/filter_audit_logs.py /usr/local/bin/collector-audit-filter
COPY scripts/filter_ebpf_logs.py /usr/local/bin/collector-ebpf-filter
COPY scripts/summarize_ebpf_logs.py /usr/local/bin/collector-ebpf-summary
COPY scripts/merge_filtered_logs.py /usr/local/bin/collector-merge-filtered
COPY config/audit_filtering.yaml /etc/collector/audit_filtering.yaml
COPY config/ebpf_filtering.yaml /etc/collector/ebpf_filtering.yaml
COPY config/ebpf_summary.yaml /etc/collector/ebpf_summary.yaml
COPY config/merge_filtering.yaml /etc/collector/merge_filtering.yaml
COPY config/auditd.conf /etc/audit/auditd.conf
COPY config/rules.d/harness.rules /etc/audit/rules.d/harness.rules

RUN chmod +x /usr/local/bin/collector-entrypoint.sh \
    /usr/local/bin/collector-audit-filter \
    /usr/local/bin/collector-ebpf-filter \
    /usr/local/bin/collector-ebpf-summary \
    /usr/local/bin/collector-merge-filtered

ENTRYPOINT ["/usr/local/bin/collector-entrypoint.sh"]
