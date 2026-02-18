use chrono::{DateTime, Utc};
use clap::{Parser, Subcommand};
use dialoguer::console::style;
use dialoguer::console::Term;
use dialoguer::theme::ColorfulTheme;
use dialoguer::{Confirm, Input, Password, Select};
use dirs::home_dir;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::io;
use std::io::IsTerminal;
#[cfg(unix)]
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

const DEFAULT_CONFIG_YAML: &str = include_str!("../config/default.yaml");

#[derive(Parser, Debug)]
#[command(name = "lasso", version, about = "Lasso CLI")]
struct Cli {
    #[arg(long, global = true)]
    config: Option<PathBuf>,
    #[arg(long, global = true)]
    json: bool,
    #[arg(long = "compose-file", global = true)]
    compose_file: Vec<PathBuf>,
    #[arg(long, global = true, hide = true)]
    bundle_dir: Option<PathBuf>,
    #[arg(long, global = true, hide = true)]
    env_file: Option<PathBuf>,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    Config {
        #[command(subcommand)]
        command: ConfigCommand,
    },
    Setup {
        #[arg(long, default_value_t = false)]
        defaults: bool,
        #[arg(long, default_value_t = false)]
        yes: bool,
        #[arg(long, default_value_t = false)]
        no_apply: bool,
        #[arg(long, default_value_t = false)]
        dry_run: bool,
    },
    Up {
        #[arg(long, conflicts_with = "collector_only")]
        provider: Option<String>,
        #[arg(long, default_value_t = false, conflicts_with = "provider")]
        collector_only: bool,
        #[arg(long)]
        workspace: Option<String>,
        #[arg(long)]
        ui: bool,
        #[arg(long, value_parser = ["always", "never", "missing"]) ]
        pull: Option<String>,
        #[arg(long)]
        wait: bool,
        #[arg(long)]
        timeout_sec: Option<u64>,
    },
    Down {
        #[arg(long, conflicts_with = "collector_only")]
        provider: Option<String>,
        #[arg(long, default_value_t = false, conflicts_with = "provider")]
        collector_only: bool,
        #[arg(long)]
        ui: bool,
    },
    Status {
        #[arg(long, conflicts_with = "collector_only")]
        provider: Option<String>,
        #[arg(long, default_value_t = false, conflicts_with = "provider")]
        collector_only: bool,
        #[arg(long)]
        ui: bool,
    },
    Run {
        #[arg(long)]
        provider: String,
        prompt: String,
        #[arg(long)]
        capture_input: Option<bool>,
        #[arg(long)]
        start_dir: Option<String>,
        #[arg(long)]
        timeout_sec: Option<u64>,
        #[arg(long)]
        env: Vec<String>,
    },
    Tui {
        #[arg(long)]
        provider: String,
        #[arg(long)]
        start_dir: Option<String>,
    },
    Jobs {
        #[command(subcommand)]
        command: JobsCommand,
    },
    Doctor,
    Paths,
    Update {
        #[command(subcommand)]
        command: UpdateCommand,
    },
    Uninstall {
        #[arg(long)]
        remove_config: bool,
        #[arg(long)]
        all_versions: bool,
        #[arg(long)]
        yes: bool,
        #[arg(long)]
        dry_run: bool,
        #[arg(long)]
        force: bool,
    },
    Logs {
        #[command(subcommand)]
        command: LogsCommand,
    },
}

#[derive(Subcommand, Debug)]
enum UpdateCommand {
    Check,
    Apply {
        #[arg(long, conflicts_with = "latest")]
        to: Option<String>,
        #[arg(long)]
        latest: bool,
        #[arg(long)]
        yes: bool,
        #[arg(long)]
        dry_run: bool,
    },
    Rollback {
        #[arg(long, conflicts_with = "previous")]
        to: Option<String>,
        #[arg(long)]
        previous: bool,
        #[arg(long)]
        yes: bool,
        #[arg(long)]
        dry_run: bool,
    },
}

#[derive(Subcommand, Debug)]
enum ConfigCommand {
    Init,
    Edit,
    Validate,
    Apply,
}

#[derive(Subcommand, Debug)]
enum JobsCommand {
    List {
        #[arg(long, conflicts_with = "latest")]
        run_id: Option<String>,
        #[arg(long)]
        latest: bool,
    },
    Get {
        id: String,
        #[arg(long, conflicts_with = "latest")]
        run_id: Option<String>,
        #[arg(long)]
        latest: bool,
    },
}

#[derive(Subcommand, Debug)]
enum LogsCommand {
    Stats {
        #[arg(long, conflicts_with = "latest")]
        run_id: Option<String>,
        #[arg(long)]
        latest: bool,
    },
    Tail {
        #[arg(long, default_value_t = 50)]
        lines: usize,
        #[arg(long)]
        file: Option<String>,
        #[arg(long, conflicts_with = "latest")]
        run_id: Option<String>,
        #[arg(long)]
        latest: bool,
    },
}

#[derive(Debug, Error)]
enum LassoError {
    #[error("config error: {0}")]
    Config(String),
    #[error("io error: {0}")]
    Io(#[from] io::Error),
    #[error("prompt error: {0}")]
    Prompt(#[from] dialoguer::Error),
    #[error("yaml error: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("process error: {0}")]
    Process(String),
    #[error("process error: {message}")]
    ProcessDetailed {
        message: String,
        details: ProcessErrorDetails,
    },
    #[error("http error: {0}")]
    Http(#[from] reqwest::Error),
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Config {
    version: u32,
    paths: Paths,
    release: Release,
    docker: Docker,
    harness: Harness,
    providers: BTreeMap<String, Provider>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Paths {
    log_root: String,
    workspace_root: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Release {
    tag: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Docker {
    project_name: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Harness {
    api_host: String,
    api_port: u16,
    api_token: String,
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum AuthMode {
    ApiKey,
    HostState,
}

impl AuthMode {
    fn as_str(&self) -> &'static str {
        match self {
            Self::ApiKey => "api_key",
            Self::HostState => "host_state",
        }
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Provider {
    auth_mode: AuthMode,
    mount_host_state_in_api_mode: bool,
    commands: ProviderCommands,
    auth: ProviderAuth,
    ownership: ProviderOwnership,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct ProviderCommands {
    tui: String,
    run_template: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct ProviderAuth {
    api_key: ProviderApiKeyAuth,
    host_state: ProviderHostStateAuth,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct ProviderApiKeyAuth {
    secrets_file: String,
    env_key: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct ProviderHostStateAuth {
    paths: Vec<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct ProviderOwnership {
    root_comm: Vec<String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            version: 2,
            paths: Paths::default(),
            release: Release::default(),
            docker: Docker::default(),
            harness: Harness::default(),
            providers: default_providers(),
        }
    }
}

impl Default for Paths {
    fn default() -> Self {
        if let Ok(paths) = computed_default_paths_for_current_os() {
            return paths;
        }
        let workspace_root = home_dir()
            .map(|path| path.to_string_lossy().to_string())
            .unwrap_or_else(|| "~".to_string());
        let log_root = match env::consts::OS {
            "macos" => "/Users/Shared/Lasso/logs",
            "linux" => "/var/lib/lasso/logs",
            _ => "/var/lib/lasso/logs",
        }
        .to_string();
        Self {
            log_root,
            workspace_root,
        }
    }
}

impl Default for Release {
    fn default() -> Self {
        Self {
            tag: "".to_string(),
        }
    }
}

impl Default for Docker {
    fn default() -> Self {
        Self {
            project_name: "lasso".to_string(),
        }
    }
}

impl Default for Harness {
    fn default() -> Self {
        Self {
            api_host: "127.0.0.1".to_string(),
            api_port: 8081,
            api_token: "".to_string(),
        }
    }
}

impl Default for AuthMode {
    fn default() -> Self {
        Self::ApiKey
    }
}

impl Default for Provider {
    fn default() -> Self {
        Self {
            auth_mode: AuthMode::ApiKey,
            mount_host_state_in_api_mode: false,
            commands: ProviderCommands::default(),
            auth: ProviderAuth::default(),
            ownership: ProviderOwnership::default(),
        }
    }
}

impl Default for ProviderCommands {
    fn default() -> Self {
        Self {
            tui: "bash -l".to_string(),
            run_template: "bash -lc {prompt}".to_string(),
        }
    }
}

impl Default for ProviderAuth {
    fn default() -> Self {
        Self {
            api_key: ProviderApiKeyAuth::default(),
            host_state: ProviderHostStateAuth::default(),
        }
    }
}

impl Default for ProviderApiKeyAuth {
    fn default() -> Self {
        Self {
            secrets_file: "".to_string(),
            env_key: "".to_string(),
        }
    }
}

impl Default for ProviderHostStateAuth {
    fn default() -> Self {
        Self { paths: Vec::new() }
    }
}

impl Default for ProviderOwnership {
    fn default() -> Self {
        Self {
            root_comm: Vec::new(),
        }
    }
}

fn default_providers() -> BTreeMap<String, Provider> {
    let mut providers = BTreeMap::new();
    providers.insert(
        "codex".to_string(),
        Provider {
            auth_mode: AuthMode::ApiKey,
            mount_host_state_in_api_mode: false,
            commands: ProviderCommands {
                tui: "codex -C /work -s danger-full-access".to_string(),
                run_template: "codex -C /work -s danger-full-access exec {prompt}".to_string(),
            },
            auth: ProviderAuth {
                api_key: ProviderApiKeyAuth {
                    secrets_file: "~/.config/lasso/secrets/codex.env".to_string(),
                    env_key: "OPENAI_API_KEY".to_string(),
                },
                host_state: ProviderHostStateAuth {
                    paths: vec![
                        "~/.codex/auth.json".to_string(),
                        "~/.codex/skills".to_string(),
                    ],
                },
            },
            ownership: ProviderOwnership {
                root_comm: vec!["codex".to_string()],
            },
        },
    );
    providers.insert(
        "claude".to_string(),
        Provider {
            auth_mode: AuthMode::HostState,
            mount_host_state_in_api_mode: false,
            commands: ProviderCommands {
                tui: "claude".to_string(),
                run_template: "claude -p {prompt}".to_string(),
            },
            auth: ProviderAuth {
                api_key: ProviderApiKeyAuth {
                    secrets_file: "~/.config/lasso/secrets/claude.env".to_string(),
                    env_key: "ANTHROPIC_API_KEY".to_string(),
                },
                host_state: ProviderHostStateAuth {
                    paths: vec![
                        "~/.claude.json".to_string(),
                        "~/.claude".to_string(),
                        "~/.config/claude-code/auth.json".to_string(),
                    ],
                },
            },
            ownership: ProviderOwnership {
                root_comm: vec!["claude".to_string()],
            },
        },
    );
    providers
}

#[derive(Debug, Serialize)]
struct JsonResult<T: Serialize> {
    ok: bool,
    result: Option<T>,
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error_details: Option<ProcessErrorDetails>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
struct ProcessErrorDetails {
    error_code: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    hint: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    command: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    raw_stderr: Option<String>,
}

#[derive(Debug)]
struct Context {
    config_path: PathBuf,
    env_file: PathBuf,
    bundle_dir: PathBuf,
    compose_file_overrides: Vec<PathBuf>,
    json: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ActiveRunState {
    run_id: String,
    started_at: String,
    #[serde(default)]
    workspace_root: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ActiveProviderState {
    provider: String,
    auth_mode: String,
    run_id: String,
    started_at: String,
}

#[derive(Debug, Clone)]
struct CommandOutput {
    status_code: i32,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

impl CommandOutput {
    fn success(&self) -> bool {
        self.status_code == 0
    }
}

trait DockerRunner {
    fn run(
        &self,
        args: &[String],
        cwd: &Path,
        env_overrides: &BTreeMap<String, String>,
        capture_output: bool,
    ) -> Result<CommandOutput, io::Error>;
}

struct RealDockerRunner;

impl DockerRunner for RealDockerRunner {
    fn run(
        &self,
        args: &[String],
        cwd: &Path,
        env_overrides: &BTreeMap<String, String>,
        capture_output: bool,
    ) -> Result<CommandOutput, io::Error> {
        let mut cmd = Command::new("docker");
        cmd.args(args).current_dir(cwd);
        for (key, value) in env_overrides {
            cmd.env(key, value);
        }
        if capture_output {
            let output = cmd.output()?;
            let status_code =
                output
                    .status
                    .code()
                    .unwrap_or(if output.status.success() { 0 } else { 1 });
            Ok(CommandOutput {
                status_code,
                stdout: output.stdout,
                stderr: output.stderr,
            })
        } else {
            let status = cmd.status()?;
            let status_code = status
                .code()
                .unwrap_or(if status.success() { 0 } else { 1 });
            Ok(CommandOutput {
                status_code,
                stdout: Vec::new(),
                stderr: Vec::new(),
            })
        }
    }
}

fn main() -> Result<(), LassoError> {
    let cli = Cli::parse();
    let ctx = build_context(&cli)?;
    let runner = RealDockerRunner;

    let result = match cli.command {
        Commands::Config { command } => handle_config(&ctx, command),
        Commands::Setup {
            defaults,
            yes,
            no_apply,
            dry_run,
        } => handle_setup(&ctx, defaults, yes, no_apply, dry_run),
        Commands::Up {
            provider,
            collector_only,
            workspace,
            ui,
            pull,
            wait,
            timeout_sec,
        } => handle_up(
            &ctx,
            provider,
            collector_only,
            workspace,
            ui,
            pull,
            wait,
            timeout_sec,
            &runner,
        ),
        Commands::Down {
            provider,
            collector_only,
            ui,
        } => handle_down(&ctx, provider, collector_only, ui, &runner),
        Commands::Status {
            provider,
            collector_only,
            ui,
        } => handle_status(&ctx, provider, collector_only, ui, &runner),
        Commands::Run {
            provider,
            prompt,
            capture_input,
            start_dir,
            timeout_sec,
            env,
        } => handle_run(
            &ctx,
            provider,
            prompt,
            capture_input,
            start_dir,
            timeout_sec,
            env,
        ),
        Commands::Tui {
            provider,
            start_dir,
        } => handle_tui(&ctx, provider, start_dir, &runner),
        Commands::Jobs { command } => handle_jobs(&ctx, command),
        Commands::Doctor => handle_doctor(&ctx),
        Commands::Paths => handle_paths(&ctx),
        Commands::Update { command } => handle_update(&ctx, command),
        Commands::Uninstall {
            remove_config,
            all_versions,
            yes,
            dry_run,
            force,
        } => handle_uninstall(
            &ctx,
            remove_config,
            all_versions,
            yes,
            dry_run,
            force,
            &runner,
        ),
        Commands::Logs { command } => handle_logs(&ctx, command),
    };

    if let Err(err) = result {
        if ctx.json {
            let payload = JsonResult::<serde_json::Value> {
                ok: false,
                result: None,
                error: Some(err.to_string()),
                error_details: extract_process_error_details(&err),
            };
            print_json(&payload)?;
        } else {
            eprintln!("{err}");
        }
        std::process::exit(1);
    }

    Ok(())
}

fn build_context(cli: &Cli) -> Result<Context, LassoError> {
    let config_path = resolve_config_path(cli.config.as_ref());
    let env_file = resolve_env_file(cli.env_file.as_ref());
    let bundle_dir = resolve_bundle_dir(cli.bundle_dir.as_ref());
    let compose_file_overrides = resolve_compose_overrides(&cli.compose_file);
    Ok(Context {
        config_path,
        env_file,
        bundle_dir,
        compose_file_overrides,
        json: cli.json,
    })
}

fn resolve_config_path(override_path: Option<&PathBuf>) -> PathBuf {
    if let Some(path) = override_path {
        return path.clone();
    }
    if let Ok(path) = env::var("LASSO_CONFIG") {
        return PathBuf::from(path);
    }
    let mut base = default_config_dir();
    base.push("config.yaml");
    base
}

fn resolve_env_file(override_path: Option<&PathBuf>) -> PathBuf {
    if let Some(path) = override_path {
        return path.clone();
    }
    if let Ok(path) = env::var("LASSO_ENV_FILE") {
        return PathBuf::from(path);
    }
    let mut base = default_config_dir();
    base.push("compose.env");
    base
}

fn resolve_bundle_dir(override_path: Option<&PathBuf>) -> PathBuf {
    if let Some(path) = override_path {
        return path.clone();
    }
    if let Ok(path) = env::var("LASSO_BUNDLE_DIR") {
        return PathBuf::from(path);
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            let candidate = dir.to_path_buf();
            if candidate.join("compose.yml").exists() {
                return candidate;
            }
        }
    }
    if let Ok(cwd) = env::current_dir() {
        if cwd.join("compose.yml").exists() {
            return cwd;
        }
        return cwd;
    }
    PathBuf::from(".")
}

fn resolve_compose_overrides(overrides: &[PathBuf]) -> Vec<PathBuf> {
    if overrides.is_empty() {
        return Vec::new();
    }
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    overrides
        .iter()
        .map(|path| {
            if path.is_absolute() {
                path.clone()
            } else {
                cwd.join(path)
            }
        })
        .collect()
}

#[derive(Debug, Clone)]
struct PolicyPaths {
    home: PathBuf,
    log_root: PathBuf,
    workspace_root: PathBuf,
}

fn required_home_dir() -> Result<PathBuf, LassoError> {
    let home = home_dir().ok_or_else(|| {
        LassoError::Config("unable to resolve $HOME; set HOME to an existing directory".to_string())
    })?;
    if !home.is_absolute() {
        return Err(LassoError::Config(format!(
            "resolved HOME path is not absolute: {}",
            home.display()
        )));
    }
    if !home.exists() {
        return Err(LassoError::Config(format!(
            "resolved HOME path does not exist: {}",
            home.display()
        )));
    }
    fs::canonicalize(&home).map_err(|err| {
        LassoError::Config(format!(
            "failed to canonicalize HOME directory {}: {}",
            home.display(),
            err
        ))
    })
}

fn default_paths_for_os(os: &str, home: &Path) -> Result<Paths, LassoError> {
    match os {
        "macos" => Ok(Paths {
            log_root: "/Users/Shared/Lasso/logs".to_string(),
            workspace_root: home.to_string_lossy().to_string(),
        }),
        "linux" => Ok(Paths {
            log_root: "/var/lib/lasso/logs".to_string(),
            workspace_root: home.to_string_lossy().to_string(),
        }),
        other => Err(LassoError::Config(format!(
            "unsupported host operating system '{}' for default path computation; supported: macos, linux",
            other
        ))),
    }
}

fn computed_default_paths_for_current_os() -> Result<Paths, LassoError> {
    let home = required_home_dir()?;
    default_paths_for_os(env::consts::OS, &home)
}

fn build_default_config_yaml() -> Result<String, LassoError> {
    let defaults = computed_default_paths_for_current_os()?;
    let mut edits = SetupYamlEdits::default();
    edits.log_root = Some(defaults.log_root);
    edits.workspace_root = Some(defaults.workspace_root);
    let (patched, _changed) = patch_setup_config_yaml(DEFAULT_CONFIG_YAML, &edits)?;
    Ok(patched)
}

fn expand_home_path(input: &str, home: &Path, field: &str) -> Result<PathBuf, LassoError> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Err(LassoError::Config(format!(
            "{field} must be a non-empty absolute path"
        )));
    }
    if trimmed == "~" {
        return Ok(home.to_path_buf());
    }
    if let Some(stripped) = trimmed.strip_prefix("~/") {
        return Ok(home.join(stripped));
    }
    if trimmed.starts_with('~') {
        return Err(LassoError::Config(format!(
            "{field} uses unsupported '~' syntax; use '~/' or an absolute path"
        )));
    }
    Ok(PathBuf::from(trimmed))
}

fn canonicalize_policy_path(path: &Path, field: &str) -> Result<PathBuf, LassoError> {
    if !path.is_absolute() {
        return Err(LassoError::Config(format!(
            "{field} must be an absolute path: {}",
            path.display()
        )));
    }
    if path.exists() {
        return fs::canonicalize(path).map_err(|err| {
            LassoError::Config(format!(
                "failed to canonicalize {field} ({}): {}",
                path.display(),
                err
            ))
        });
    }

    let mut cursor = path.to_path_buf();
    let mut tail: Vec<std::ffi::OsString> = Vec::new();
    while !cursor.exists() {
        let name = cursor.file_name().ok_or_else(|| {
            LassoError::Config(format!(
                "{field} is not canonicalizable: {}",
                path.display()
            ))
        })?;
        tail.push(name.to_os_string());
        cursor = cursor
            .parent()
            .ok_or_else(|| {
                LassoError::Config(format!(
                    "{field} is not canonicalizable: {}",
                    path.display()
                ))
            })?
            .to_path_buf();
    }

    let mut canonical = fs::canonicalize(&cursor).map_err(|err| {
        LassoError::Config(format!(
            "failed to canonicalize {field} ancestor ({}): {}",
            cursor.display(),
            err
        ))
    })?;
    for segment in tail.iter().rev() {
        canonical.push(segment);
    }
    Ok(canonical)
}

fn resolve_policy_path(input: &str, field: &str, home: &Path) -> Result<PathBuf, LassoError> {
    let expanded = expand_home_path(input, home, field)?;
    canonicalize_policy_path(&expanded, field)
}

fn path_is_within(path: &Path, root: &Path) -> bool {
    path == root || path.starts_with(root)
}

fn resolve_config_policy_paths(cfg: &Config) -> Result<PolicyPaths, LassoError> {
    let home = required_home_dir()?;
    let workspace_root =
        resolve_policy_path(&cfg.paths.workspace_root, "paths.workspace_root", &home)?;
    let log_root = resolve_policy_path(&cfg.paths.log_root, "paths.log_root", &home)?;

    if !path_is_within(&workspace_root, &home) {
        return Err(LassoError::Config(format!(
            "paths.workspace_root must be under $HOME (home={}, workspace={})",
            home.display(),
            workspace_root.display()
        )));
    }
    if path_is_within(&log_root, &home) {
        return Err(LassoError::Config(format!(
            "paths.log_root must be outside $HOME to protect evidence integrity (home={}, log_root={})",
            home.display(),
            log_root.display()
        )));
    }
    if path_is_within(&workspace_root, &log_root) || path_is_within(&log_root, &workspace_root) {
        return Err(LassoError::Config(format!(
            "paths.workspace_root and paths.log_root must not overlap (workspace={}, log_root={})",
            workspace_root.display(),
            log_root.display()
        )));
    }

    Ok(PolicyPaths {
        home,
        log_root,
        workspace_root,
    })
}

fn default_config_dir() -> PathBuf {
    if let Ok(path) = env::var("LASSO_CONFIG_DIR") {
        return PathBuf::from(path);
    }
    let mut base = home_dir().unwrap_or_else(|| PathBuf::from("."));
    base.push(".config");
    base.push("lasso");
    base
}

fn ensure_parent(path: &Path) -> Result<(), LassoError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    Ok(())
}

fn read_config_from_str(content: &str) -> Result<Config, LassoError> {
    let cfg: Config = serde_yaml::from_str(content)?;
    if cfg.version != 2 {
        return Err(LassoError::Config(format!(
            "unsupported config version {}",
            cfg.version
        )));
    }
    validate_config(&cfg)?;
    Ok(cfg)
}

fn read_config(path: &Path) -> Result<Config, LassoError> {
    let content = fs::read_to_string(path)?;
    read_config_from_str(&content)
}

fn validate_config(cfg: &Config) -> Result<(), LassoError> {
    if env::consts::OS != "macos" && env::consts::OS != "linux" {
        return Err(LassoError::Config(format!(
            "unsupported host operating system '{}'; supported: macos, linux",
            env::consts::OS
        )));
    }
    let _ = resolve_config_policy_paths(cfg)?;

    if cfg.providers.is_empty() {
        return Err(LassoError::Config(
            "config.providers must contain at least one provider".to_string(),
        ));
    }
    for (name, provider) in &cfg.providers {
        if provider.commands.tui.trim().is_empty() {
            return Err(LassoError::Config(format!(
                "providers.{name}.commands.tui must be non-empty"
            )));
        }
        if provider.commands.run_template.trim().is_empty() {
            return Err(LassoError::Config(format!(
                "providers.{name}.commands.run_template must be non-empty"
            )));
        }
        if provider.auth.api_key.secrets_file.trim().is_empty() {
            return Err(LassoError::Config(format!(
                "providers.{name}.auth.api_key.secrets_file must be non-empty"
            )));
        }
        if provider.auth.api_key.env_key.trim().is_empty() {
            return Err(LassoError::Config(format!(
                "providers.{name}.auth.api_key.env_key must be non-empty"
            )));
        }
        if provider.auth.host_state.paths.is_empty() {
            return Err(LassoError::Config(format!(
                "providers.{name}.auth.host_state.paths must contain at least one path"
            )));
        }
        if provider.ownership.root_comm.is_empty() {
            return Err(LassoError::Config(format!(
                "providers.{name}.ownership.root_comm must contain at least one process name"
            )));
        }
    }
    Ok(())
}

fn expand_path(input: &str) -> String {
    if let Some(stripped) = input.strip_prefix("~/") {
        if let Some(home) = home_dir() {
            return home.join(stripped).to_string_lossy().to_string();
        }
    }
    input.to_string()
}

fn config_to_env(cfg: &Config) -> BTreeMap<String, String> {
    let mut envs = BTreeMap::new();
    let tag = if cfg.release.tag.trim().is_empty() {
        format!("v{}", env!("CARGO_PKG_VERSION"))
    } else {
        cfg.release.tag.trim().to_string()
    };
    envs.insert("LASSO_VERSION".to_string(), tag);
    envs.insert(
        "LASSO_LOG_ROOT".to_string(),
        expand_path(&cfg.paths.log_root),
    );
    envs.insert(
        "LASSO_WORKSPACE_ROOT".to_string(),
        expand_path(&cfg.paths.workspace_root),
    );
    if !cfg.harness.api_token.trim().is_empty() {
        envs.insert(
            "HARNESS_API_TOKEN".to_string(),
            cfg.harness.api_token.clone(),
        );
    }
    envs.insert(
        "HARNESS_HTTP_PORT".to_string(),
        cfg.harness.api_port.to_string(),
    );
    let root_comm = merged_root_comm(cfg);
    if !root_comm.is_empty() {
        envs.insert("COLLECTOR_ROOT_COMM".to_string(), root_comm.join(","));
    }
    envs
}

fn merged_root_comm(cfg: &Config) -> Vec<String> {
    let mut merged = std::collections::BTreeSet::new();
    for provider in cfg.providers.values() {
        for value in &provider.ownership.root_comm {
            let item = value.trim();
            if !item.is_empty() {
                merged.insert(item.to_string());
            }
        }
    }
    merged.into_iter().collect()
}

fn write_env_file(path: &Path, envs: &BTreeMap<String, String>) -> Result<(), LassoError> {
    ensure_parent(path)?;
    let mut content = String::new();
    for (key, value) in envs {
        content.push_str(&format!("{}={}\n", key, value));
    }
    fs::write(path, content)?;
    Ok(())
}

fn host_dir_writable(path: &Path) -> bool {
    fs::create_dir_all(path)
        .and_then(|_| {
            let test_path = path.join(".lasso_write_test");
            fs::write(&test_path, b"ok")?;
            fs::remove_file(&test_path)?;
            Ok(())
        })
        .is_ok()
}

#[derive(Debug, Clone, Serialize)]
struct SetupActionPlan {
    config_path: String,
    created_config: bool,
    updated_config: bool,
    wrote_secrets: Vec<SetupSecretPlan>,
    apply: bool,
    dry_run: bool,
    warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
struct SetupSecretPlan {
    provider: String,
    env_key: String,
    path: String,
    action: String,
}

fn handle_setup(
    ctx: &Context,
    defaults: bool,
    yes: bool,
    no_apply: bool,
    dry_run: bool,
) -> Result<(), LassoError> {
    let apply = !no_apply && !dry_run;
    if ctx.json && !defaults {
        return Err(LassoError::Process(
            "--json is only supported with `lasso setup --defaults`".to_string(),
        ));
    }
    if !defaults && !io::stdin().is_terminal() {
        return Err(LassoError::Process(
            "interactive setup requires a TTY; re-run with `--defaults` for non-interactive mode"
                .to_string(),
        ));
    }

    let config_path = &ctx.config_path;
    let config_exists = config_path.exists();
    let mut base_yaml = if config_exists {
        fs::read_to_string(config_path)?
    } else {
        build_default_config_yaml()?
    };
    if !base_yaml.ends_with('\n') {
        base_yaml.push('\n');
    }
    let base_cfg = match read_config_from_str(&base_yaml) {
        Ok(cfg) => cfg,
        Err(err) => {
            return Err(LassoError::Config(format!(
                "config is invalid. Please edit {} and try again. ({})",
                config_path.display(),
                err
            )));
        }
    };
    let created_config = !config_exists;

    let mut warnings: Vec<String> = Vec::new();
    let mut wrote_secrets: Vec<SetupSecretPlan> = Vec::new();

    if defaults {
        // Non-interactive: keep values as-is, but ensure API-key providers have secrets.
        for (provider_name, provider) in &base_cfg.providers {
            if provider.auth_mode != AuthMode::ApiKey {
                continue;
            }
            let secrets_file = PathBuf::from(expand_path(&provider.auth.api_key.secrets_file));
            if secrets_file.exists() {
                continue;
            }
            let env_key = provider.auth.api_key.env_key.trim();
            let value = env::var(env_key).ok().unwrap_or_default();
            if value.trim().is_empty() {
                return Err(LassoError::Process(format!(
                    "provider '{provider_name}' uses auth_mode=api_key but secrets file is missing at {}; set {} in your environment or create the secrets file manually",
                    secrets_file.display(),
                    env_key
                )));
            }
            if !dry_run {
                write_provider_secrets_file(&secrets_file, env_key, &value, false)?;
            }
            wrote_secrets.push(SetupSecretPlan {
                provider: provider_name.clone(),
                env_key: env_key.to_string(),
                path: secrets_file.to_string_lossy().to_string(),
                action: "create_from_env".to_string(),
            });
        }

        if created_config && !dry_run {
            write_atomic_text_file_preserving_mode(config_path, &base_yaml, 0o644)?;
        }

        if apply && !dry_run {
            let _ = apply_config(ctx, &base_cfg)?;
        }

        let plan = SetupActionPlan {
            config_path: config_path.to_string_lossy().to_string(),
            created_config,
            updated_config: false,
            wrote_secrets,
            apply,
            dry_run,
            warnings,
        };
        if ctx.json {
            return output(ctx, serde_json::to_value(plan)?);
        }
        println!("{}", serde_json::to_string_pretty(&plan)?);
        return Ok(());
    }

    #[derive(Debug, Clone)]
    struct PendingSecretWrite {
        provider: String,
        env_key: String,
        path: PathBuf,
        value: String,
        overwrite: bool,
    }

    fn manual_secrets_instructions(env_key: &str, secrets_file: &Path) -> String {
        let dir = secrets_file.parent().unwrap_or_else(|| Path::new("."));
        format!(
            "mkdir -p {dir}\nchmod 700 {dir}\nprintf '{env_key}=%s\\n' 'YOUR_KEY' > {file}\nchmod 600 {file}",
            dir = dir.to_string_lossy(),
            file = secrets_file.to_string_lossy(),
            env_key = env_key
        )
    }

    fn print_step(step: usize, total: usize, title: &str) {
        println!();
        println!(
            "{} {}",
            style(format!("Lasso Setup ({step}/{total})")).bold().cyan(),
            style(title).bold()
        );
    }

    // Interactive setup (wizard loop).
    let theme = ColorfulTheme::default();
    let total_steps = 4usize;

    if io::stdout().is_terminal() {
        // Best-effort clear so the wizard starts at the top of the visible terminal,
        // without needing a full-screen TUI.
        let _ = Term::stdout().clear_screen();
    }
    println!("{}", style("Lasso Setup").bold().cyan());
    println!(
        "{}",
        style("Welcome to Lasso! The blackbox for your ai agents. ")
    );
    println!(
        "{}",
        style("Follow the prompts to help set a few configs, stored at: ").dim()
    );
    println!();
    println!(
        "{}",
        style(format!("Config: {}", config_path.display())).dim()
    );
    // println!(
    //     "{}",
    //     style("Updates config.yaml in place (preserves comments/formatting).").dim()
    // );
    // println!(
    //     "{}",
    //     style("Can optionally create provider secrets files (never prints secret values).").dim()
    // );

    let mut log_root_state = base_cfg.paths.log_root.clone();
    let mut workspace_root_state = base_cfg.paths.workspace_root.clone();
    let mut provider_auth_state: BTreeMap<String, String> = BTreeMap::new();
    for (provider_name, provider) in &base_cfg.providers {
        provider_auth_state.insert(
            provider_name.clone(),
            provider.auth_mode.as_str().to_string(),
        );
    }

    let mut pending_secrets: Vec<PendingSecretWrite> = Vec::new();
    let mut missing_api_key_secrets: Vec<(String, String, PathBuf)> = Vec::new();

    let (patched_yaml, cfg_after_yaml, should_write_config) = loop {
        warnings.clear();
        pending_secrets.clear();
        missing_api_key_secrets.clear();

        print_step(1, total_steps, "Paths");
        println!(
            "{}",
            style("This will be where your logs are stored (on your computer/host).").dim()
        );
        println!(
            "{}",
            style(
                "These logs can grow to be large. 
We recommend putting it in your root directory with our default name."
            )
            .dim()
        );
        log_root_state = Input::<String>::with_theme(&theme)
            .with_prompt("What directory do you want your logs to be stored?")
            .default(log_root_state.clone())
            .interact_text()?;
        println!("{}", style("Great! Now choose your agent's workspace"));
        println!(
            "{}",
            style(
                "This will be where your agents have access
Lasso works by creating a separate Docker container for your agents to work in
(that way they don't have unfettered access to your personal machine).

The safest way would be to create a new, empty directory (e.g. ~/lasso-workspace)
that your agents can access from the isolatd container.

If you want your agent to retain access to all of your files, you can set the workspace
as something like your user root directory (e.g. ~/ ).

We recommend using your best judgement.
"
            )
            .dim()
        );
        workspace_root_state = Input::<String>::with_theme(&theme)
            .with_prompt("Select your agent's workspace folder.")
            .default(workspace_root_state.clone())
            .interact_text()?;

        print_step(2, total_steps, "Provider Auth");
        println!(
            "{}",
            style(
                "How Lasso authenticates your agents depends on 
if you're using an API key or a subscription-based plan"
            )
            .dim()
        );
        println!(
            "{}",
            style("select host_state if you don't use an API key").dim()
        );

        #[derive(Debug, Clone)]
        struct ApiKeyProviderInfo {
            provider: String,
            env_key: String,
            secrets_file: PathBuf,
            secrets_exists: bool,
        }

        let mut api_key_providers: Vec<ApiKeyProviderInfo> = Vec::new();

        for (provider_name, provider) in &base_cfg.providers {
            let current = provider_auth_state
                .get(provider_name)
                .map(|s| s.as_str())
                .unwrap_or_else(|| provider.auth_mode.as_str());

            let items = ["api_key", "host_state (mounts local app state)"];
            let values = ["api_key", "host_state"];
            let default_idx = if current == "host_state" { 1 } else { 0 };
            let selection = Select::with_theme(&theme)
                .with_prompt(format!(
                    "providers.{provider_name}.auth_mode (Enter = keep {current})"
                ))
                .items(&items)
                .default(default_idx)
                .interact()?;
            let chosen = values[selection].to_string();
            provider_auth_state.insert(provider_name.clone(), chosen.clone());

            if provider_name == "claude" && chosen == "host_state" && env::consts::OS == "macos" {
                warnings.push("provider 'claude': host_state mode on macOS can fail when auth depends on Keychain; switch to api_key if needed".to_string());
            }

            let should_mount_host_state =
                chosen == "host_state" || provider.mount_host_state_in_api_mode;
            if should_mount_host_state {
                for configured in &provider.auth.host_state.paths {
                    let host_path = PathBuf::from(expand_path(configured));
                    if !host_path.exists() {
                        warnings.push(format!(
                            "provider '{provider_name}': host-state path missing: {}",
                            host_path.display()
                        ));
                    }
                }
            }

            if chosen != "api_key" {
                continue;
            }

            let env_key = provider.auth.api_key.env_key.trim().to_string();
            let secrets_file = PathBuf::from(expand_path(&provider.auth.api_key.secrets_file));
            let secrets_exists = secrets_file.exists();
            api_key_providers.push(ApiKeyProviderInfo {
                provider: provider_name.clone(),
                env_key,
                secrets_file,
                secrets_exists,
            });
        }

        print_step(3, total_steps, "Secrets");
        if api_key_providers.is_empty() {
            println!(
                "{}",
                style("No providers are using auth_mode=api_key.").dim()
            );
        }
        for item in &api_key_providers {
            let wants_write = if item.secrets_exists {
                Confirm::with_theme(&theme)
                    .with_prompt(format!(
                        "Secrets file exists for provider '{}' at {}. Overwrite?",
                        item.provider,
                        item.secrets_file.display()
                    ))
                    .default(false)
                    .interact()?
            } else {
                Confirm::with_theme(&theme)
                    .with_prompt(format!(
                        "Create secrets file for provider '{}' at {} now?",
                        item.provider,
                        item.secrets_file.display()
                    ))
                    .default(true)
                    .interact()?
            };

            if !wants_write {
                if !item.secrets_exists {
                    missing_api_key_secrets.push((
                        item.provider.clone(),
                        item.env_key.clone(),
                        item.secrets_file.clone(),
                    ));
                }
                continue;
            }

            if dry_run {
                pending_secrets.push(PendingSecretWrite {
                    provider: item.provider.clone(),
                    env_key: item.env_key.clone(),
                    path: item.secrets_file.clone(),
                    value: String::new(),
                    overwrite: item.secrets_exists,
                });
                continue;
            }

            let existing_env = env::var(&item.env_key).ok().unwrap_or_default();
            let value = if !existing_env.trim().is_empty() {
                let use_env = Confirm::with_theme(&theme)
                    .with_prompt(format!(
                        "Use existing ${} from your environment for provider '{}'?",
                        item.env_key, item.provider
                    ))
                    .default(true)
                    .interact()?;
                if use_env {
                    existing_env
                } else {
                    Password::with_theme(&theme)
                        .with_prompt(format!(
                            "Enter {} for provider '{}'",
                            item.env_key, item.provider
                        ))
                        .with_confirmation("Confirm value", "Values do not match")
                        .interact()?
                }
            } else {
                Password::with_theme(&theme)
                    .with_prompt(format!(
                        "Enter {} for provider '{}'",
                        item.env_key, item.provider
                    ))
                    .with_confirmation("Confirm value", "Values do not match")
                    .interact()?
            };

            pending_secrets.push(PendingSecretWrite {
                provider: item.provider.clone(),
                env_key: item.env_key.clone(),
                path: item.secrets_file.clone(),
                value,
                overwrite: item.secrets_exists,
            });
        }

        // Desired config (in memory).
        let mut desired_cfg = base_cfg.clone();
        desired_cfg.paths.log_root = log_root_state.clone();
        desired_cfg.paths.workspace_root = workspace_root_state.clone();
        for (provider_name, auth_mode) in &provider_auth_state {
            let provider = desired_cfg
                .providers
                .get_mut(provider_name)
                .ok_or_else(|| {
                    LassoError::Config(format!("provider missing from config: {provider_name}"))
                })?;
            provider.auth_mode = match auth_mode.as_str() {
                "api_key" => AuthMode::ApiKey,
                "host_state" => AuthMode::HostState,
                other => {
                    return Err(LassoError::Config(format!(
                        "unsupported auth_mode '{other}'"
                    )))
                }
            };
        }
        validate_config(&desired_cfg)?;

        let mut yaml_edits = SetupYamlEdits::default();
        if desired_cfg.paths.log_root != base_cfg.paths.log_root {
            yaml_edits.log_root = Some(desired_cfg.paths.log_root.clone());
        }
        if desired_cfg.paths.workspace_root != base_cfg.paths.workspace_root {
            yaml_edits.workspace_root = Some(desired_cfg.paths.workspace_root.clone());
        }
        for (provider_name, provider) in &desired_cfg.providers {
            let desired = provider.auth_mode.as_str();
            let existing = base_cfg
                .providers
                .get(provider_name)
                .map(|p| p.auth_mode.as_str())
                .unwrap_or("");
            if desired != existing {
                yaml_edits
                    .provider_auth_modes
                    .insert(provider_name.clone(), desired.to_string());
            }
        }

        let (candidate_yaml, yaml_changed) = patch_setup_config_yaml(&base_yaml, &yaml_edits)?;
        let candidate_cfg = read_config_from_str(&candidate_yaml)?;
        let should_write_config = created_config || yaml_changed;

        print_step(4, total_steps, "Review");
        println!("{} {}", style("Config:").bold(), config_path.display());

        println!("\n{}", style("Paths").bold());
        if desired_cfg.paths.log_root == base_cfg.paths.log_root {
            println!(
                "  {} {}",
                style("paths.log_root:").dim(),
                style(&desired_cfg.paths.log_root).dim()
            );
        } else {
            println!(
                "  {} {} {} {}",
                style("paths.log_root:").dim(),
                style(&base_cfg.paths.log_root).dim(),
                style("->").dim(),
                style(&desired_cfg.paths.log_root).green()
            );
        }
        if desired_cfg.paths.workspace_root == base_cfg.paths.workspace_root {
            println!(
                "  {} {}",
                style("paths.workspace_root:").dim(),
                style(&desired_cfg.paths.workspace_root).dim()
            );
        } else {
            println!(
                "  {} {} {} {}",
                style("paths.workspace_root:").dim(),
                style(&base_cfg.paths.workspace_root).dim(),
                style("->").dim(),
                style(&desired_cfg.paths.workspace_root).green()
            );
        }

        println!("\n{}", style("Provider Auth").bold());
        for (provider_name, provider) in &desired_cfg.providers {
            let old = base_cfg
                .providers
                .get(provider_name)
                .map(|p| p.auth_mode.as_str())
                .unwrap_or("");
            let new = provider.auth_mode.as_str();
            if old == new {
                println!(
                    "  {} {}",
                    style(format!("{provider_name}:")).dim(),
                    style(new).dim()
                );
            } else {
                println!(
                    "  {} {} {} {}",
                    style(format!("{provider_name}:")).dim(),
                    style(old).dim(),
                    style("->").dim(),
                    style(new).green()
                );
            }
        }

        println!("\n{}", style("Secrets").bold());
        if pending_secrets.is_empty() && missing_api_key_secrets.is_empty() {
            println!("  {}", style("no changes").dim());
        } else {
            for item in &pending_secrets {
                println!(
                    "  {} {} {}",
                    style(format!("{}:", item.provider)).dim(),
                    style(if item.overwrite {
                        "overwrite"
                    } else {
                        "create"
                    })
                    .yellow(),
                    style(item.path.display()).dim(),
                );
            }
            for (provider_name, env_key, secrets_file) in &missing_api_key_secrets {
                println!(
                    "  {} {} {}",
                    style(format!("{provider_name}:")).dim(),
                    style("missing").red(),
                    style(format!("{env_key} at {}", secrets_file.display())).dim(),
                );
            }
        }

        println!("\n{}", style("Apply").bold());
        println!(
            "  {}",
            if apply {
                style("yes").green()
            } else {
                style("no").yellow()
            }
        );

        if !warnings.is_empty() {
            println!("\n{}", style("Warnings").bold().yellow());
            for w in &warnings {
                println!("  {}", style(format!("- {w}")).yellow());
            }
        }

        if should_write_config {
            println!(
                "\n{} {}",
                style("Config file:").bold(),
                style(if created_config { "create" } else { "update" }).green()
            );
        } else {
            println!(
                "\n{} {}",
                style("Config file:").bold(),
                style("no changes").dim()
            );
        }

        if dry_run {
            println!();
            println!(
                "{}",
                style("Dry-run: no filesystem changes will be made.").yellow()
            );
            if !missing_api_key_secrets.is_empty() {
                println!("\n{}", style("Manual secrets next steps").bold());
                for (provider_name, env_key, secrets_file) in &missing_api_key_secrets {
                    println!(
                        "\n{} {}:\n{}",
                        style("Provider").dim(),
                        style(format!("'{provider_name}' ({env_key})")).bold(),
                        manual_secrets_instructions(env_key, secrets_file)
                    );
                }
            }
            return Ok(());
        }

        let mut proceed = true;
        if !yes {
            let actions = ["Proceed", "Back", "Abort"];
            let action_idx = Select::with_theme(&theme)
                .with_prompt("Confirm")
                .items(&actions)
                .default(0)
                .interact()?;
            match actions[action_idx] {
                "Proceed" => proceed = true,
                "Back" => proceed = false,
                "Abort" => {
                    println!("\n{}", style("Aborted.").yellow());
                    return Ok(());
                }
                _ => proceed = false,
            }
        }

        if proceed {
            break (candidate_yaml, candidate_cfg, should_write_config);
        }
    };

    if should_write_config {
        write_atomic_text_file_preserving_mode(config_path, &patched_yaml, 0o644)?;
    }

    for item in &pending_secrets {
        write_provider_secrets_file(&item.path, &item.env_key, &item.value, item.overwrite)?;
        wrote_secrets.push(SetupSecretPlan {
            provider: item.provider.clone(),
            env_key: item.env_key.clone(),
            path: item.path.to_string_lossy().to_string(),
            action: if item.overwrite {
                "overwrite".to_string()
            } else {
                "create".to_string()
            },
        });
    }

    if !missing_api_key_secrets.is_empty() {
        println!();
        println!(
            "{}",
            style("Manual secrets next steps (required before `lasso up --provider <name>` will work):")
                .yellow()
                .bold()
        );
        for (provider_name, env_key, secrets_file) in &missing_api_key_secrets {
            println!(
                "\n{} {}:\n{}",
                style("Provider").dim(),
                style(format!("'{provider_name}' ({env_key})")).bold(),
                manual_secrets_instructions(env_key, secrets_file)
            );
        }
    }

    if apply {
        println!();
        println!("{}", style("Applying config...").cyan().bold());
        let _ = apply_config(ctx, &cfg_after_yaml)?;
    }
    println!();
    println!("{}", style("That's it!"));
    println!(
        "{}",
        style("Now go spin up Lasso and start keeping track of your agents.").dim()
    );
    println!(
        "{}",
        style("Start the collector and it will run in the background.").dim()
    );
    println!(
        "{}",
        style("Run codex or cluade through our ```lasso tui ``` command.").dim()
    );

    println!();
    println!("{}", style("Next steps").bold().cyan());
    if !apply {
        println!("  lasso config apply");
    }
    println!("  lasso up --collector-only --wait");
    if let Some(example) = cfg_after_yaml.providers.keys().next() {
        println!("  lasso up --provider {example} --wait");
        println!("  lasso tui --provider {example}");
    } else {
        println!("  lasso up --provider <provider> --wait");
        println!("  lasso tui --provider <provider>");
    }
    println!(
        "  Available providers: {}",
        cfg_after_yaml
            .providers
            .keys()
            .cloned()
            .collect::<Vec<String>>()
            .join(", ")
    );

    Ok(())
}

fn handle_config(ctx: &Context, command: ConfigCommand) -> Result<(), LassoError> {
    match command {
        ConfigCommand::Init => {
            if ctx.config_path.exists() {
                return output(ctx, json!({"path": ctx.config_path, "created": false}));
            }
            ensure_parent(&ctx.config_path)?;
            fs::write(&ctx.config_path, build_default_config_yaml()?)?;
            output(ctx, json!({"path": ctx.config_path, "created": true}))
        }
        ConfigCommand::Edit => {
            if !ctx.config_path.exists() {
                ensure_parent(&ctx.config_path)?;
                fs::write(&ctx.config_path, build_default_config_yaml()?)?;
            }
            let editor = env::var("VISUAL").ok().or_else(|| env::var("EDITOR").ok());
            if let Some(editor) = editor {
                let status = Command::new(editor)
                    .arg(&ctx.config_path)
                    .status()
                    .map_err(|err| {
                        LassoError::Process(format!("failed to launch editor: {err}"))
                    })?;
                if !status.success() {
                    return Err(LassoError::Process("editor exited with error".to_string()));
                }
                output(ctx, json!({"path": ctx.config_path}))
            } else {
                Err(LassoError::Process(
                    "EDITOR is not set; please edit the config file manually".to_string(),
                ))
            }
        }
        ConfigCommand::Validate => {
            let _cfg = read_config(&ctx.config_path)?;
            output(ctx, json!({"path": ctx.config_path, "valid": true}))
        }
        ConfigCommand::Apply => {
            let cfg = match read_config(&ctx.config_path) {
                Ok(cfg) => cfg,
                Err(err) => {
                    return Err(LassoError::Config(format!(
                        "config is invalid. Please edit {} and try again. ({})",
                        ctx.config_path.display(),
                        err
                    )));
                }
            };
            let (log_root, workspace_root) = apply_config(ctx, &cfg)?;
            output(
                ctx,
                json!({"env_file": ctx.env_file, "log_root": log_root, "workspace_root": workspace_root}),
            )
        }
    }
}

fn apply_config(ctx: &Context, cfg: &Config) -> Result<(PathBuf, PathBuf), LassoError> {
    let policy_paths = resolve_config_policy_paths(cfg)?;
    let mut envs = config_to_env(cfg);
    envs.insert(
        "LASSO_LOG_ROOT".to_string(),
        policy_paths.log_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LASSO_WORKSPACE_ROOT".to_string(),
        policy_paths.workspace_root.to_string_lossy().to_string(),
    );
    write_env_file(&ctx.env_file, &envs)?;
    let log_root = policy_paths.log_root;
    fs::create_dir_all(&log_root)?;
    let workspace_root = policy_paths.workspace_root;
    fs::create_dir_all(&workspace_root)?;
    Ok((log_root, workspace_root))
}

fn shell_single_quote(value: &str) -> String {
    // Bash-safe single-quoted string: close/open around escaped single quotes.
    // Example: foo'bar -> 'foo'\''bar'
    let mut out = String::new();
    out.push('\'');
    for ch in value.chars() {
        if ch == '\'' {
            out.push_str("'\\''");
        } else {
            out.push(ch);
        }
    }
    out.push('\'');
    out
}

fn write_atomic_text_file(path: &Path, content: &str, mode: Option<u32>) -> Result<(), LassoError> {
    ensure_parent(path)?;
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let pid = std::process::id();
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    let tmp_path = parent.join(format!(
        ".{}.tmp.{}.{}",
        path.file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| "lasso".to_string()),
        pid,
        ts
    ));

    fs::write(&tmp_path, content)?;
    #[cfg(unix)]
    if let Some(mode) = mode {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&tmp_path, fs::Permissions::from_mode(mode))?;
    }
    fs::rename(&tmp_path, path)?;
    Ok(())
}

fn write_atomic_text_file_preserving_mode(
    path: &Path,
    content: &str,
    default_mode: u32,
) -> Result<(), LassoError> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = fs::metadata(path)
            .map(|m| m.permissions().mode())
            .unwrap_or(default_mode);
        return write_atomic_text_file(path, content, Some(mode));
    }
    #[cfg(not(unix))]
    {
        let _ = default_mode;
        write_atomic_text_file(path, content, None)
    }
}

fn write_provider_secrets_file(
    path: &Path,
    env_key: &str,
    value: &str,
    overwrite_allowed: bool,
) -> Result<(), LassoError> {
    if path.exists() && !overwrite_allowed {
        return Err(LassoError::Process(format!(
            "refusing to overwrite existing secrets file: {}",
            path.display()
        )));
    }
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        // Best-effort tighten perms; if it fails, we still proceed (common on some filesystems).
        let _ = fs::set_permissions(parent, fs::Permissions::from_mode(0o700));
    }

    let env_key = env_key.trim();
    if env_key.is_empty() {
        return Err(LassoError::Config(
            "provider env_key must be non-empty".to_string(),
        ));
    }
    let quoted = shell_single_quote(value);
    let content = format!("{env_key}={quoted}\n");
    write_atomic_text_file(path, &content, Some(0o600))
}

#[derive(Debug, Clone, Default)]
struct SetupYamlEdits {
    log_root: Option<String>,
    workspace_root: Option<String>,
    provider_auth_modes: BTreeMap<String, String>,
}

fn is_blank_or_comment(line: &str) -> bool {
    let trimmed = line.trim();
    trimmed.is_empty() || trimmed.starts_with('#')
}

fn leading_space_count(line: &str) -> Result<usize, LassoError> {
    let mut count = 0usize;
    for ch in line.chars() {
        match ch {
            ' ' => count += 1,
            '\t' => {
                return Err(LassoError::Config(
                    "tabs are not supported in config.yaml indentation".to_string(),
                ))
            }
            _ => break,
        }
    }
    Ok(count)
}

fn match_block_key_line(line: &str, key: &str) -> Result<Option<usize>, LassoError> {
    if is_blank_or_comment(line) {
        return Ok(None);
    }
    let indent = leading_space_count(line)?;
    let rest = &line[indent..];
    if !rest.starts_with(key) {
        return Ok(None);
    }
    let mut idx = key.len();
    while idx < rest.len() && rest.as_bytes()[idx].is_ascii_whitespace() {
        idx += 1;
    }
    if idx >= rest.len() || rest.as_bytes()[idx] != b':' {
        return Ok(None);
    }
    idx += 1;
    while idx < rest.len() && rest.as_bytes()[idx].is_ascii_whitespace() {
        idx += 1;
    }
    if idx >= rest.len() {
        return Ok(Some(indent));
    }
    if rest.as_bytes()[idx] == b'#' {
        return Ok(Some(indent));
    }
    Ok(None)
}

fn match_scalar_key_line(line: &str, key: &str) -> Result<Option<usize>, LassoError> {
    if is_blank_or_comment(line) {
        return Ok(None);
    }
    let indent = leading_space_count(line)?;
    let rest = &line[indent..];
    if !rest.starts_with(key) {
        return Ok(None);
    }
    let mut idx = key.len();
    while idx < rest.len() && rest.as_bytes()[idx].is_ascii_whitespace() {
        idx += 1;
    }
    if idx >= rest.len() || rest.as_bytes()[idx] != b':' {
        return Ok(None);
    }
    Ok(Some(indent))
}

fn find_block_range(
    lines: &[String],
    start: usize,
    key: &str,
    expected_indent: usize,
) -> Result<(usize, usize, usize), LassoError> {
    for (idx, line) in lines.iter().enumerate().skip(start) {
        let Some(indent) = match_block_key_line(line, key)? else {
            continue;
        };
        if indent != expected_indent {
            continue;
        }
        let block_indent = indent;
        let body_start = idx + 1;
        let mut body_end = lines.len();
        for j in body_start..lines.len() {
            let candidate = &lines[j];
            if is_blank_or_comment(candidate) {
                continue;
            }
            let ind = leading_space_count(candidate)?;
            if ind <= block_indent {
                body_end = j;
                break;
            }
        }
        return Ok((idx, body_start, body_end));
    }
    Err(LassoError::Config(format!(
        "could not find YAML mapping block '{key}:' at indent {expected_indent}"
    )))
}

fn is_yaml_indicator(ch: char) -> bool {
    matches!(
        ch,
        '#' | ':'
            | '{'
            | '}'
            | '['
            | ']'
            | ','
            | '&'
            | '*'
            | '!'
            | '|'
            | '>'
            | '\''
            | '"'
            | '%'
            | '@'
            | '`'
    )
}

fn is_safe_plain_yaml_scalar(value: &str) -> bool {
    if value.is_empty() {
        return false;
    }
    if value.chars().any(|c| c == '\n' || c == '\r') {
        return false;
    }
    if value.trim() != value {
        return false;
    }
    if value.chars().next().map(is_yaml_indicator).unwrap_or(true) {
        return false;
    }
    if value.contains(": ") {
        return false;
    }
    if value.contains(" #") || value.contains("\t#") {
        return false;
    }
    true
}

fn format_yaml_scalar_preserving(existing_token: &str, new_value: &str) -> String {
    let token = existing_token.trim();
    if token.len() >= 2 && token.starts_with('\'') && token.ends_with('\'') {
        let inner = new_value.replace('\'', "''");
        return format!("'{inner}'");
    }
    if token.len() >= 2 && token.starts_with('\"') && token.ends_with('\"') {
        let mut inner = String::new();
        for ch in new_value.chars() {
            match ch {
                '\\' => inner.push_str("\\\\"),
                '\"' => inner.push_str("\\\""),
                '\n' => inner.push_str("\\n"),
                '\r' => inner.push_str("\\r"),
                '\t' => inner.push_str("\\t"),
                _ => inner.push(ch),
            }
        }
        return format!("\"{inner}\"");
    }
    if is_safe_plain_yaml_scalar(new_value) {
        return new_value.to_string();
    }
    let mut inner = String::new();
    for ch in new_value.chars() {
        match ch {
            '\\' => inner.push_str("\\\\"),
            '\"' => inner.push_str("\\\""),
            '\n' => inner.push_str("\\n"),
            '\r' => inner.push_str("\\r"),
            '\t' => inner.push_str("\\t"),
            _ => inner.push(ch),
        }
    }
    format!("\"{inner}\"")
}

fn replace_yaml_scalar_value_in_line(
    line: &str,
    key: &str,
    new_value: &str,
) -> Result<(String, bool), LassoError> {
    let indent = leading_space_count(line)?;
    let rest = &line[indent..];
    if !rest.starts_with(key) {
        return Ok((line.to_string(), false));
    }
    let mut idx = key.len();
    while idx < rest.len() && rest.as_bytes()[idx].is_ascii_whitespace() {
        idx += 1;
    }
    if idx >= rest.len() || rest.as_bytes()[idx] != b':' {
        return Ok((line.to_string(), false));
    }
    let colon_idx = indent + idx;
    let mut value_start = colon_idx + 1;
    while value_start < line.len() && line.as_bytes()[value_start].is_ascii_whitespace() {
        value_start += 1;
    }
    if value_start >= line.len() {
        return Err(LassoError::Config(format!(
            "expected scalar value for key '{key}'"
        )));
    }

    // Find comment start outside quotes where '#' is preceded by whitespace.
    let mut in_single = false;
    let mut in_double = false;
    let mut i = value_start;
    let bytes = line.as_bytes();
    let mut comment_start: Option<usize> = None;
    while i < line.len() {
        let ch = bytes[i] as char;
        if in_double {
            if ch == '\\' {
                i = (i + 2).min(line.len());
                continue;
            }
            if ch == '\"' {
                in_double = false;
            }
            i += 1;
            continue;
        }
        if in_single {
            if ch == '\'' {
                if i + 1 < line.len() && bytes[i + 1] as char == '\'' {
                    i += 2;
                    continue;
                }
                in_single = false;
            }
            i += 1;
            continue;
        }
        match ch {
            '\'' => in_single = true,
            '"' => in_double = true,
            '#' => {
                if i == 0 || bytes[i.saturating_sub(1)].is_ascii_whitespace() {
                    comment_start = Some(i);
                    break;
                }
            }
            _ => {}
        }
        i += 1;
    }

    let (pre_comment, comment_part) = if let Some(cs) = comment_start {
        (&line[..cs], &line[cs..])
    } else {
        (line, "")
    };
    let value_with_ws = &pre_comment[value_start..];
    let value_trimmed = value_with_ws.trim_end_matches(|c: char| c.is_ascii_whitespace());
    let trailing_ws = &value_with_ws[value_trimmed.len()..];

    let formatted = format_yaml_scalar_preserving(value_trimmed, new_value);
    let new_line = format!(
        "{}{}{}{}",
        &line[..value_start],
        formatted,
        trailing_ws,
        comment_part
    );
    Ok((new_line.clone(), new_line != line))
}

fn patch_scalar_in_block(
    lines: &mut [String],
    block_body_start: usize,
    block_body_end: usize,
    block_indent: usize,
    key: &str,
    new_value: &str,
) -> Result<bool, LassoError> {
    for idx in block_body_start..block_body_end {
        let line = &lines[idx];
        if is_blank_or_comment(line) {
            continue;
        }
        let indent = leading_space_count(line)?;
        if indent <= block_indent {
            continue;
        }
        if match_scalar_key_line(line, key)?.is_none() {
            continue;
        }
        let (patched, changed) = replace_yaml_scalar_value_in_line(line, key, new_value)?;
        lines[idx] = patched;
        return Ok(changed);
    }
    Err(LassoError::Config(format!(
        "could not find scalar key '{key}:' within YAML block"
    )))
}

fn patch_setup_config_yaml(
    content: &str,
    edits: &SetupYamlEdits,
) -> Result<(String, bool), LassoError> {
    let mut lines: Vec<String> = content.split('\n').map(|s| s.to_string()).collect();
    // `split('\n')` leaves a trailing empty line if the input ends with '\n'. We'll normalize to
    // always end with one newline when writing back.
    if lines.last().map(|s| s.is_empty()).unwrap_or(false) {
        // Keep the trailing empty line as a sentinel and patch within it safely.
    }

    let mut changed = false;

    if edits.log_root.is_some() || edits.workspace_root.is_some() {
        let (_paths_line, paths_body_start, paths_body_end) =
            find_block_range(&lines, 0, "paths", 0)?;
        let paths_indent = 0usize;
        if let Some(value) = edits.log_root.as_deref() {
            changed |= patch_scalar_in_block(
                &mut lines,
                paths_body_start,
                paths_body_end,
                paths_indent,
                "log_root",
                value,
            )?;
        }
        if let Some(value) = edits.workspace_root.as_deref() {
            changed |= patch_scalar_in_block(
                &mut lines,
                paths_body_start,
                paths_body_end,
                paths_indent,
                "workspace_root",
                value,
            )?;
        }
    }

    if !edits.provider_auth_modes.is_empty() {
        let (_providers_line, providers_body_start, providers_body_end) =
            find_block_range(&lines, 0, "providers", 0)?;
        let providers_indent = 0usize;
        for (provider_name, auth_mode) in &edits.provider_auth_modes {
            // Find provider block within providers block.
            let mut provider_line_idx: Option<usize> = None;
            for idx in providers_body_start..providers_body_end {
                let line = &lines[idx];
                let Some(indent) = match_block_key_line(line, provider_name)? else {
                    continue;
                };
                if indent <= providers_indent {
                    continue;
                }
                provider_line_idx = Some(idx);
                break;
            }
            let Some(provider_line_idx) = provider_line_idx else {
                return Err(LassoError::Config(format!(
                    "could not find provider block '{}:' in config.yaml",
                    provider_name
                )));
            };
            let provider_indent = leading_space_count(&lines[provider_line_idx])?;
            let provider_body_start = provider_line_idx + 1;
            let mut provider_body_end = providers_body_end;
            for j in provider_body_start..providers_body_end {
                let candidate = &lines[j];
                if is_blank_or_comment(candidate) {
                    continue;
                }
                let ind = leading_space_count(candidate)?;
                if ind <= provider_indent {
                    provider_body_end = j;
                    break;
                }
            }
            changed |= patch_scalar_in_block(
                &mut lines,
                provider_body_start,
                provider_body_end,
                provider_indent,
                "auth_mode",
                auth_mode,
            )?;
        }
    }

    let mut out = lines.join("\n");
    if !out.ends_with('\n') {
        out.push('\n');
    }
    Ok((out, changed))
}

fn default_install_dir() -> PathBuf {
    let mut base = home_dir().unwrap_or_else(|| PathBuf::from("."));
    base.push(".lasso");
    base
}

fn default_bin_dir() -> PathBuf {
    let mut base = home_dir().unwrap_or_else(|| PathBuf::from("."));
    base.push(".local");
    base.push("bin");
    base
}

#[derive(Debug, Clone)]
struct RuntimePaths {
    config_dir: PathBuf,
    config_path: PathBuf,
    env_file: PathBuf,
    bundle_dir: PathBuf,
    log_root: PathBuf,
    workspace_root: PathBuf,
    install_dir: PathBuf,
    versions_dir: PathBuf,
    current_link: PathBuf,
    bin_dir: PathBuf,
    bin_path: PathBuf,
}

fn resolve_runtime_paths(ctx: &Context) -> Result<(RuntimePaths, bool), LassoError> {
    let config_exists = ctx.config_path.exists();
    let cfg = if config_exists {
        read_config(&ctx.config_path)?
    } else {
        let mut cfg = Config::default();
        cfg.paths = computed_default_paths_for_current_os()?;
        cfg
    };
    let policy_paths = resolve_config_policy_paths(&cfg)?;
    let config_dir = ctx
        .config_path
        .parent()
        .map_or_else(default_config_dir, PathBuf::from);
    let install_dir = default_install_dir();
    let versions_dir = install_dir.join("versions");
    let current_link = install_dir.join("current");
    let bin_dir = default_bin_dir();
    let bin_path = bin_dir.join("lasso");
    Ok((
        RuntimePaths {
            config_dir,
            config_path: ctx.config_path.clone(),
            env_file: ctx.env_file.clone(),
            bundle_dir: ctx.bundle_dir.clone(),
            log_root: policy_paths.log_root,
            workspace_root: policy_paths.workspace_root,
            install_dir,
            versions_dir,
            current_link,
            bin_dir,
            bin_path,
        },
        config_exists,
    ))
}

#[derive(Debug, Clone)]
struct UpdatePlan {
    target_version: String,
    target_version_tag: String,
    bundle_name: String,
    checksum_name: String,
    bundle_url: String,
    checksum_url: String,
    target_dir: PathBuf,
}

#[derive(Debug, Deserialize)]
struct GitHubReleasePayload {
    tag_name: String,
}

fn normalize_version_tag(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.starts_with('v') {
        trimmed.to_string()
    } else {
        format!("v{trimmed}")
    }
}

fn release_platform() -> Result<(String, String), LassoError> {
    let os = match env::consts::OS {
        "macos" => "darwin",
        "linux" => "linux",
        value => {
            return Err(LassoError::Config(format!(
                "unsupported operating system for update: {value}"
            )))
        }
    };
    let arch = match env::consts::ARCH {
        "x86_64" => "amd64",
        "aarch64" => "arm64",
        value => {
            return Err(LassoError::Config(format!(
                "unsupported architecture for update: {value}"
            )))
        }
    };
    Ok((os.to_string(), arch.to_string()))
}

fn release_base_url_root() -> String {
    let raw = env::var("LASSO_RELEASE_BASE_URL")
        .unwrap_or_else(|_| "https://github.com/scottmaran/lasso/releases/download".to_string());
    raw.trim_end_matches('/').to_string()
}

fn build_update_plan(paths: &RuntimePaths, target_version: &str) -> Result<UpdatePlan, LassoError> {
    let target_version_tag = target_version.trim_start_matches('v').to_string();
    let (os, arch) = release_platform()?;
    let bundle_name = format!("lasso_{}_{}_{}.tar.gz", target_version_tag, os, arch);
    let checksum_name = format!("{bundle_name}.sha256");
    let base_url = format!("{}/{target_version}", release_base_url_root());
    Ok(UpdatePlan {
        target_version: target_version.to_string(),
        target_version_tag: target_version_tag.clone(),
        bundle_name: bundle_name.clone(),
        checksum_name: checksum_name.clone(),
        bundle_url: format!("{base_url}/{bundle_name}"),
        checksum_url: format!("{base_url}/{checksum_name}"),
        target_dir: paths.versions_dir.join(target_version_tag),
    })
}

fn read_current_version(paths: &RuntimePaths) -> Option<String> {
    let target = safe_current_target(&paths.current_link, &paths.versions_dir)?;
    let version_tag = target.file_name()?.to_string_lossy().to_string();
    Some(format!("v{version_tag}"))
}

fn parse_version_key(version_tag: &str) -> Option<Vec<u64>> {
    let mut values = Vec::new();
    for part in version_tag.split('.') {
        let value = part.parse::<u64>().ok()?;
        values.push(value);
    }
    if values.is_empty() {
        None
    } else {
        Some(values)
    }
}

fn compare_version_tags(a: &str, b: &str) -> std::cmp::Ordering {
    match (parse_version_key(a), parse_version_key(b)) {
        (Some(left), Some(right)) => left.cmp(&right),
        _ => a.cmp(b),
    }
}

fn list_installed_version_tags(paths: &RuntimePaths) -> Result<Vec<String>, LassoError> {
    if !paths.versions_dir.exists() {
        return Ok(Vec::new());
    }
    let mut versions = Vec::new();
    for entry in fs::read_dir(&paths.versions_dir)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() {
            continue;
        }
        versions.push(entry.file_name().to_string_lossy().to_string());
    }
    versions.sort_by(|a, b| compare_version_tags(a, b));
    Ok(versions)
}

fn select_previous_version(current: &str, installed_tags: &[String]) -> Option<String> {
    let current_tag = current.trim_start_matches('v');
    let mut previous: Option<String> = None;
    for item in installed_tags {
        if item == current_tag {
            break;
        }
        previous = Some(item.clone());
    }
    previous.map(|tag| format!("v{tag}"))
}

fn fetch_latest_release_tag() -> Result<String, LassoError> {
    let url = "https://api.github.com/repos/scottmaran/lasso/releases/latest";
    let client = reqwest::blocking::Client::new();
    let response = client
        .get(url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", "lasso-cli")
        .send()?;
    let status = response.status();
    if !status.is_success() {
        let body = response.text().unwrap_or_default();
        return Err(LassoError::Process(format!(
            "failed to resolve latest release: HTTP {} {}",
            status, body
        )));
    }
    let payload: GitHubReleasePayload = response.json()?;
    Ok(normalize_version_tag(&payload.tag_name))
}

fn download_file(url: &str, path: &Path) -> Result<(), LassoError> {
    let client = reqwest::blocking::Client::new();
    let response = client.get(url).header("User-Agent", "lasso-cli").send()?;
    let status = response.status();
    if !status.is_success() {
        let body = response.text().unwrap_or_default();
        return Err(LassoError::Process(format!(
            "download failed: {} (HTTP {} {})",
            url, status, body
        )));
    }
    let bytes = response.bytes()?;
    ensure_parent(path)?;
    fs::write(path, &bytes)?;
    Ok(())
}

fn parse_checksum(content: &str) -> Option<String> {
    for raw in content.split_whitespace() {
        let candidate = raw
            .trim_matches(|c: char| !c.is_ascii_hexdigit())
            .to_lowercase();
        if candidate.len() == 64 && candidate.chars().all(|c| c.is_ascii_hexdigit()) {
            return Some(candidate);
        }
    }
    None
}

fn sha256_file(path: &Path) -> Result<String, LassoError> {
    let path_str = path.to_string_lossy().to_string();
    let attempts: Vec<(&str, Vec<String>)> = vec![
        (
            "shasum",
            vec!["-a".to_string(), "256".to_string(), path_str.clone()],
        ),
        ("sha256sum", vec![path_str.clone()]),
        (
            "openssl",
            vec!["dgst".to_string(), "-sha256".to_string(), path_str],
        ),
    ];
    for (program, args) in attempts {
        let output = Command::new(program).args(&args).output();
        let Ok(output) = output else { continue };
        if !output.status.success() {
            continue;
        }
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Some(token) = parse_checksum(&stdout) {
            return Ok(token);
        }
    }
    Err(LassoError::Process(
        "no SHA256 tool found (expected shasum, sha256sum, or openssl)".to_string(),
    ))
}

fn verify_bundle_checksum(bundle_path: &Path, checksum_path: &Path) -> Result<(), LassoError> {
    let checksum_content = fs::read_to_string(checksum_path)?;
    let Some(expected) = parse_checksum(&checksum_content) else {
        return Err(LassoError::Process(format!(
            "invalid checksum file: {}",
            checksum_path.display()
        )));
    };
    let actual = sha256_file(bundle_path)?;
    if expected != actual {
        return Err(LassoError::Process(format!(
            "checksum mismatch for {}: expected {}, got {}",
            bundle_path.display(),
            expected,
            actual
        )));
    }
    Ok(())
}

fn normalize_tar_entry_path(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }
    let stripped = trimmed
        .trim_start_matches("./")
        .trim_start_matches('/')
        .trim_end_matches('/');
    if stripped.is_empty() {
        return None;
    }
    Some(stripped.to_string())
}

fn tar_list_entries(bundle_path: &Path) -> Result<Vec<String>, LassoError> {
    let output = Command::new("tar")
        .arg("-tzf")
        .arg(bundle_path)
        .output()
        .map_err(|err| LassoError::Process(format!("failed to run tar: {err}")))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(LassoError::Process(format!(
            "tar listing failed with status {}: {}",
            output.status,
            stderr.trim()
        )));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    Ok(stdout
        .lines()
        .filter_map(normalize_tar_entry_path)
        .collect())
}

fn tar_has_single_top_level_dir(entries: &[String]) -> bool {
    let mut top: Option<&str> = None;
    let mut saw_nested = false;
    for entry in entries {
        let mut parts = entry.splitn(2, '/');
        let first = parts.next().unwrap_or("");
        let rest = parts.next();
        if first.is_empty() {
            continue;
        }
        match rest {
            Some(_) => {
                saw_nested = true;
                match top {
                    None => top = Some(first),
                    Some(existing) => {
                        if existing != first {
                            return false;
                        }
                    }
                }
            }
            None => {
                // Allow only top-level directory marker entries (e.g. "lasso_0.1.0_darwin_arm64").
                if let Some(existing) = top {
                    if existing != first {
                        return false;
                    }
                } else {
                    top = Some(first);
                }
            }
        }
    }
    saw_nested && top.is_some()
}

fn extract_bundle(bundle_path: &Path, destination_dir: &Path) -> Result<(), LassoError> {
    fs::create_dir_all(destination_dir)?;
    let entries = tar_list_entries(bundle_path)?;
    let strip_components = tar_has_single_top_level_dir(&entries);
    let mut cmd = Command::new("tar");
    cmd.arg("-xzf")
        .arg(bundle_path)
        .arg("-C")
        .arg(destination_dir);
    if strip_components {
        cmd.arg("--strip-components").arg("1");
    }
    let status = cmd
        .status()
        .map_err(|err| LassoError::Process(format!("failed to run tar: {err}")))?;
    if !status.success() {
        return Err(LassoError::Process(format!(
            "tar extraction failed with status {status}"
        )));
    }
    Ok(())
}

fn force_symlink(target: &Path, link_path: &Path) -> Result<(), LassoError> {
    ensure_parent(link_path)?;
    match fs::symlink_metadata(link_path) {
        Ok(meta) => {
            if meta.file_type().is_symlink() || meta.file_type().is_file() {
                fs::remove_file(link_path)?;
            } else {
                return Err(LassoError::Process(format!(
                    "refusing to replace directory with symlink: {}",
                    link_path.display()
                )));
            }
        }
        Err(err) if err.kind() == io::ErrorKind::NotFound => {}
        Err(err) => return Err(LassoError::Io(err)),
    }
    #[cfg(unix)]
    {
        symlink(target, link_path)?;
        return Ok(());
    }
    #[allow(unreachable_code)]
    Err(LassoError::Config(
        "update is not supported on this platform".to_string(),
    ))
}

fn temp_download_dir() -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    env::temp_dir().join(format!("lasso-update-{}-{}", std::process::id(), nanos))
}

#[derive(Debug)]
enum LifecycleTarget {
    CollectorOnly,
    Provider(String),
}

#[derive(Debug, Serialize, Default)]
struct ComposeServiceOverride {
    #[serde(skip_serializing_if = "Vec::is_empty")]
    volumes: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    environment: Vec<String>,
}

#[derive(Debug, Serialize, Default)]
struct ComposeRuntimeOverride {
    services: BTreeMap<String, ComposeServiceOverride>,
}

#[derive(Debug)]
struct ProviderRuntimeCompose {
    override_file: PathBuf,
    warnings: Vec<String>,
}

fn configured_compose_files(
    ctx: &Context,
    ui: bool,
    runtime_overrides: &[PathBuf],
) -> Vec<PathBuf> {
    let mut files = if !ctx.compose_file_overrides.is_empty() {
        ctx.compose_file_overrides.clone()
    } else {
        let mut resolved = vec![ctx.bundle_dir.join("compose.yml")];
        if ui {
            resolved.push(ctx.bundle_dir.join("compose.ui.yml"));
        }
        resolved
    };
    files.extend(runtime_overrides.iter().cloned());
    files
}

fn compose_files(
    ctx: &Context,
    ui: bool,
    runtime_overrides: &[PathBuf],
) -> Result<Vec<PathBuf>, LassoError> {
    let files = configured_compose_files(ctx, ui, runtime_overrides);
    for path in &files {
        if !path.exists() {
            return Err(LassoError::Config(format!(
                "missing compose file: {}",
                path.display()
            )));
        }
    }
    Ok(files)
}

fn compose_base_args(
    ctx: &Context,
    cfg: &Config,
    ui: bool,
    runtime_overrides: &[PathBuf],
) -> Result<Vec<String>, LassoError> {
    let files = compose_files(ctx, ui, runtime_overrides)?;
    if !ctx.env_file.exists() {
        let policy_paths = resolve_config_policy_paths(cfg)?;
        let mut envs = config_to_env(cfg);
        envs.insert(
            "LASSO_LOG_ROOT".to_string(),
            policy_paths.log_root.to_string_lossy().to_string(),
        );
        envs.insert(
            "LASSO_WORKSPACE_ROOT".to_string(),
            policy_paths.workspace_root.to_string_lossy().to_string(),
        );
        write_env_file(&ctx.env_file, &envs)?;
    }
    let mut args = vec![
        "compose".to_string(),
        "--env-file".to_string(),
        ctx.env_file.to_string_lossy().to_string(),
    ];
    if !cfg.docker.project_name.trim().is_empty() {
        args.push("-p".to_string());
        args.push(cfg.docker.project_name.clone());
    }
    for file in files {
        args.push("-f".to_string());
        args.push(file.to_string_lossy().to_string());
    }
    Ok(args)
}

fn resolve_lifecycle_target(
    provider: Option<String>,
    collector_only: bool,
) -> Result<LifecycleTarget, LassoError> {
    if collector_only {
        if provider.is_some() {
            return Err(LassoError::Config(
                "--collector-only conflicts with --provider".to_string(),
            ));
        }
        return Ok(LifecycleTarget::CollectorOnly);
    }
    let provider = provider.ok_or_else(|| {
        LassoError::Config("missing required --provider for this command".to_string())
    })?;
    if provider.trim().is_empty() {
        return Err(LassoError::Config(
            "--provider must be non-empty".to_string(),
        ));
    }
    Ok(LifecycleTarget::Provider(provider))
}

fn provider_from_config<'a>(cfg: &'a Config, provider: &str) -> Result<&'a Provider, LassoError> {
    cfg.providers.get(provider).ok_or_else(|| {
        LassoError::Config(format!(
            "provider '{provider}' is not defined in config.providers"
        ))
    })
}

fn active_provider_state_path(log_root: &Path) -> PathBuf {
    log_root.join(".active_provider.json")
}

fn load_active_provider_state(log_root: &Path) -> Result<Option<ActiveProviderState>, LassoError> {
    let state_path = active_provider_state_path(log_root);
    if !state_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&state_path)?;
    let parsed: ActiveProviderState = serde_json::from_str(&content)?;
    Ok(Some(parsed))
}

fn write_active_provider_state(
    log_root: &Path,
    provider: &str,
    auth_mode: &AuthMode,
    run_id: &str,
) -> Result<(), LassoError> {
    fs::create_dir_all(log_root)?;
    let state = ActiveProviderState {
        provider: provider.to_string(),
        auth_mode: auth_mode.as_str().to_string(),
        run_id: run_id.to_string(),
        started_at: Utc::now().to_rfc3339(),
    };
    let path = active_provider_state_path(log_root);
    let tmp_path = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&state)?;
    fs::write(&tmp_path, format!("{body}\n"))?;
    fs::rename(&tmp_path, &path)?;
    Ok(())
}

fn clear_active_provider_state(log_root: &Path) -> Result<(), LassoError> {
    let path = active_provider_state_path(log_root);
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn resolve_host_state_destination(host_path: &Path) -> String {
    if let Some(home) = home_dir() {
        if let Ok(relative) = host_path.strip_prefix(home) {
            let mapped = Path::new("/home/agent").join(relative);
            return mapped.to_string_lossy().to_string();
        }
    }
    if host_path.is_absolute() {
        return host_path.to_string_lossy().to_string();
    }
    Path::new("/home/agent")
        .join(host_path)
        .to_string_lossy()
        .to_string()
}

fn generate_provider_runtime_compose(
    ctx: &Context,
    provider_name: &str,
    provider: &Provider,
) -> Result<ProviderRuntimeCompose, LassoError> {
    let runtime_dir = ctx
        .config_path
        .parent()
        .map(PathBuf::from)
        .unwrap_or_else(default_config_dir)
        .join("runtime");
    fs::create_dir_all(&runtime_dir)?;

    let override_file = runtime_dir.join(format!("compose.provider.{provider_name}.yml"));
    let mut warnings = Vec::new();

    let mut agent = ComposeServiceOverride::default();
    let mut harness = ComposeServiceOverride::default();

    harness
        .environment
        .push(format!("HARNESS_TUI_CMD={}", provider.commands.tui));
    harness.environment.push(format!(
        "HARNESS_RUN_CMD_TEMPLATE={}",
        provider.commands.run_template
    ));

    agent
        .environment
        .push(format!("LASSO_PROVIDER={provider_name}"));
    agent
        .environment
        .push(format!("LASSO_AUTH_MODE={}", provider.auth_mode.as_str()));
    agent.environment.push(format!(
        "LASSO_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE={}",
        if provider.mount_host_state_in_api_mode {
            "true"
        } else {
            "false"
        }
    ));
    agent.environment.push(format!(
        "LASSO_PROVIDER_ENV_KEY={}",
        provider.auth.api_key.env_key
    ));

    let mut host_state_count = 0usize;
    let should_mount_host_state =
        provider.auth_mode == AuthMode::HostState || provider.mount_host_state_in_api_mode;
    if should_mount_host_state {
        for configured in &provider.auth.host_state.paths {
            let host_path = PathBuf::from(expand_path(configured));
            if !host_path.exists() {
                warnings.push(format!(
                    "provider '{provider_name}': host-state path missing, skipping mount: {}",
                    host_path.display()
                ));
                continue;
            }
            let mount_dst = format!("/run/lasso/provider_host_state/{host_state_count}");
            agent
                .volumes
                .push(format!("{}:{}:ro", host_path.to_string_lossy(), mount_dst));
            agent.environment.push(format!(
                "LASSO_PROVIDER_HOST_STATE_SRC_{host_state_count}={mount_dst}"
            ));
            agent.environment.push(format!(
                "LASSO_PROVIDER_HOST_STATE_DST_{host_state_count}={}",
                resolve_host_state_destination(&host_path)
            ));
            host_state_count += 1;
        }
        if host_state_count == 0 {
            warnings.push(format!(
                "provider '{provider_name}': all configured host-state paths are missing"
            ));
        }
    }
    agent.environment.push(format!(
        "LASSO_PROVIDER_HOST_STATE_COUNT={host_state_count}"
    ));

    if provider.auth_mode == AuthMode::ApiKey {
        let secrets_file = PathBuf::from(expand_path(&provider.auth.api_key.secrets_file));
        if !secrets_file.exists() {
            return Err(LassoError::Config(format!(
                "provider '{provider_name}': API secrets file not found: {}",
                secrets_file.display()
            )));
        }
        if !secrets_file.is_file() {
            return Err(LassoError::Config(format!(
                "provider '{provider_name}': API secrets path is not a file: {}",
                secrets_file.display()
            )));
        }
        let container_secrets = "/run/lasso/provider_secrets.env";
        agent.volumes.push(format!(
            "{}:{}:ro",
            secrets_file.to_string_lossy(),
            container_secrets
        ));
        agent
            .environment
            .push(format!("LASSO_PROVIDER_SECRETS_FILE={container_secrets}"));
    } else {
        agent
            .environment
            .push("LASSO_PROVIDER_SECRETS_FILE=".to_string());
    }

    let mut runtime_override = ComposeRuntimeOverride::default();
    runtime_override.services.insert("agent".to_string(), agent);
    runtime_override
        .services
        .insert("harness".to_string(), harness);
    let body = serde_yaml::to_string(&runtime_override)?;
    fs::write(&override_file, body)?;

    Ok(ProviderRuntimeCompose {
        override_file,
        warnings,
    })
}

fn run_id_from_now() -> String {
    format!("lasso__{}", Utc::now().format("%Y_%m_%d_%H_%M_%S"))
}

fn active_run_state_path(log_root: &Path) -> PathBuf {
    log_root.join(".active_run.json")
}

fn load_active_run_state(log_root: &Path) -> Result<Option<ActiveRunState>, LassoError> {
    let state_path = active_run_state_path(log_root);
    if !state_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&state_path)?;
    let parsed: ActiveRunState = serde_json::from_str(&content)?;
    Ok(Some(parsed))
}

fn write_active_run_state(
    log_root: &Path,
    run_id: &str,
    workspace_root: &Path,
) -> Result<(), LassoError> {
    fs::create_dir_all(log_root)?;
    let state = ActiveRunState {
        run_id: run_id.to_string(),
        started_at: Utc::now().to_rfc3339(),
        workspace_root: Some(workspace_root.to_string_lossy().to_string()),
    };
    let path = active_run_state_path(log_root);
    let tmp_path = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&state)?;
    fs::write(&tmp_path, format!("{body}\n"))?;
    fs::rename(&tmp_path, &path)?;
    Ok(())
}

fn clear_active_run_state(log_root: &Path) -> Result<(), LassoError> {
    let path = active_run_state_path(log_root);
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn run_root(log_root: &Path, run_id: &str) -> PathBuf {
    log_root.join(run_id)
}

fn list_run_ids(log_root: &Path) -> Result<Vec<String>, LassoError> {
    let mut run_ids: Vec<String> = Vec::new();
    if !log_root.exists() {
        return Ok(run_ids);
    }
    for entry in fs::read_dir(log_root)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with("lasso__") {
            run_ids.push(name);
        }
    }
    run_ids.sort();
    Ok(run_ids)
}

fn resolve_latest_run_id(log_root: &Path) -> Result<Option<String>, LassoError> {
    let runs = list_run_ids(log_root)?;
    Ok(runs.last().cloned())
}

fn compose_env_for_run(
    run_id: Option<&str>,
    workspace_root: Option<&Path>,
) -> BTreeMap<String, String> {
    let mut envs = BTreeMap::new();
    if let Some(run_id) = run_id {
        envs.insert("LASSO_RUN_ID".to_string(), run_id.to_string());
    }
    if let Some(workspace_root) = workspace_root {
        envs.insert(
            "LASSO_WORKSPACE_ROOT".to_string(),
            workspace_root.to_string_lossy().to_string(),
        );
    }
    envs
}

fn resolve_default_run_id(log_root: &Path) -> Result<String, LassoError> {
    match load_active_run_state(log_root)? {
        Some(state) => {
            if run_root(log_root, &state.run_id).exists() {
                Ok(state.run_id)
            } else {
                clear_active_run_state(log_root)?;
                Err(LassoError::Process(
                    "no active run found; use --run-id or --latest".to_string(),
                ))
            }
        }
        None => Err(LassoError::Process(
            "no active run found; use --run-id or --latest".to_string(),
        )),
    }
}

fn resolve_run_id_from_selector(
    log_root: &Path,
    run_id: Option<&str>,
    latest: bool,
) -> Result<String, LassoError> {
    if let Some(run_id) = run_id {
        if !run_root(log_root, run_id).exists() {
            return Err(LassoError::Process(format!("run not found: {run_id}")));
        }
        return Ok(run_id.to_string());
    }
    if latest {
        return resolve_latest_run_id(log_root)?.ok_or_else(|| {
            LassoError::Process("no run directories found under log root".to_string())
        });
    }
    resolve_default_run_id(log_root)
}

fn validate_workspace_policy(
    workspace_root: &Path,
    home: &Path,
    log_root: &Path,
    field: &str,
) -> Result<(), LassoError> {
    if !path_is_within(workspace_root, home) {
        return Err(LassoError::Config(format!(
            "{field} must be under $HOME (home={}, workspace={})",
            home.display(),
            workspace_root.display()
        )));
    }
    if path_is_within(workspace_root, log_root) || path_is_within(log_root, workspace_root) {
        return Err(LassoError::Config(format!(
            "{field} must not overlap log root (workspace={}, log_root={})",
            workspace_root.display(),
            log_root.display()
        )));
    }
    Ok(())
}

fn resolve_effective_workspace_root(
    cfg: &Config,
    workspace_override: Option<&str>,
) -> Result<PathBuf, LassoError> {
    let policy = resolve_config_policy_paths(cfg)?;
    let mut workspace_root = policy.workspace_root;
    if let Some(raw_override) = workspace_override {
        workspace_root = resolve_policy_path(raw_override, "--workspace", &policy.home)?;
        validate_workspace_policy(
            &workspace_root,
            &policy.home,
            &policy.log_root,
            "--workspace",
        )?;
    }
    Ok(workspace_root)
}

fn resolve_active_run_workspace_root(
    cfg: &Config,
    active_run: &ActiveRunState,
) -> Result<PathBuf, LassoError> {
    let policy = resolve_config_policy_paths(cfg)?;
    if let Some(raw) = active_run.workspace_root.as_deref() {
        let workspace_root = resolve_policy_path(raw, "active run workspace", &policy.home)?;
        validate_workspace_policy(
            &workspace_root,
            &policy.home,
            &policy.log_root,
            "active run workspace",
        )?;
        return Ok(workspace_root);
    }
    Ok(policy.workspace_root)
}

fn resolve_host_start_dir(
    cfg: &Config,
    workspace_root: &Path,
    start_dir: Option<&str>,
) -> Result<PathBuf, LassoError> {
    let policy = resolve_config_policy_paths(cfg)?;
    let host_start_dir = match start_dir {
        Some(raw) => resolve_policy_path(raw, "--start-dir", &policy.home)?,
        None => {
            let cwd = env::current_dir().map_err(|err| {
                LassoError::Process(format!(
                    "failed to resolve current working directory for default --start-dir: {}",
                    err
                ))
            })?;
            canonicalize_policy_path(&cwd, "current working directory")
                .map_err(|err| LassoError::Process(err.to_string()))?
        }
    };
    if !path_is_within(&host_start_dir, workspace_root) {
        return Err(LassoError::Config(format!(
            "--start-dir must be inside workspace (start_dir={}, workspace={})",
            host_start_dir.display(),
            workspace_root.display()
        )));
    }
    Ok(host_start_dir)
}

fn map_host_start_dir_to_container(
    host_start_dir: &Path,
    workspace_root: &Path,
) -> Result<String, LassoError> {
    let relative = host_start_dir.strip_prefix(workspace_root).map_err(|_| {
        LassoError::Config(format!(
            "--start-dir must be inside workspace (start_dir={}, workspace={})",
            host_start_dir.display(),
            workspace_root.display()
        ))
    })?;
    if relative.as_os_str().is_empty() {
        return Ok("/work".to_string());
    }
    Ok(Path::new("/work")
        .join(relative)
        .to_string_lossy()
        .to_string())
}

fn running_services<R: DockerRunner>(
    ctx: &Context,
    runner: &R,
    cfg: &Config,
    ui: bool,
    runtime_overrides: &[PathBuf],
    env_overrides: &BTreeMap<String, String>,
    services: &[&str],
) -> Result<Vec<String>, LassoError> {
    let mut args = compose_base_args(ctx, cfg, ui, runtime_overrides)?;
    args.push("ps".to_string());
    args.push("--status".to_string());
    args.push("running".to_string());
    args.push("--services".to_string());
    for service in services {
        args.push((*service).to_string());
    }
    let output = execute_docker(ctx, runner, &args, env_overrides, true, false)?;
    let text = String::from_utf8_lossy(&output.stdout);
    Ok(text
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(ToString::to_string)
        .collect())
}

fn provider_plane_is_running<R: DockerRunner>(
    ctx: &Context,
    runner: &R,
    cfg: &Config,
    ui: bool,
    env_overrides: &BTreeMap<String, String>,
) -> Result<bool, LassoError> {
    let running = running_services(
        ctx,
        runner,
        cfg,
        ui,
        &[],
        env_overrides,
        &["agent", "harness"],
    )?;
    Ok(running.iter().any(|s| s == "agent") && running.iter().any(|s| s == "harness"))
}

fn collector_is_running<R: DockerRunner>(
    ctx: &Context,
    runner: &R,
    cfg: &Config,
    ui: bool,
    env_overrides: &BTreeMap<String, String>,
) -> Result<bool, LassoError> {
    let running = running_services(ctx, runner, cfg, ui, &[], env_overrides, &["collector"])?;
    Ok(running.iter().any(|s| s == "collector"))
}

fn parse_compose_ps_output(text: &str) -> serde_json::Value {
    match serde_json::from_str(text) {
        Ok(value) => match value {
            // Docker Compose `ps --format json` should generally return an array,
            // but some Compose versions/configs return a single object when the
            // output contains exactly one row. Normalize to an array for stable
            // downstream consumers/tests.
            serde_json::Value::Object(_) => serde_json::Value::Array(vec![value]),
            serde_json::Value::Null => serde_json::Value::Array(Vec::new()),
            _ => value,
        },
        Err(_) => {
            let mut items = Vec::new();
            for line in text.lines() {
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                if let Ok(value) = serde_json::from_str::<serde_json::Value>(line) {
                    items.push(value);
                }
            }
            serde_json::Value::Array(items)
        }
    }
}

fn provider_mismatch_error(active_provider: &str, requested_provider: &str) -> LassoError {
    LassoError::Process(format!(
        "provider mismatch: active provider is '{active_provider}', requested '{requested_provider}'. \
Run `lasso down --provider {active_provider}` first."
    ))
}

fn render_docker_command(args: &[String]) -> String {
    fn shell_quote(part: &str) -> String {
        if part.is_empty() {
            return "\"\"".to_string();
        }
        if part.chars().any(|c| c.is_whitespace()) {
            return format!("\"{}\"", part.replace('"', "\\\""));
        }
        part.to_string()
    }
    let mut parts = Vec::with_capacity(args.len() + 1);
    parts.push("docker".to_string());
    parts.extend(args.iter().map(|arg| shell_quote(arg)));
    parts.join(" ")
}

fn docker_spawn_error_details(err: &io::Error, command: &str) -> ProcessErrorDetails {
    if err.kind() == io::ErrorKind::NotFound {
        return ProcessErrorDetails {
            error_code: "docker_not_found".to_string(),
            hint: Some("Install Docker and ensure `docker` is on your PATH.".to_string()),
            command: Some(command.to_string()),
            raw_stderr: None,
        };
    }
    ProcessErrorDetails {
        error_code: "process_command_failed".to_string(),
        hint: None,
        command: Some(command.to_string()),
        raw_stderr: None,
    }
}

fn classify_docker_command_failure(stderr: &str) -> (String, Option<String>) {
    let lower = stderr.to_lowercase();

    if lower.contains("unknown command: docker compose")
        || lower.contains("is not a docker command")
        || lower.contains("unknown flag: --env-file")
        || lower.contains("unknown shorthand flag: 'f' in -f")
    {
        return (
            "docker_compose_unavailable".to_string(),
            Some(
                "Docker Compose is unavailable. If HOME is overridden, set DOCKER_CONFIG to a directory containing Docker CLI plugins (for example ~/.docker)."
                    .to_string(),
            ),
        );
    }

    if lower.contains("cannot connect to the docker daemon")
        || lower.contains("is the docker daemon running")
        || lower.contains("failed to connect to the docker api")
        || lower.contains("error during connect")
    {
        return (
            "docker_daemon_unreachable".to_string(),
            Some(
                "Docker daemon is unreachable. Start Docker Desktop (or dockerd) and retry."
                    .to_string(),
            ),
        );
    }

    if lower.contains("unknown flag: --wait") || lower.contains("unknown flag: --wait-timeout") {
        return (
            "docker_compose_flag_unsupported".to_string(),
            Some(
                "Your Docker Compose version does not support required flags. Upgrade Docker/Compose and retry."
                    .to_string(),
            ),
        );
    }

    if lower.contains("port is already allocated")
        || lower.contains("bind: address already in use")
        || lower.contains("address already in use")
    {
        return (
            "docker_port_conflict".to_string(),
            Some(
                "A required host port is already in use. Free the conflicting port or update config/overrides."
                    .to_string(),
            ),
        );
    }

    if lower.contains("timed out waiting")
        || lower.contains("timeout waiting")
        || lower.contains("did not become healthy")
        || lower.contains("didn't become healthy")
        || lower.contains("context deadline exceeded")
        || lower.contains("application not healthy")
    {
        return (
            "docker_compose_wait_timeout".to_string(),
            Some(
                "Compose wait timed out. Check `docker compose ps` and `docker compose logs`, then retry with a larger --timeout-sec."
                    .to_string(),
            ),
        );
    }

    if lower.contains("denied")
        || lower.contains("unauthorized")
        || lower.contains("authentication")
    {
        return (
            "docker_registry_auth".to_string(),
            Some("Authenticate with `docker login ghcr.io` for private images.".to_string()),
        );
    }

    ("process_command_failed".to_string(), None)
}

fn execute_docker<R: DockerRunner>(
    ctx: &Context,
    runner: &R,
    args: &[String],
    env_overrides: &BTreeMap<String, String>,
    capture_output: bool,
    passthrough_stdout: bool,
) -> Result<CommandOutput, LassoError> {
    let command = render_docker_command(args);
    let cmd_output = runner
        .run(args, &ctx.bundle_dir, env_overrides, capture_output)
        .map_err(|err| {
            let details = docker_spawn_error_details(&err, &command);
            LassoError::ProcessDetailed {
                message: format!("failed to run command `{command}`: {err}"),
                details,
            }
        })?;
    if !cmd_output.success() {
        let stderr = String::from_utf8_lossy(&cmd_output.stderr)
            .trim()
            .to_string();
        let (error_code, hint) = classify_docker_command_failure(&stderr);
        let mut message = format!(
            "command failed with status {} while running `{}`",
            cmd_output.status_code, command
        );
        if !stderr.is_empty() {
            message = format!("{message}: {stderr}");
        }
        if let Some(ref hint_message) = hint {
            message = format!("{message}\nHint: {hint_message}");
        }
        return Err(LassoError::ProcessDetailed {
            message,
            details: ProcessErrorDetails {
                error_code,
                hint,
                command: Some(command),
                raw_stderr: if stderr.is_empty() {
                    None
                } else {
                    Some(stderr)
                },
            },
        });
    }
    if capture_output && passthrough_stdout && !cmd_output.stdout.is_empty() && !ctx.json {
        let stdout = String::from_utf8_lossy(&cmd_output.stdout);
        print!("{stdout}");
    }
    Ok(cmd_output)
}

fn run_docker_command<R: DockerRunner>(
    ctx: &Context,
    runner: &R,
    args: &[String],
    env_overrides: &BTreeMap<String, String>,
    json_payload: serde_json::Value,
    capture_output: bool,
) -> Result<(), LassoError> {
    let _ = execute_docker(ctx, runner, args, env_overrides, capture_output, true)?;
    output(ctx, json_payload)
}

fn handle_up<R: DockerRunner>(
    ctx: &Context,
    provider: Option<String>,
    collector_only: bool,
    workspace: Option<String>,
    ui: bool,
    pull: Option<String>,
    wait: bool,
    timeout_sec: Option<u64>,
    runner: &R,
) -> Result<(), LassoError> {
    if timeout_sec.is_some() && !wait {
        return Err(LassoError::Config(
            "--timeout-sec requires --wait".to_string(),
        ));
    }
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let target = resolve_lifecycle_target(provider, collector_only)?;

    match target {
        LifecycleTarget::CollectorOnly => {
            let effective_workspace = resolve_effective_workspace_root(&cfg, workspace.as_deref())?;
            let preflight_env = compose_env_for_run(None, Some(&effective_workspace));
            if provider_plane_is_running(ctx, runner, &cfg, ui, &preflight_env)? {
                return Err(LassoError::Process(
                    "provider plane is still running; stop it before starting a new collector run"
                        .to_string(),
                ));
            }
            if collector_is_running(ctx, runner, &cfg, ui, &preflight_env)? {
                return Err(LassoError::Process(
                    "collector is already running".to_string(),
                ));
            }
            let run_id = run_id_from_now();
            fs::create_dir_all(run_root(&log_root, &run_id))?;
            write_active_run_state(&log_root, &run_id, &effective_workspace)?;

            let mut args = compose_base_args(ctx, &cfg, ui, &[])?;
            args.push("up".to_string());
            args.push("-d".to_string());
            if let Some(pull) = pull {
                args.push("--pull".to_string());
                args.push(pull);
            }
            if wait {
                args.push("--wait".to_string());
                if let Some(timeout_sec) = timeout_sec {
                    args.push("--wait-timeout".to_string());
                    args.push(timeout_sec.to_string());
                }
            }
            args.push("collector".to_string());
            let env_overrides = compose_env_for_run(Some(&run_id), Some(&effective_workspace));
            let result = run_docker_command(
                ctx,
                runner,
                &args,
                &env_overrides,
                json!({
                    "action": "up",
                    "collector_only": true,
                    "run_id": run_id,
                    "workspace_root": effective_workspace,
                }),
                true,
            );
            if result.is_err() {
                let _ = clear_active_run_state(&log_root);
            }
            result
        }
        LifecycleTarget::Provider(provider_name) => {
            let provider_cfg = provider_from_config(&cfg, &provider_name)?;
            let active_run = load_active_run_state(&log_root)?.ok_or_else(|| {
                LassoError::Process(
                    "no active run found; start collector first with `lasso up --collector-only`"
                        .to_string(),
                )
            })?;
            let active_workspace = resolve_active_run_workspace_root(&cfg, &active_run)?;
            if let Some(raw_workspace) = workspace.as_deref() {
                let requested_workspace =
                    resolve_effective_workspace_root(&cfg, Some(raw_workspace))?;
                if requested_workspace != active_workspace {
                    return Err(LassoError::Config(format!(
                        "--workspace must match active run workspace (active={}, requested={})",
                        active_workspace.display(),
                        requested_workspace.display()
                    )));
                }
            }
            if !run_root(&log_root, &active_run.run_id).exists() {
                clear_active_run_state(&log_root)?;
                return Err(LassoError::Process(
                    "active run metadata points to a missing run directory; restart collector with `lasso up --collector-only`"
                        .to_string(),
                ));
            }
            let run_env = compose_env_for_run(Some(&active_run.run_id), Some(&active_workspace));
            if !collector_is_running(ctx, runner, &cfg, ui, &run_env)? {
                return Err(LassoError::Process(
                    "collector is not running; start it first with `lasso up --collector-only`"
                        .to_string(),
                ));
            }
            if let Some(active_provider) = load_active_provider_state(&log_root)? {
                if active_provider.provider != provider_name {
                    return Err(provider_mismatch_error(
                        &active_provider.provider,
                        &provider_name,
                    ));
                }
            }
            if provider_plane_is_running(ctx, runner, &cfg, ui, &run_env)? {
                return Err(LassoError::Process(format!(
                    "provider plane is already running for '{}'",
                    provider_name
                )));
            }

            let runtime = generate_provider_runtime_compose(ctx, &provider_name, provider_cfg)?;
            for warning in &runtime.warnings {
                eprintln!("warning: {warning}");
            }

            let mut args = compose_base_args(ctx, &cfg, ui, &[runtime.override_file.clone()])?;
            args.push("up".to_string());
            args.push("-d".to_string());
            if let Some(pull) = pull {
                args.push("--pull".to_string());
                args.push(pull);
            }
            if wait {
                args.push("--wait".to_string());
                if let Some(timeout_sec) = timeout_sec {
                    args.push("--wait-timeout".to_string());
                    args.push(timeout_sec.to_string());
                }
            }
            args.push("agent".to_string());
            args.push("harness".to_string());

            let result = run_docker_command(
                ctx,
                runner,
                &args,
                &run_env,
                json!({
                    "action": "up",
                    "collector_only": false,
                    "provider": provider_name,
                    "run_id": active_run.run_id,
                    "auth_mode": provider_cfg.auth_mode.as_str(),
                    "workspace_root": active_workspace,
                }),
                true,
            );
            if result.is_ok() {
                write_active_provider_state(
                    &log_root,
                    &provider_name,
                    &provider_cfg.auth_mode,
                    &active_run.run_id,
                )?;
            }
            result
        }
    }
}

fn handle_down<R: DockerRunner>(
    ctx: &Context,
    provider: Option<String>,
    collector_only: bool,
    ui: bool,
    runner: &R,
) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let target = resolve_lifecycle_target(provider, collector_only)?;
    let active_run = load_active_run_state(&log_root)?;
    let run_id = active_run.as_ref().map(|state| state.run_id.clone());
    let workspace_root = active_run
        .as_ref()
        .map(|state| resolve_active_run_workspace_root(&cfg, state))
        .transpose()?;
    let env_overrides = compose_env_for_run(run_id.as_deref(), workspace_root.as_deref());

    match target {
        LifecycleTarget::CollectorOnly => {
            let mut args = compose_base_args(ctx, &cfg, ui, &[])?;
            args.push("stop".to_string());
            args.push("collector".to_string());
            run_docker_command(
                ctx,
                runner,
                &args,
                &env_overrides,
                json!({"action": "down", "collector_only": true, "run_id": run_id}),
                true,
            )
        }
        LifecycleTarget::Provider(provider_name) => {
            let _provider_cfg = provider_from_config(&cfg, &provider_name)?;
            if let Some(active_provider) = load_active_provider_state(&log_root)? {
                if active_provider.provider != provider_name {
                    return Err(provider_mismatch_error(
                        &active_provider.provider,
                        &provider_name,
                    ));
                }
            }
            let mut args = compose_base_args(ctx, &cfg, ui, &[])?;
            args.push("stop".to_string());
            args.push("agent".to_string());
            args.push("harness".to_string());
            let result = run_docker_command(
                ctx,
                runner,
                &args,
                &env_overrides,
                json!({"action": "down", "collector_only": false, "provider": provider_name, "run_id": run_id}),
                true,
            );
            if result.is_ok() {
                clear_active_provider_state(&log_root)?;
            }
            result
        }
    }
}

fn handle_status<R: DockerRunner>(
    ctx: &Context,
    provider: Option<String>,
    collector_only: bool,
    ui: bool,
    runner: &R,
) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let active_run = load_active_run_state(&log_root)?;
    let run_id = active_run.as_ref().map(|state| state.run_id.clone());
    let workspace_root = active_run
        .as_ref()
        .map(|state| resolve_active_run_workspace_root(&cfg, state))
        .transpose()?;
    let env_overrides = compose_env_for_run(run_id.as_deref(), workspace_root.as_deref());
    let target = resolve_lifecycle_target(provider, collector_only)?;

    let mut args = compose_base_args(ctx, &cfg, ui, &[])?;
    args.push("ps".to_string());
    args.push("--format".to_string());
    args.push("json".to_string());
    match target {
        LifecycleTarget::CollectorOnly => {
            args.push("collector".to_string());
        }
        LifecycleTarget::Provider(provider_name) => {
            let _provider_cfg = provider_from_config(&cfg, &provider_name)?;
            if let Some(active_provider) = load_active_provider_state(&log_root)? {
                if active_provider.provider != provider_name {
                    return Err(provider_mismatch_error(
                        &active_provider.provider,
                        &provider_name,
                    ));
                }
            }
            args.push("agent".to_string());
            args.push("harness".to_string());
        }
    }

    let cmd_output = execute_docker(ctx, runner, &args, &env_overrides, true, false)?;
    let text = String::from_utf8_lossy(&cmd_output.stdout);
    let rows = parse_compose_ps_output(&text);
    if ctx.json {
        let payload = JsonResult {
            ok: true,
            result: Some(rows),
            error: None,
            error_details: None,
        };
        print_json(&payload)?;
        return Ok(());
    }
    if rows.as_array().map(|a| a.is_empty()).unwrap_or(true) {
        println!("No containers running.");
    } else {
        println!("{}", text.trim());
    }
    Ok(())
}

fn handle_run(
    ctx: &Context,
    provider: String,
    prompt: String,
    capture_input: Option<bool>,
    start_dir: Option<String>,
    timeout_sec: Option<u64>,
    env_list: Vec<String>,
) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let _provider_cfg = provider_from_config(&cfg, &provider)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let active_provider = load_active_provider_state(&log_root)?.ok_or_else(|| {
        LassoError::Process(
            "no active provider plane found; start one with `lasso up --provider <name>`"
                .to_string(),
        )
    })?;
    if active_provider.provider != provider {
        return Err(provider_mismatch_error(
            &active_provider.provider,
            &provider,
        ));
    }
    let active_run = load_active_run_state(&log_root)?.ok_or_else(|| {
        LassoError::Process(
            "no active run metadata found; restart collector with `lasso up --collector-only`"
                .to_string(),
        )
    })?;
    if active_run.run_id != active_provider.run_id {
        return Err(LassoError::Process(format!(
            "active run mismatch (collector run_id={}, provider run_id={}); restart provider plane",
            active_run.run_id, active_provider.run_id
        )));
    }
    let workspace_root = resolve_active_run_workspace_root(&cfg, &active_run)?;
    let host_start_dir = resolve_host_start_dir(&cfg, &workspace_root, start_dir.as_deref())?;
    let container_start_dir = map_host_start_dir_to_container(&host_start_dir, &workspace_root)?;

    let token = resolve_token(&cfg)?;
    let mut env_map = BTreeMap::new();
    for entry in env_list {
        if let Some((key, value)) = entry.split_once('=') {
            env_map.insert(key.to_string(), value.to_string());
        }
    }
    let payload = json!({
        "prompt": prompt,
        "capture_input": capture_input.unwrap_or(true),
        "cwd": container_start_dir,
        "timeout_sec": timeout_sec,
        "env": env_map,
    });
    let url = format!(
        "http://{}:{}/run",
        cfg.harness.api_host, cfg.harness.api_port
    );
    let client = reqwest::blocking::Client::new();
    let response = client
        .post(&url)
        .header("X-Harness-Token", token)
        .json(&payload)
        .send()?;
    let status = response.status();
    let body = response.text()?;
    if !status.is_success() {
        return Err(LassoError::Process(format!(
            "run failed: HTTP {}: {}",
            status, body
        )));
    }
    if ctx.json {
        let payload: serde_json::Value =
            serde_json::from_str(&body).unwrap_or(json!({"raw": body}));
        let wrapper = JsonResult {
            ok: true,
            result: Some(payload),
            error: None,
            error_details: None,
        };
        print_json(&wrapper)?;
    } else {
        println!("{}", body.trim());
    }
    Ok(())
}

fn handle_tui<R: DockerRunner>(
    ctx: &Context,
    provider: String,
    start_dir: Option<String>,
    runner: &R,
) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let provider_cfg = provider_from_config(&cfg, &provider)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let active_provider = load_active_provider_state(&log_root)?.ok_or_else(|| {
        LassoError::Process(
            "no active provider plane found; start one with `lasso up --provider <name>`"
                .to_string(),
        )
    })?;
    if active_provider.provider != provider {
        return Err(provider_mismatch_error(
            &active_provider.provider,
            &provider,
        ));
    }
    let active_run = load_active_run_state(&log_root)?.ok_or_else(|| {
        LassoError::Process(
            "no active run metadata found; restart collector with `lasso up --collector-only`"
                .to_string(),
        )
    })?;
    if active_run.run_id != active_provider.run_id {
        return Err(LassoError::Process(format!(
            "active run mismatch (collector run_id={}, provider run_id={}); restart provider plane",
            active_run.run_id, active_provider.run_id
        )));
    }
    let workspace_root = resolve_active_run_workspace_root(&cfg, &active_run)?;
    let host_start_dir = resolve_host_start_dir(&cfg, &workspace_root, start_dir.as_deref())?;
    let container_start_dir = map_host_start_dir_to_container(&host_start_dir, &workspace_root)?;

    let runtime = generate_provider_runtime_compose(ctx, &provider, provider_cfg)?;
    for warning in &runtime.warnings {
        eprintln!("warning: {warning}");
    }
    let mut args = compose_base_args(ctx, &cfg, false, &[runtime.override_file.clone()])?;
    args.push("run".to_string());
    args.push("--rm".to_string());
    args.push("-e".to_string());
    args.push("HARNESS_MODE=tui".to_string());
    args.push("-e".to_string());
    args.push(format!("HARNESS_AGENT_WORKDIR={container_start_dir}"));
    args.push("harness".to_string());
    let env_overrides = compose_env_for_run(Some(&active_provider.run_id), Some(&workspace_root));
    if !provider_plane_is_running(ctx, runner, &cfg, false, &env_overrides)? {
        return Err(LassoError::Process(format!(
            "provider plane for '{provider}' is not running; start it with `lasso up --provider {provider}`"
        )));
    }
    run_docker_command(
        ctx,
        runner,
        &args,
        &env_overrides,
        json!({"action": "tui", "provider": provider, "run_id": active_provider.run_id}),
        false,
    )
}

fn handle_jobs(ctx: &Context, command: JobsCommand) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    match command {
        JobsCommand::List { run_id, latest } => {
            let run_id = resolve_run_id_from_selector(&log_root, run_id.as_deref(), latest)?;
            let jobs_dir = run_root(&log_root, &run_id).join("harness").join("jobs");
            let mut jobs = Vec::new();
            if jobs_dir.exists() {
                for entry in fs::read_dir(jobs_dir)? {
                    let entry = entry?;
                    if entry.file_type()?.is_dir() {
                        jobs.push(entry.file_name().to_string_lossy().to_string());
                    }
                }
            }
            jobs.sort();
            output(ctx, json!({"run_id": run_id, "jobs": jobs}))
        }
        JobsCommand::Get { id, run_id, latest } => {
            let run_id = resolve_run_id_from_selector(&log_root, run_id.as_deref(), latest)?;
            let jobs_dir = run_root(&log_root, &run_id).join("harness").join("jobs");
            let status_path = jobs_dir.join(&id).join("status.json");
            if !status_path.exists() {
                return Err(LassoError::Process(format!("job not found: {id}")));
            }
            let content = fs::read_to_string(status_path)?;
            let data: serde_json::Value =
                serde_json::from_str(&content).unwrap_or(json!({"raw": content}));
            output(ctx, json!({"run_id": run_id, "job": data}))
        }
    }
}

fn handle_doctor(ctx: &Context) -> Result<(), LassoError> {
    let mut checks = BTreeMap::new();
    let docker_present = which::which("docker").is_ok();
    let docker_ok = if docker_present {
        let output = Command::new("docker")
            .arg("info")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        output.map(|s| s.success()).unwrap_or(false)
    } else {
        false
    };
    let docker_compose_ok = if docker_present {
        let output = Command::new("docker")
            .arg("compose")
            .arg("version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        output.map(|s| s.success()).unwrap_or(false)
    } else {
        false
    };
    checks.insert("docker".to_string(), docker_ok);
    checks.insert("docker_compose".to_string(), docker_compose_ok);

    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let log_ok = host_dir_writable(&log_root);
    checks.insert("log_root_writable".to_string(), log_ok);
    let ok = docker_ok && docker_compose_ok && log_ok;
    let error = if ok {
        None
    } else if !docker_ok && !docker_compose_ok {
        Some("docker is not available; docker compose is not available".to_string())
    } else if !docker_ok {
        Some("docker is not available".to_string())
    } else if !docker_compose_ok {
        Some("docker compose is not available".to_string())
    } else {
        Some("log root is not writable".to_string())
    };

    if ctx.json {
        let payload = JsonResult {
            ok,
            result: Some(json!({ "checks": checks })),
            error,
            error_details: None,
        };
        print_json(&payload)?;
        return Ok(());
    }

    println!(
        "Docker: {}",
        if docker_ok {
            "ok"
        } else {
            "missing or not running"
        }
    );
    println!(
        "Docker Compose: {}",
        if docker_compose_ok {
            "ok"
        } else {
            "missing or not running"
        }
    );
    println!(
        "Log root: {}",
        if log_ok { "writable" } else { "not writable" }
    );
    if !docker_ok {
        return Err(LassoError::Process("docker is not available".to_string()));
    }
    if !docker_compose_ok {
        return Err(LassoError::Process(
            "docker compose is not available".to_string(),
        ));
    }
    if !log_ok {
        return Err(LassoError::Process("log root is not writable".to_string()));
    }
    Ok(())
}

fn handle_paths(ctx: &Context) -> Result<(), LassoError> {
    let (paths, config_exists) = resolve_runtime_paths(ctx)?;
    let env_exists = paths.env_file.exists();
    let compose_files: Vec<String> = configured_compose_files(ctx, false, &[])
        .into_iter()
        .map(|p| p.to_string_lossy().to_string())
        .collect();
    output(
        ctx,
        json!({
            "config_exists": config_exists,
            "env_file_exists": env_exists,
            "config_dir": paths.config_dir,
            "config_path": paths.config_path,
            "env_file": paths.env_file,
            "bundle_dir": paths.bundle_dir,
            "compose_files": compose_files,
            "log_root": paths.log_root,
            "workspace_root": paths.workspace_root,
            "install_dir": paths.install_dir,
            "versions_dir": paths.versions_dir,
            "current_link": paths.current_link,
            "bin_dir": paths.bin_dir,
            "bin_path": paths.bin_path,
        }),
    )
}

fn handle_update(ctx: &Context, command: UpdateCommand) -> Result<(), LassoError> {
    match command {
        UpdateCommand::Check => update_check(ctx),
        UpdateCommand::Apply {
            to,
            latest,
            yes,
            dry_run,
        } => update_apply(ctx, to, latest, yes, dry_run),
        UpdateCommand::Rollback {
            to,
            previous,
            yes,
            dry_run,
        } => update_rollback(ctx, to, previous, yes, dry_run),
    }
}

fn update_check(ctx: &Context) -> Result<(), LassoError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    let current_version = read_current_version(&paths);
    let latest_version = fetch_latest_release_tag()?;
    let up_to_date = current_version.as_deref() == Some(latest_version.as_str());
    output(
        ctx,
        json!({
            "current_version": current_version,
            "latest_version": latest_version,
            "up_to_date": up_to_date,
        }),
    )
}

fn update_apply(
    ctx: &Context,
    to: Option<String>,
    latest: bool,
    yes: bool,
    dry_run: bool,
) -> Result<(), LassoError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    let current_version = read_current_version(&paths);
    let target_version = match to {
        Some(value) => normalize_version_tag(&value),
        None => {
            let _ = latest;
            fetch_latest_release_tag()?
        }
    };
    let plan = build_update_plan(&paths, &target_version)?;
    let already_current = current_version.as_deref() == Some(target_version.as_str());
    if dry_run {
        return output(
            ctx,
            json!({
                "action": "update_apply",
                "dry_run": true,
                "current_version": current_version,
                "target_version": plan.target_version,
                "target_version_tag": plan.target_version_tag,
                "already_current": already_current,
                "bundle_url": plan.bundle_url,
                "checksum_url": plan.checksum_url,
                "target_dir": plan.target_dir,
                "current_link": paths.current_link,
                "bin_path": paths.bin_path,
            }),
        );
    }
    if !yes {
        return Err(LassoError::Config(
            "update apply requires --yes (or use --dry-run to preview)".to_string(),
        ));
    }
    if already_current {
        return output(
            ctx,
            json!({
                "action": "update_apply",
                "updated": false,
                "reason": "already_current",
                "current_version": current_version,
                "target_version": target_version,
            }),
        );
    }

    let download_dir = temp_download_dir();
    fs::create_dir_all(&download_dir)?;
    let bundle_path = download_dir.join(&plan.bundle_name);
    let checksum_path = download_dir.join(&plan.checksum_name);

    let update_result = (|| -> Result<(), LassoError> {
        download_file(&plan.bundle_url, &bundle_path)?;
        download_file(&plan.checksum_url, &checksum_path)?;
        verify_bundle_checksum(&bundle_path, &checksum_path)?;
        if plan.target_dir.exists() {
            fs::remove_dir_all(&plan.target_dir)?;
        }
        extract_bundle(&bundle_path, &plan.target_dir)?;
        let lasso_binary = plan.target_dir.join("lasso");
        if !lasso_binary.exists() {
            return Err(LassoError::Process(format!(
                "bundle did not contain expected binary: {}",
                lasso_binary.display()
            )));
        }
        fs::create_dir_all(&paths.install_dir)?;
        fs::create_dir_all(&paths.bin_dir)?;
        force_symlink(&plan.target_dir, &paths.current_link)?;
        force_symlink(&paths.current_link.join("lasso"), &paths.bin_path)?;
        Ok(())
    })();
    let _ = fs::remove_dir_all(&download_dir);
    update_result?;

    output(
        ctx,
        json!({
            "action": "update_apply",
            "updated": true,
            "from_version": current_version,
            "to_version": target_version,
            "target_dir": plan.target_dir,
            "bin_path": paths.bin_path,
        }),
    )
}

fn update_rollback(
    ctx: &Context,
    to: Option<String>,
    previous: bool,
    yes: bool,
    dry_run: bool,
) -> Result<(), LassoError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    let current_version = read_current_version(&paths);
    let installed_tags = list_installed_version_tags(&paths)?;
    if installed_tags.is_empty() {
        return Err(LassoError::Process(
            "no installed versions found under install directory".to_string(),
        ));
    }
    let target_version = match to {
        Some(value) => normalize_version_tag(&value),
        None => {
            let _ = previous;
            let Some(current) = current_version.as_deref() else {
                return Err(LassoError::Process(
                    "cannot infer rollback target: current version is not set".to_string(),
                ));
            };
            let Some(prev) = select_previous_version(current, &installed_tags) else {
                return Err(LassoError::Process(
                    "no previous installed version available for rollback".to_string(),
                ));
            };
            prev
        }
    };
    let target_tag = target_version.trim_start_matches('v');
    let target_dir = paths.versions_dir.join(target_tag);
    if !target_dir.exists() {
        return Err(LassoError::Process(format!(
            "rollback target is not installed: {}",
            target_version
        )));
    }
    if dry_run {
        return output(
            ctx,
            json!({
                "action": "update_rollback",
                "dry_run": true,
                "current_version": current_version,
                "target_version": target_version,
                "target_dir": target_dir,
            }),
        );
    }
    if !yes {
        return Err(LassoError::Config(
            "update rollback requires --yes (or use --dry-run to preview)".to_string(),
        ));
    }
    if current_version.as_deref() == Some(target_version.as_str()) {
        return output(
            ctx,
            json!({
                "action": "update_rollback",
                "updated": false,
                "reason": "already_current",
                "current_version": current_version,
                "target_version": target_version,
            }),
        );
    }
    fs::create_dir_all(&paths.install_dir)?;
    fs::create_dir_all(&paths.bin_dir)?;
    force_symlink(&target_dir, &paths.current_link)?;
    force_symlink(&paths.current_link.join("lasso"), &paths.bin_path)?;
    output(
        ctx,
        json!({
            "action": "update_rollback",
            "updated": true,
            "from_version": current_version,
            "to_version": target_version,
            "target_dir": target_dir,
        }),
    )
}

fn safe_current_target(current_link: &Path, versions_dir: &Path) -> Option<PathBuf> {
    let target = fs::read_link(current_link).ok()?;
    let resolved = if target.is_absolute() {
        target
    } else {
        current_link.parent()?.join(target)
    };
    if resolved.starts_with(versions_dir) {
        Some(resolved)
    } else {
        None
    }
}

fn path_exists(path: &Path) -> bool {
    fs::symlink_metadata(path).is_ok()
}

fn remove_path(path: &Path) -> Result<bool, LassoError> {
    let meta = match fs::symlink_metadata(path) {
        Ok(meta) => meta,
        Err(err) if err.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(err) => return Err(LassoError::Io(err)),
    };
    let file_type = meta.file_type();
    if file_type.is_symlink() || file_type.is_file() {
        fs::remove_file(path)?;
    } else if file_type.is_dir() {
        fs::remove_dir_all(path)?;
    } else {
        fs::remove_file(path)?;
    }
    Ok(true)
}

fn prune_empty_dir(path: &Path) {
    let _ = fs::remove_dir(path);
}

fn handle_uninstall<R: DockerRunner>(
    ctx: &Context,
    remove_config: bool,
    all_versions: bool,
    yes: bool,
    dry_run: bool,
    force: bool,
    runner: &R,
) -> Result<(), LassoError> {
    if !dry_run && !yes {
        return Err(LassoError::Config(
            "uninstall requires --yes (or use --dry-run to preview)".to_string(),
        ));
    }
    let config_dir = ctx
        .config_path
        .parent()
        .map_or_else(default_config_dir, PathBuf::from);
    let install_dir = default_install_dir();
    let versions_dir = install_dir.join("versions");
    let current_link = install_dir.join("current");
    let bin_dir = default_bin_dir();
    let bin_path = bin_dir.join("lasso");

    let mut warnings: Vec<String> = Vec::new();
    let mut down_attempted = false;
    let down_skipped = force || dry_run;
    if !force && !dry_run {
        if !ctx.env_file.exists() {
            warnings.push(format!(
                "skipping stack shutdown: env file missing at {}",
                ctx.env_file.display()
            ));
        } else {
            let files = configured_compose_files(ctx, false, &[]);
            let mut missing_files: Vec<String> = Vec::new();
            for path in &files {
                if !path.exists() {
                    missing_files.push(path.to_string_lossy().to_string());
                }
            }
            if !missing_files.is_empty() {
                warnings.push(format!(
                    "skipping stack shutdown: missing compose files: {}",
                    missing_files.join(", ")
                ));
            } else {
                down_attempted = true;
                let project_name = match read_config(&ctx.config_path) {
                    Ok(cfg) => cfg.docker.project_name,
                    Err(err) => {
                        warnings.push(format!(
                            "unable to read config for compose project name; proceeding without -p ({})",
                            err
                        ));
                        String::new()
                    }
                };

                let mut down_args = vec![
                    "compose".to_string(),
                    "--env-file".to_string(),
                    ctx.env_file.to_string_lossy().to_string(),
                ];
                if !project_name.trim().is_empty() {
                    down_args.push("-p".to_string());
                    down_args.push(project_name);
                }
                for file in files {
                    down_args.push("-f".to_string());
                    down_args.push(file.to_string_lossy().to_string());
                }
                down_args.push("down".to_string());
                down_args.push("--volumes".to_string());
                down_args.push("--remove-orphans".to_string());

                if let Err(err) =
                    execute_docker(ctx, runner, &down_args, &BTreeMap::new(), true, false)
                {
                    warnings.push(format!(
                        "failed to stop stack before uninstall (containers may still be running): {}",
                        err
                    ));
                }
            }
        }
    }

    let mut targets: Vec<PathBuf> = Vec::new();
    if all_versions {
        targets.push(versions_dir.clone());
    } else if let Some(current_target) = safe_current_target(&current_link, &versions_dir) {
        targets.push(current_target);
    }
    targets.push(current_link.clone());
    targets.push(bin_path.clone());
    if remove_config {
        targets.push(ctx.env_file.clone());
        targets.push(ctx.config_path.clone());
    }

    let mut dedup: BTreeMap<String, PathBuf> = BTreeMap::new();
    for path in targets {
        dedup.insert(path.to_string_lossy().to_string(), path);
    }
    let targets: Vec<PathBuf> = dedup.into_values().collect();

    let mut planned: Vec<String> = Vec::new();
    let mut removed: Vec<String> = Vec::new();
    let mut missing: Vec<String> = Vec::new();
    for path in &targets {
        let display = path.to_string_lossy().to_string();
        if path_exists(path) {
            planned.push(display.clone());
            if !dry_run && remove_path(path)? {
                removed.push(display);
            }
        } else {
            missing.push(display);
        }
    }

    if !dry_run {
        if remove_config {
            prune_empty_dir(&config_dir);
        }
        prune_empty_dir(&bin_dir);
        prune_empty_dir(&install_dir);
    }

    output(
        ctx,
        json!({
            "action": "uninstall",
            "dry_run": dry_run,
            "remove_config": remove_config,
            "all_versions": all_versions,
            "down_attempted": down_attempted,
            "down_skipped": down_skipped,
            "planned": planned,
            "removed": removed,
            "missing": missing,
            "warnings": warnings,
        }),
    )
}

fn handle_logs(ctx: &Context, command: LogsCommand) -> Result<(), LassoError> {
    match command {
        LogsCommand::Stats { run_id, latest } => logs_stats(ctx, run_id, latest),
        LogsCommand::Tail {
            lines,
            file,
            run_id,
            latest,
        } => logs_tail(ctx, lines, file, run_id, latest),
    }
}

fn logs_stats(ctx: &Context, run_id: Option<String>, latest: bool) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let run_id = resolve_run_id_from_selector(&log_root, run_id.as_deref(), latest)?;
    let run_root = run_root(&log_root, &run_id);
    let sessions_dir = run_root.join("harness").join("sessions");
    let mut total_bytes: u64 = 0;
    let mut total_hours: f64 = 0.0;
    let mut session_count = 0u64;

    if sessions_dir.exists() {
        for entry in fs::read_dir(&sessions_dir)? {
            let entry = entry?;
            if !entry.file_type()?.is_dir() {
                continue;
            }
            let meta_path = entry.path().join("meta.json");
            if !meta_path.exists() {
                continue;
            }
            let meta_raw = fs::read_to_string(&meta_path)?;
            let meta: serde_json::Value = serde_json::from_str(&meta_raw).unwrap_or(json!({}));
            let started = meta.get("started_at").and_then(|v| v.as_str());
            let ended = meta.get("ended_at").and_then(|v| v.as_str());
            let (Some(started), Some(ended)) = (started, ended) else {
                continue;
            };
            let start_dt = DateTime::parse_from_rfc3339(started).ok();
            let end_dt = DateTime::parse_from_rfc3339(ended).ok();
            let (Some(start_dt), Some(end_dt)) = (start_dt, end_dt) else {
                continue;
            };
            let duration = end_dt.with_timezone(&Utc) - start_dt.with_timezone(&Utc);
            let hours = duration.num_seconds() as f64 / 3600.0;
            if hours <= 0.0 {
                continue;
            }
            let size = dir_size(entry.path())?;
            total_bytes += size;
            total_hours += hours;
            session_count += 1;
        }
    }

    let avg_mb_per_hour = if total_hours > 0.0 {
        (total_bytes as f64 / (1024.0 * 1024.0)) / total_hours
    } else {
        0.0
    };

    let payload = json!({
        "run_id": run_id,
        "sessions": session_count,
        "total_bytes": total_bytes,
        "avg_mb_per_hour": avg_mb_per_hour,
    });
    output(ctx, payload)
}

fn logs_tail(
    ctx: &Context,
    lines: usize,
    file: Option<String>,
    run_id: Option<String>,
    latest: bool,
) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let run_id = resolve_run_id_from_selector(&log_root, run_id.as_deref(), latest)?;
    let run_root = run_root(&log_root, &run_id);
    let target = match file.as_deref() {
        Some("audit") => run_root.join("collector").join("raw").join("audit.log"),
        Some("ebpf") => run_root.join("collector").join("raw").join("ebpf.jsonl"),
        Some("timeline") | None => run_root
            .join("collector")
            .join("filtered")
            .join("filtered_timeline.jsonl"),
        Some(name) => run_root.join(name),
    };
    if !target.exists() {
        return Err(LassoError::Process(format!(
            "log not found: {}",
            target.display()
        )));
    }
    if ctx.json {
        let payload = JsonResult {
            ok: true,
            result: Some(json!({"run_id": run_id, "path": target})),
            error: None,
            error_details: None,
        };
        print_json(&payload)?;
        return Ok(());
    }
    let content = fs::read_to_string(&target)?;
    let lines_vec: Vec<&str> = content.lines().collect();
    let start = lines_vec.len().saturating_sub(lines);
    for line in &lines_vec[start..] {
        println!("{}", line);
    }
    Ok(())
}

fn dir_size(path: PathBuf) -> Result<u64, LassoError> {
    let mut size = 0;
    if path.is_file() {
        return Ok(fs::metadata(path)?.len());
    }
    if path.is_dir() {
        for entry in fs::read_dir(path)? {
            let entry = entry?;
            let file_type = entry.file_type()?;
            if file_type.is_dir() {
                size += dir_size(entry.path())?;
            } else if file_type.is_file() {
                size += entry.metadata()?.len();
            }
        }
    }
    Ok(size)
}

fn resolve_token(cfg: &Config) -> Result<String, LassoError> {
    if !cfg.harness.api_token.trim().is_empty() {
        return Ok(cfg.harness.api_token.clone());
    }
    if let Ok(token) = env::var("HARNESS_API_TOKEN") {
        if !token.trim().is_empty() {
            return Ok(token);
        }
    }
    Err(LassoError::Config(
        "HARNESS_API_TOKEN is required for server runs; set it in config.yaml or env".to_string(),
    ))
}

fn extract_process_error_details(err: &LassoError) -> Option<ProcessErrorDetails> {
    match err {
        LassoError::ProcessDetailed { details, .. } => Some(details.clone()),
        _ => None,
    }
}

fn output(ctx: &Context, payload: serde_json::Value) -> Result<(), LassoError> {
    if ctx.json {
        let wrapper = JsonResult {
            ok: true,
            result: Some(payload),
            error: None,
            error_details: None,
        };
        print_json(&wrapper)?;
    } else {
        println!("{}", payload);
    }
    Ok(())
}

fn print_json<T: Serialize>(payload: &T) -> Result<(), LassoError> {
    let text = serde_json::to_string_pretty(payload)?;
    println!("{}", text);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use tempfile::tempdir;

    #[derive(Debug, Clone)]
    struct RecordedCall {
        args: Vec<String>,
        env_overrides: BTreeMap<String, String>,
        capture_output: bool,
    }

    #[derive(Default)]
    struct MockDockerRunner {
        calls: RefCell<Vec<RecordedCall>>,
        outputs: RefCell<Vec<CommandOutput>>,
    }

    impl MockDockerRunner {
        fn push_output(&self, output: CommandOutput) {
            self.outputs.borrow_mut().push(output);
        }

        fn calls(&self) -> Vec<RecordedCall> {
            self.calls.borrow().clone()
        }
    }

    impl DockerRunner for MockDockerRunner {
        fn run(
            &self,
            args: &[String],
            _cwd: &Path,
            env_overrides: &BTreeMap<String, String>,
            capture_output: bool,
        ) -> Result<CommandOutput, io::Error> {
            self.calls.borrow_mut().push(RecordedCall {
                args: args.to_vec(),
                env_overrides: env_overrides.clone(),
                capture_output,
            });
            let mut queued = self.outputs.borrow_mut();
            if queued.is_empty() {
                return Ok(CommandOutput {
                    status_code: 0,
                    stdout: Vec::new(),
                    stderr: Vec::new(),
                });
            }
            Ok(queued.remove(0))
        }
    }

    fn write_minimal_config(path: &Path) {
        let base = path.parent().unwrap_or_else(|| Path::new("."));
        let home = required_home_dir().expect("home");
        let mut cfg = Config::default();
        cfg.paths.log_root = base.join("logs").to_string_lossy().to_string();
        cfg.paths.workspace_root = home
            .join("lasso-test-workspace")
            .to_string_lossy()
            .to_string();
        fs::write(path, serde_yaml::to_string(&cfg).unwrap()).unwrap();
    }

    fn write_default_compose_files(dir: &Path) {
        fs::write(dir.join("compose.yml"), "services: {}\n").unwrap();
        fs::write(dir.join("compose.ui.yml"), "services: {}\n").unwrap();
    }

    fn make_context(dir: &Path) -> Context {
        let config_path = dir.join("config.yaml");
        let env_file = dir.join("compose.env");
        Context {
            config_path,
            env_file,
            bundle_dir: dir.to_path_buf(),
            compose_file_overrides: Vec::new(),
            json: true,
        }
    }

    #[test]
    fn config_unknown_field_errors() {
        let yaml = r#"
version: 2
unknown: true
paths:
  log_root: ~/lasso-logs
  workspace_root: ~/lasso-workspace
"#;
        let result: Result<Config, _> = serde_yaml::from_str(yaml);
        assert!(result.is_err());
    }

    #[test]
    fn config_defaults_apply() {
        let yaml = r#"version: 2"#;
        let cfg: Config = serde_yaml::from_str(yaml).expect("config");
        assert_eq!(cfg.version, 2);
        let home = required_home_dir().expect("home");
        let expected = default_paths_for_os(env::consts::OS, &home).expect("default paths");
        assert_eq!(cfg.paths.log_root, expected.log_root);
        assert_eq!(cfg.paths.workspace_root, expected.workspace_root);
    }

    #[test]
    fn expand_tilde_works() {
        let expanded = expand_path("~/lasso-logs");
        assert!(!expanded.starts_with("~/"));
    }

    #[test]
    fn env_file_written() {
        let dir = tempdir().unwrap();
        let env_path = dir.path().join("compose.env");
        let cfg: Config = serde_yaml::from_str("version: 2").unwrap();
        let envs = config_to_env(&cfg);
        write_env_file(&env_path, &envs).unwrap();
        let content = fs::read_to_string(&env_path).unwrap();
        assert!(content.contains("LASSO_VERSION="));
        assert!(content.contains("LASSO_LOG_ROOT="));
    }

    #[test]
    fn yaml_patch_preserves_comments_and_spacing() {
        let input = r#"# top comment
version: 2

paths:   # paths comment
  log_root : ~/lasso-logs   # inline
  workspace_root: "~/lasso-workspace"   # keep quotes

providers:
  codex:
    auth_mode: api_key  # keep
    mount_host_state_in_api_mode: false
    commands:
      tui: "codex"
      run_template: "codex exec {prompt}"
    auth:
      api_key:
        secrets_file: ~/.config/lasso/secrets/codex.env
        env_key: OPENAI_API_KEY
      host_state:
        paths:
          - ~/.codex/auth.json
    ownership:
      root_comm:
        - codex
"#;

        let mut edits = SetupYamlEdits::default();
        edits.log_root = Some("/tmp/new-logs".to_string());

        let (patched, changed) = patch_setup_config_yaml(input, &edits).unwrap();
        assert!(changed);
        assert!(patched.ends_with('\n'));

        // Comments must remain byte-for-byte.
        assert!(patched.contains("# top comment"));
        assert!(patched.contains("paths:   # paths comment"));
        assert!(patched.contains("  log_root : /tmp/new-logs   # inline"));
        assert!(patched.contains("  workspace_root: \"~/lasso-workspace\"   # keep quotes"));

        // Unchanged provider line should remain unchanged.
        assert!(patched.contains("    auth_mode: api_key  # keep"));
    }

    #[test]
    fn up_wait_timeout_builds_expected_compose_args() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = MockDockerRunner::default();

        handle_up(&ctx, None, true, None, false, None, true, Some(45), &runner).unwrap();

        let calls = runner.calls();
        assert_eq!(calls.len(), 3);

        let ps_args = &calls[0].args;
        assert!(ps_args.iter().any(|x| x == "ps"));
        assert!(calls[0].env_overrides.contains_key("LASSO_WORKSPACE_ROOT"));
        assert!(!calls[0].env_overrides.contains_key("LASSO_RUN_ID"));

        let args = &calls[2].args;
        assert!(calls[2].capture_output);
        assert!(args.iter().any(|x| x == "up"));
        assert!(args.iter().any(|x| x == "--wait"));
        let idx = args.iter().position(|x| x == "--wait-timeout").unwrap();
        assert_eq!(args[idx + 1], "45");
        assert!(calls[2].env_overrides.contains_key("LASSO_RUN_ID"));
        assert!(calls[2].env_overrides.contains_key("LASSO_WORKSPACE_ROOT"));
    }

    #[test]
    fn up_timeout_requires_wait() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = MockDockerRunner::default();

        let err = handle_up(
            &ctx,
            None,
            true,
            None,
            false,
            None,
            false,
            Some(10),
            &runner,
        )
        .expect_err("timeout without wait should fail");
        assert!(err.to_string().contains("--timeout-sec requires --wait"));
    }

    #[test]
    fn up_fails_when_stack_already_running() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = MockDockerRunner::default();
        runner.push_output(CommandOutput {
            status_code: 0,
            stdout: Vec::new(),
            stderr: Vec::new(),
        });
        runner.push_output(CommandOutput {
            status_code: 0,
            stdout: b"collector\n".to_vec(),
            stderr: Vec::new(),
        });

        let err = handle_up(&ctx, None, true, None, false, None, false, None, &runner)
            .expect_err("already-running stack should fail");
        assert!(err.to_string().contains("collector is already running"));
        assert_eq!(runner.calls().len(), 2);
    }

    #[test]
    fn down_collector_only_builds_expected_args() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = MockDockerRunner::default();

        handle_down(&ctx, None, true, false, &runner).unwrap();

        let calls = runner.calls();
        assert_eq!(calls.len(), 1);
        let args = &calls[0].args;
        assert!(args.iter().any(|x| x == "stop"));
        assert!(args.iter().any(|x| x == "collector"));
    }

    #[test]
    fn compose_file_override_replaces_default_compose_selection() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        let override_file = dir.path().join("custom.compose.yml");
        fs::write(&override_file, "services: {}\n").unwrap();
        let mut ctx = make_context(dir.path());
        ctx.compose_file_overrides = vec![override_file.clone()];
        let runner = MockDockerRunner::default();
        runner.push_output(CommandOutput {
            status_code: 0,
            stdout: b"[]\n".to_vec(),
            stderr: Vec::new(),
        });

        handle_status(&ctx, None, true, true, &runner).unwrap();

        let calls = runner.calls();
        assert_eq!(calls.len(), 1);
        let args = &calls[0].args;
        assert!(args
            .iter()
            .any(|x| x == &override_file.to_string_lossy().to_string()));
    }

    #[test]
    fn normalize_version_tag_adds_prefix() {
        assert_eq!(normalize_version_tag("0.1.0"), "v0.1.0");
        assert_eq!(normalize_version_tag("v0.1.0"), "v0.1.0");
    }

    #[test]
    fn select_previous_version_uses_installed_order() {
        let installed = vec![
            "0.1.0".to_string(),
            "0.2.0".to_string(),
            "0.3.0".to_string(),
        ];
        assert_eq!(
            select_previous_version("v0.3.0", &installed),
            Some("v0.2.0".to_string())
        );
        assert_eq!(select_previous_version("v0.1.0", &installed), None);
    }

    #[test]
    fn parse_checksum_reads_first_token() {
        let hash = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        let content = format!("{hash}  lasso_0.1.0_linux_amd64.tar.gz");
        assert_eq!(parse_checksum(&content), Some(hash.to_string()));
    }

    #[test]
    fn parse_checksum_supports_openssl_output() {
        let hash = "abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd";
        let content = format!("SHA2-256(file.tar.gz)= {hash}");
        assert_eq!(parse_checksum(&content), Some(hash.to_string()));
    }

    #[test]
    fn map_host_start_dir_to_container_maps_root_and_nested_paths() {
        let workspace = PathBuf::from("/tmp/workspace");
        let mapped_root = map_host_start_dir_to_container(&workspace, &workspace).unwrap();
        assert_eq!(mapped_root, "/work");

        let nested = workspace.join("src").join("project");
        let mapped_nested = map_host_start_dir_to_container(&nested, &workspace).unwrap();
        assert_eq!(mapped_nested, "/work/src/project");
    }

    #[test]
    fn resolve_effective_workspace_root_enforces_home_policy_for_override() {
        let dir = tempdir().unwrap();
        let home = required_home_dir().unwrap();
        let mut cfg = Config::default();
        cfg.paths.log_root = dir.path().join("logs").to_string_lossy().to_string();
        cfg.paths.workspace_root = home.join("workspace").to_string_lossy().to_string();

        let override_workspace = home.join("workspace-alt");
        let resolved =
            resolve_effective_workspace_root(&cfg, Some(override_workspace.to_str().unwrap()))
                .unwrap();
        assert_eq!(resolved, override_workspace);

        let outside_workspace = dir.path().join("outside-home-workspace");
        let err = resolve_effective_workspace_root(&cfg, Some(outside_workspace.to_str().unwrap()))
            .expect_err("outside-home workspace should fail");
        assert!(err.to_string().contains("--workspace must be under $HOME"));
    }

    #[test]
    fn resolve_host_start_dir_requires_start_dir_inside_workspace() {
        let dir = tempdir().unwrap();
        let home = required_home_dir().unwrap();
        let mut cfg = Config::default();
        cfg.paths.log_root = dir.path().join("logs").to_string_lossy().to_string();
        cfg.paths.workspace_root = home.join("workspace").to_string_lossy().to_string();

        let workspace_root = resolve_effective_workspace_root(&cfg, None).unwrap();
        let inside = workspace_root.join("src");
        let resolved =
            resolve_host_start_dir(&cfg, &workspace_root, Some(inside.to_str().unwrap())).unwrap();
        assert_eq!(resolved, inside);

        let outside = dir.path().join("outside");
        let err = resolve_host_start_dir(&cfg, &workspace_root, Some(outside.to_str().unwrap()))
            .expect_err("outside workspace should fail");
        assert!(err
            .to_string()
            .contains("--start-dir must be inside workspace"));
    }

    #[test]
    fn classify_docker_command_failure_detects_compose_unavailable() {
        let (code, hint) = classify_docker_command_failure(
            "unknown flag: --env-file\n\nUsage:  docker [OPTIONS] COMMAND [ARG...]",
        );
        assert_eq!(code, "docker_compose_unavailable");
        assert!(hint.unwrap_or_default().contains("DOCKER_CONFIG"));
    }

    #[test]
    fn execute_docker_nonzero_exit_surfaces_structured_details() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = MockDockerRunner::default();
        runner.push_output(CommandOutput {
            status_code: 125,
            stdout: Vec::new(),
            stderr: b"unknown flag: --env-file".to_vec(),
        });
        let args = vec![
            "compose".to_string(),
            "--env-file".to_string(),
            "/tmp/compose.env".to_string(),
            "ps".to_string(),
        ];
        let err = execute_docker(&ctx, &runner, &args, &BTreeMap::new(), true, false)
            .expect_err("docker command should fail");

        match err {
            LassoError::ProcessDetailed { message, details } => {
                assert!(message
                    .contains("while running `docker compose --env-file /tmp/compose.env ps`"));
                assert_eq!(details.error_code, "docker_compose_unavailable");
                assert!(details.hint.unwrap_or_default().contains("DOCKER_CONFIG"));
                assert_eq!(
                    details.command.unwrap_or_default(),
                    "docker compose --env-file /tmp/compose.env ps"
                );
                assert!(details
                    .raw_stderr
                    .unwrap_or_default()
                    .contains("unknown flag: --env-file"));
            }
            other => panic!("unexpected error variant: {other:?}"),
        }
    }

    #[test]
    fn execute_docker_spawn_not_found_sets_docker_not_found_code() {
        struct NotFoundRunner;
        impl DockerRunner for NotFoundRunner {
            fn run(
                &self,
                _args: &[String],
                _cwd: &Path,
                _env_overrides: &BTreeMap<String, String>,
                _capture_output: bool,
            ) -> Result<CommandOutput, io::Error> {
                Err(io::Error::new(io::ErrorKind::NotFound, "docker not found"))
            }
        }

        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = NotFoundRunner;
        let args = vec!["compose".to_string(), "ps".to_string()];
        let err = execute_docker(&ctx, &runner, &args, &BTreeMap::new(), true, false)
            .expect_err("missing docker should fail");
        match err {
            LassoError::ProcessDetailed { message, details } => {
                assert!(message.contains("failed to run command `docker compose ps`"));
                assert_eq!(details.error_code, "docker_not_found");
                assert!(details.hint.unwrap_or_default().contains("Install Docker"));
                assert_eq!(details.command.unwrap_or_default(), "docker compose ps");
            }
            other => panic!("unexpected error variant: {other:?}"),
        }
    }
}
