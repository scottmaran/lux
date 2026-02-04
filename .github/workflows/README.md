# Release Workflow

This directory contains the manual release workflow for Lasso.

## How it works

- The workflow is **manual-only** (`workflow_dispatch`).
- It builds the Rust CLI bundles for multiple OS/arch targets.
- Optionally pushes multi-arch Docker images to GHCR.
- Optionally publishes a GitHub Release and uploads the bundles as assets.

## How to run it (GitHub UI)

1) Go to the repo → **Actions** tab.
2) Select the **release** workflow.
3) Click **Run workflow**.
4) Fill in inputs:
   - `version` (e.g., `v0.1.0`)
   - `push_images` (`true`/`false`)
   - `publish_release` (`true`/`false`)

## Where the release goes

If `publish_release` is `true`, the workflow creates a GitHub Release at:

```
https://github.com/<owner>/<repo>/releases/tag/vX.Y.Z
```

The release assets include the CLI bundle tarballs + SHA256 checksums.

## Build assumptions / dependencies

- Rust toolchain is installed via `dtolnay/rust-toolchain@stable`.
- Cross-compilation targets are used for linux + macOS bundles.
- For linux/arm64, the workflow installs `gcc-aarch64-linux-gnu`.
- Docker Buildx is used for multi-arch image builds.
- GHCR auth uses `GITHUB_TOKEN` with `packages: write` permissions.

## Notes

- Image tags are pushed as both `vX.Y.Z` and `X.Y.Z`.
- The release bundle includes:
  - `lasso` binary
  - `compose.yml`, `compose.codex.yml`, `compose.ui.yml`
  - `config/default.yaml`
  - `docs/guide/` (user docs)
  - `README.md`, `LICENSE`, `VERSION`
  - SHA256 checksum
