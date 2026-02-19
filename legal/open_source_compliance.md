# Open Source Compliance and Source Availability
Layer: Contract

This document defines how Lux communicates licensing and corresponding source
for distributed artifacts in the open-source distribution.

## License

Lux is licensed under `AGPL-3.0-only`.

Primary license text:

- `LICENSE`

## Distributed Artifacts

Lux distribution currently includes:

- CLI release bundles,
- OCI container images for `agent`, `harness`, `collector`, and `ui`.

## Corresponding Source Location

Authoritative source repository:

- `https://github.com/scottmaran/lux`

Tag mapping policy:

- For a released artifact tagged `vX.Y.Z`, corresponding source is the same git
  tag `vX.Y.Z` in the repository.
- For development snapshots built from branch commits, corresponding source is
  the referenced commit in the same repository.

## Image Metadata Pointers

Lux runtime image Dockerfiles include OCI metadata labels that point to:

- source repository (`org.opencontainers.image.source`),
- license identifier (`org.opencontainers.image.licenses`).

These labels are intended to make source/license discovery straightforward from
the pulled image metadata.

## Related

- `README.md`
- `.github/workflows/release.yml`
