# Release Workflow Consistency + Quick-Release Support

## Context
- We want a reliable way to cut a quick “test release” from a feature branch without bumping `main`.
- The current `.github/workflows/release.yml` has hard failures and correctness gaps (tag/branch mismatch, missing files, weak safety rails).

## Goals
- `release.yml` is consistent with the current repo layout (no missing file references).
- Running the workflow from any branch produces a tag pointing at the exact commit that produced the artifacts/images.
- “Publish release” is safe: no silent missing assets, no accidental “latest” test release, no partial side effects.
- Fail fast with clear errors for invalid inputs (version mismatch, tag exists, etc.).
- Workflow docs and user docs accurately match what is shipped.

## Non-Goals (For This Pass)
- Changing the Linux binary compatibility strategy (glibc floor, musl) unless needed to unblock the workflow.
- Changing the release bundle format (keep tarball layout and installer expectations).

## Current Issues (Audit Findings)
- `release.yml` copies `compose.codex.yml` into bundles, but `compose.codex.yml` does not exist in the repo.
- GitHub Release tag creation can default to the repo default branch because `target_commitish` is not set.
- Rust build is not `--locked` despite `lasso/Cargo.lock` existing.
- A GitHub Release can be published even if images were not pushed for the same version.
- Release asset upload can succeed even if globs match nothing (risk of empty releases).
- No guardrail preventing reuse of an existing tag/version (reruns can overwrite release assets and GHCR tags).
- Docs mention missing files and appear pinned to an older version string.

## Proposed Changes

### 1) Fix `.github/workflows/release.yml` (Required)
- Fully remove `compose.codex.yml` from bundle assembly and docs (it is not in the repo).
- Add `--locked` to the `cargo build` step for reproducible builds.
- Ensure tags created by the workflow point at the build commit by setting `target_commitish: ${{ github.sha }}` in the release step.
- Set `fail_on_unmatched_files: true` for release uploads and use file-only globs (tarballs + `.sha256`) for clarity.
- Add a preflight check that fails if `refs/tags/<version>` already exists, with an explicit override input to allow intentional overwrite.
- Strengthen workflow dispatch inputs:
  - Use `type: choice` for boolean-like inputs to avoid casing/typing mistakes.
  - Add `draft` and `prerelease` inputs for safe “test release” publishing.
- Fix job dependency graph so “publish release” cannot run until both:
  - CLI bundles were built successfully, and
  - images were pushed successfully.
- Enforce: `publish_release=true` implies pushing images in the same run (no “release without images” mode).

### 2) Align `.github/workflows/README.md` (Required)
- Remove or update the “bundle includes `compose.codex.yml`” statement.
- Ensure the documented “bundle contents” list matches what the workflow actually packages.

### 3) Make Docs Version-Agnostic (Required)
- Replace pinned versions (e.g. `v0.1.4`) in:
  - `README.md`
  - `docs/guide/install.md`
- Use `VERSION=vX.Y.Z` examples and derive bundle names from `VERSION` instead of hardcoding `0.1.4`.
- Keep the “private repo” guidance (use `gh release download` + `install_lasso.sh --bundle/--checksum`).

### 4) `prepare-release-pr` Workflow (No Doc Changes Needed)
- No doc bump step needed once docs are version-agnostic.
- Keep the version bump behavior for:
  - `lasso/Cargo.toml`
  - `pyproject.toml`

## Acceptance Criteria
- `release.yml` no longer references missing files.
- A workflow_dispatch run from a feature branch creates `vX.Y.Z` pointing at that branch’s `github.sha`.
- If `publish_release=true`, the workflow does not publish unless bundles are present and images are pushed.
- Release upload fails if asset globs match nothing.
- Re-running with an existing `vX.Y.Z` fails fast with a clear error unless override is enabled.
- Workflow docs and installation docs match the actual shipped bundle contents.
- Installation docs do not pin a specific version.

## Rollout / Validation Steps
- Dry-run: run the workflow with `publish_release=false` to validate build + bundle assembly.
- Test publish: run from a feature branch with `prerelease=true` to verify tag commitish behavior and avoid affecting `/releases/latest`.

## Open Questions
- None.
