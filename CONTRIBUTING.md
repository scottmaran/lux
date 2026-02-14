# Contributing to Lasso

## Before You Start

- For a documentation map, see `docs/README.md`.
- For local development notes, see `docs/dev/DEVELOPING.md`.

## Pull Requests

- Keep PRs focused and small when possible.
- Include tests when changing behavior. The repo has:
  - Rust unit tests (`cargo test` in `lasso/` and `collector/ebpf/`)
  - Python tests (`uv run pytest`)
- If you change log schemas or filtering behavior, please update the relevant docs in `collector/*_data.md` and/or `docs/guide/*`.

## Legal: CLA (Required)

By submitting a pull request, you agree to the Contributor License Agreement in `CLA.md`.

If you are contributing on behalf of your employer or another entity, you are responsible for ensuring you have permission to submit the contribution under these terms.

## Legal: Commit Sign-off (Recommended)

We recommend adding a `Signed-off-by:` line to each commit to make contribution provenance explicit.

To sign off a commit:

```bash
git commit -s
```

If you already have commits and need to add sign-offs:

```bash
git rebase --signoff origin/main
```

