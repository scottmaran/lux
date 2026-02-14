# Feature Plan: `lasso setup` (Interactive Config Wizard)

## Goal
Reduce beta user friction by replacing “edit YAML by hand” with an optional, re-runnable, terminal wizard that:
- Updates `~/.config/lasso/config.yaml` in place (still the source of truth).
- Guides users through the minimal choices required to run Lasso.
- Handles `auth_mode` + API key secrets creation (without leaking secrets to stdout).
- Runs `lasso config apply` by default at the end (can be skipped).

## Non-Goals (Beta)
- No “default provider” concept; no provider selection step.
- No exhaustive configuration editor (leave advanced fields to manual YAML edits).
- Do not run `lasso doctor` automatically at the end.
- No extra flags like `--providers`.

## CLI Surface
Add a new top-level command:

```text
lasso setup [--defaults] [--yes] [--no-apply] [--dry-run]
```

Flags:
- `--defaults`: non-interactive; accept defaults and/or existing config values.
- `--yes`: required for non-interactive mutations when `--defaults` would change existing files (config and/or secrets overwrite).
- `--no-apply`: do not run `lasso config apply` at the end.
- `--dry-run`: print an action plan, write nothing, and imply `--no-apply`.

Notes:
- Interactive mode should error if stdin is not a TTY (unless `--defaults` is used).
- `--dry-run` should still validate inputs/config and may exit non-zero; it just must not mutate the filesystem.
- Global `--config` and `LASSO_CONFIG_DIR`/`LASSO_CONFIG` continue to work (wizard operates on resolved config path).
- Global `--json` should be supported for non-interactive flows (`--defaults`), returning a structured summary of what changed (never include secrets).
- `--yes` in interactive mode only skips the final “confirm and proceed” prompt; it must not auto-overwrite existing secrets files.

## User Flow (Interactive)
1) Intro + what will be configured:
   - Paths: log root, workspace root.
   - Auth: configure `auth_mode` for each provider already present in the config (no provider selection/default provider).
   - API-key providers: optionally write secrets files (with correct permissions).
   - Optionally run `lasso config apply` (default yes).

2) Paths
- Prompt for `paths.log_root` and `paths.workspace_root`.
- Defaults: current values from config (or default config values if missing).
- Validate:
  - Expand `~/` for checks.
  - Check host writability (same semantics as current `host_dir_writable` helper).

3) Providers (no provider selection)
For each `providers.<name>` in config (typically `codex`, `claude`):
- Prompt for `auth_mode`:
  - `api_key`
  - `host_state`
  - Default selection is the current config value (Enter = keep).
- If `host_state`:
  - Keep configured `auth.host_state.paths` as-is.
  - Optionally show warnings if paths are missing (wizard should not block).
  - Show the macOS Claude Keychain caveat when selecting `host_state` for `claude`.
- If `api_key`:
  - Offer to write the secrets file at `providers.<name>.auth.api_key.secrets_file`.
  - If writing secrets:
    - If `providers.<name>.auth.api_key.env_key` is present in the user’s shell environment, offer “use existing env var” as default.
    - Otherwise prompt for the key (hidden input).
    - Create secrets dir `~/.config/lasso/secrets` with `0700` if needed.
    - Write secrets file with `0600`.
    - If file exists: default to NOT overwriting; require explicit confirmation.
  - If the user declines to write secrets, print an explicit “you must do this before `lasso up --provider <name>` will work” message plus the exact shell commands to create the secrets file.

4) Summary + confirm
- Print a summary (paths, provider auth modes, which secrets files will be created/updated).
- Ask for confirmation, then write changes.

5) Apply (default yes)
- Unless `--no-apply`/`--dry-run`, run the equivalent of `lasso config apply`:
  - validate config
  - write `compose.env`
  - create `log_root` + `workspace_root`

6) Final next steps (printed)
- Minimal “what to run next” using explicit `--provider` flags (no implicit defaults), for example:
  - `lasso up --collector-only --wait`
  - `lasso up --provider codex --wait` (or other configured provider)
  - `lasso tui --provider codex` (or other configured provider)

## User Flow (`--defaults`, Non-Interactive)
Intended for scripted installs and CI.

Behavior:
- Load config if present, else start from default config.
- Paths:
  - Keep current values if config exists, otherwise keep defaults.
- Providers:
  - Keep current provider blocks as-is (including `auth_mode`).
  - If a provider is `api_key` and its secrets file is missing:
    - If required env var is present, write secrets file.
    - Otherwise exit non-zero with an actionable error (do not silently “succeed then fail on `up`”).
- Mutations:
  - If config exists and the computed output differs, require `--yes` to proceed.
  - If secrets file exists and would be overwritten, require `--yes`.
- Unless `--no-apply`/`--dry-run`, run apply at the end.

## Implementation Steps
1) Add Clap subcommand
- Update `lasso/src/main.rs`:
  - Add `Commands::Setup { defaults, yes, no_apply, dry_run }`.
  - Wire into main dispatch.

2) Add an interactive prompt helper
- Add dependency (pick one):
  - `dialoguer` (recommended): `Input`, `Select`, `Confirm`, `Password`.
  - Ensure it works on macOS/Linux terminals.
- Implement:
  - `ensure_tty_or_defaults()`
  - `prompt_paths()`
  - `prompt_provider_auth_modes()`
  - `prompt_write_secrets_if_needed()`

3) Config read/modify/write
- Reuse existing `read_config()` for validation when config exists.
- If the config file is missing:
  - Create it from the shipped default template (`DEFAULT_CONFIG_YAML` / `lasso/config/default.yaml`) so the wizard has a known-good base layout (and future comments in the template are preserved).
  - Then parse/validate and proceed with the same patching flow.
- Update fields in memory, then apply a **lossless patch** to `ctx.config_path` that preserves existing comments/whitespace/formatting.
  - We must not rewrite the full file via `serde_yaml` re-serialization.
  - Writes must be atomic:
    - write to a temp file in the same directory, then `rename` into place
    - if config exists, preserve its file mode when possible.
  - Implementation approach:
    - Preferred: a conservative, indentation-aware “scalar replace” patcher for the known Lasso schema paths (paths + providers.*.auth_mode), which edits only the value portion of existing lines and leaves the rest untouched (including inline comments and spacing).
    - Optional: use a lossless YAML parser (e.g. `yaml-edit`) only to *locate* the exact scalar token range for replacement, but do not use APIs that rebuild mappings/sequences (rebuilding risks losing formatting/comments).
  - If the patcher cannot confidently update a required field (unexpected YAML shape), abort with an actionable error (“config format not supported by `lasso setup`; please edit manually”).
  - Always write a trailing newline if we write the file.
  - Patcher constraints (acceptable for beta):
    - Keys must exist in the file and be single-line scalars (`key: value`); do not support block scalars (`|`/`>`), multi-doc YAML, or flow mappings for the touched keys.
    - Preserve inline comments by only replacing the scalar value segment.
    - Preserve existing quoting style when possible; otherwise quote as needed to keep YAML valid.

4) Secrets writer
- Implement a `write_provider_secrets_file(path, env_key, value, overwrite_allowed)` helper:
  - Create parent dir with `0700`.
  - Create/overwrite file with `0600`.
  - Write a shell-compatible assignment (the agent container `source`s this file). Use conservative quoting/escaping so arbitrary key values remain valid.
  - Write atomically via temp file + rename.
  - Never print secret values.

5) Apply reuse
- Refactor current `ConfigCommand::Apply` logic into a shared helper (so `config apply` and `setup` share code without double-output).
  - Keep existing behavior: write env file and create directories.

6) `--dry-run` output
- Compute an “action plan”:
  - config path: will write or not
  - secrets files: create/overwrite/skip
  - apply: run or not
- Print it in human-readable form; if `--json`, return structured output.

## Installer Hook
Update `install_lasso.sh`:
- Add `--setup` flag.
- Default behavior stays the same (do not auto-run).
- When `--setup` is present:
  - Only attempt to run `lasso setup` if stdout/stderr are TTYs (otherwise print a message telling the user to run it manually).
  - Invoke the just-installed binary via an absolute path (e.g. `${INSTALL_DIR}/current/lasso setup`) rather than relying on `~/.local/bin` already being on `PATH`.
  - If the wizard fails, propagate failure code.
- Always end install output with:
  - “Next: run `lasso setup`” (plus `lasso up` examples).

## Docs Updates
- `README.md`: Quick start should become:
  - `lasso setup` (instead of “edit config by hand”)
  - then `lasso up ...`
- `docs/guide/install.md`: Add `lasso setup` as the recommended post-install step; document `install_lasso.sh --setup`.
- `docs/guide/config.md`: Keep the manual secrets instructions, but add “Wizard will optionally create these files.”

## Tests (Rust CLI)
Add non-interactive tests in `lasso/tests/cli.rs`:
- `setup_defaults_creates_secrets_from_env_when_missing`
  - Arrange config with `auth_mode=api_key`, missing secrets file, env var present.
  - Run `lasso setup --defaults --yes --no-apply`.
  - Assert secrets file exists and contains `ENV_KEY=...` (value can be sentinel), with correct perms on unix.
- `setup_defaults_errors_when_api_key_missing_and_env_missing`
  - Missing secrets file + no env var => non-zero with actionable error.
- `setup_dry_run_writes_nothing`
  - Run with `--dry-run --defaults`, assert no file mutations.

Add unit tests for the YAML patcher (in the `lasso` crate, near existing unit tests in `lasso/src/main.rs` or a new module):
- `yaml_patch_preserves_comments_and_spacing`
  - Input YAML contains:
    - comments above and inline (`# ...`)
    - nonstandard spacing around `:`
  - Patch `paths.log_root` and assert:
    - comment lines remain byte-for-byte
    - only the scalar value segment changes
    - trailing newline preserved.

## Acceptance Criteria
- A brand-new user can run:
  - install
  - `lasso setup`
  - `lasso up --collector-only --wait`
  - `lasso up --provider codex --wait`
  - `lasso tui --provider codex`
  without manually editing YAML.
- `lasso setup` is safe to re-run (updates in place, doesn’t clobber secrets unless confirmed / `--yes` in defaults mode).
- Existing `config.yaml` comments/formatting are preserved (only scalar values change for touched keys).
- No secret values are printed to stdout/stderr.
- `--defaults` is fully non-interactive and errors early when it cannot make the system runnable (missing secrets and missing env).

## Open Questions (Small, Beta-Scope)
- None (beta scope). Keep behavior conservative: preserve YAML formatting/comments and never auto-overwrite secrets.
