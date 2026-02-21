use chrono::{DateTime, Utc};
use clap::{Parser, Subcommand};
use dialoguer::console::style;
use dialoguer::console::Term;
use dialoguer::theme::ColorfulTheme;
use dialoguer::{Confirm, Input, Password, Select};
use dirs::home_dir;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, VecDeque};
use std::env;
use std::fs;
use std::io;
use std::io::IsTerminal;
use std::io::{Read, Write};
#[cfg(unix)]
use std::os::unix::ffi::OsStrExt;
#[cfg(unix)]
use std::os::unix::fs::symlink;
#[cfg(unix)]
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use thiserror::Error;

const DEFAULT_CONFIG_YAML: &str = include_str!("../config/default.yaml");
const RUNTIME_BYPASS_ENV: &str = "LUX_RUNTIME_BYPASS";
#[cfg(unix)]
const UNIX_SOCKET_PATH_LIMIT_BYTES: usize = 100;

#[derive(Parser, Debug)]
#[command(name = "lux", version, about = "Lux CLI")]
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
    },
    Status {
        #[arg(long, conflicts_with = "collector_only")]
        provider: Option<String>,
        #[arg(long, default_value_t = false, conflicts_with = "provider")]
        collector_only: bool,
    },
    Ui {
        #[command(subcommand)]
        command: UiCommand,
    },
    Runtime {
        #[command(subcommand)]
        command: RuntimeCommand,
    },
    Shim {
        #[command(subcommand)]
        command: ShimCommand,
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
    Doctor {
        #[arg(long, default_value_t = false)]
        strict: bool,
    },
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
enum UiCommand {
    Up {
        #[arg(long)]
        wait: bool,
        #[arg(long)]
        timeout_sec: Option<u64>,
        #[arg(long, value_parser = ["always", "never", "missing"]) ]
        pull: Option<String>,
    },
    Down,
    Status,
    Url,
}

#[derive(Subcommand, Debug)]
enum RuntimeCommand {
    Up,
    Down,
    Status,
    #[command(hide = true)]
    Serve,
}

#[derive(Subcommand, Debug)]
enum ShimCommand {
    Enable {
        providers: Vec<String>,
    },
    Disable {
        providers: Vec<String>,
    },
    Status {
        providers: Vec<String>,
    },
    Exec {
        provider: String,
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        argv: Vec<String>,
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
enum LuxError {
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
    shims: Shims,
    release: Release,
    docker: Docker,
    harness: Harness,
    collector: CollectorConfig,
    runtime_control_plane: RuntimeControlPlaneConfig,
    providers: BTreeMap<String, Provider>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Paths {
    trusted_root: String,
    log_root: String,
    workspace_root: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct Shims {
    bin_dir: String,
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

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct CollectorConfig {
    auto_start: bool,
    idle_timeout_min: u64,
    rotate_every_min: u64,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(default, deny_unknown_fields)]
struct RuntimeControlPlaneConfig {
    socket_path: String,
    socket_gid: Option<u32>,
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
            shims: Shims::default(),
            release: Release::default(),
            docker: Docker::default(),
            harness: Harness::default(),
            collector: CollectorConfig::default(),
            runtime_control_plane: RuntimeControlPlaneConfig::default(),
            providers: default_providers(),
        }
    }
}

impl Default for Paths {
    fn default() -> Self {
        if let Ok(paths) = computed_default_paths_for_current_os() {
            return paths;
        }
        let trusted_root = match env::consts::OS {
            "macos" => "/Users/Shared/Lux",
            "linux" => "/var/lib/lux",
            _ => "/var/lib/lux",
        }
        .to_string();
        let workspace_root = home_dir()
            .map(|path| path.to_string_lossy().to_string())
            .unwrap_or_else(|| "~".to_string());
        let log_root = Path::new(&trusted_root)
            .join("logs")
            .to_string_lossy()
            .to_string();
        Self {
            trusted_root,
            log_root,
            workspace_root,
        }
    }
}

impl Default for Shims {
    fn default() -> Self {
        let bin_dir = computed_default_paths_for_current_os()
            .map(|paths| {
                Path::new(&paths.trusted_root)
                    .join("bin")
                    .to_string_lossy()
                    .to_string()
            })
            .unwrap_or_else(|_| match env::consts::OS {
                "macos" => "/Users/Shared/Lux/bin".to_string(),
                "linux" => "/var/lib/lux/bin".to_string(),
                _ => "/var/lib/lux/bin".to_string(),
            });
        Self { bin_dir }
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
            project_name: "lux".to_string(),
        }
    }
}

impl Default for Harness {
    fn default() -> Self {
        Self {
            api_host: "127.0.0.1".to_string(),
            api_port: 8081,
            api_token: "TEMP_STR_TO_CHANGE".to_string(),
        }
    }
}

impl Default for CollectorConfig {
    fn default() -> Self {
        Self {
            auto_start: true,
            idle_timeout_min: 10_080,
            rotate_every_min: 1_440,
        }
    }
}

impl Default for RuntimeControlPlaneConfig {
    fn default() -> Self {
        Self {
            socket_path: String::new(),
            socket_gid: None,
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
    let default_secrets_root = computed_default_paths_for_current_os()
        .map(|paths| {
            Path::new(&paths.trusted_root)
                .join("secrets")
                .to_string_lossy()
                .to_string()
        })
        .unwrap_or_else(|_| match env::consts::OS {
            "macos" => "/Users/Shared/Lux/secrets".to_string(),
            "linux" => "/var/lib/lux/secrets".to_string(),
            _ => "/var/lib/lux/secrets".to_string(),
        });
    let mut providers = BTreeMap::new();
    providers.insert(
        "codex".to_string(),
        Provider {
            auth_mode: AuthMode::ApiKey,
            mount_host_state_in_api_mode: false,
            commands: ProviderCommands {
                tui: "codex -s danger-full-access".to_string(),
                run_template: "codex -s danger-full-access exec --skip-git-repo-check {prompt}"
                    .to_string(),
            },
            auth: ProviderAuth {
                api_key: ProviderApiKeyAuth {
                    secrets_file: Path::new(&default_secrets_root)
                        .join("codex.env")
                        .to_string_lossy()
                        .to_string(),
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
                    secrets_file: Path::new(&default_secrets_root)
                        .join("claude.env")
                        .to_string_lossy()
                        .to_string(),
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
    #[serde(skip_serializing_if = "Option::is_none")]
    partial_outcome: Option<serde_json::Value>,
}

#[derive(Debug, Clone)]
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

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RuntimeEvent {
    id: u64,
    ts: String,
    event_type: String,
    severity: String,
    payload: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct RuntimeWarning {
    ts: String,
    message: String,
}

#[derive(Debug, Default)]
struct RuntimeSharedState {
    next_event_id: u64,
    events: VecDeque<RuntimeEvent>,
    warnings: VecDeque<RuntimeWarning>,
    shutdown: bool,
    rotation_pending: bool,
    last_provider_activity_at: Option<String>,
}

#[derive(Debug, Deserialize)]
struct RuntimeExecuteRequest {
    argv: Vec<String>,
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

fn main() -> Result<(), LuxError> {
    let raw_args: Vec<String> = env::args().skip(1).collect();
    let cli = Cli::parse();
    let ctx = build_context(&cli)?;
    let runner = RealDockerRunner;

    let result = if should_route_through_runtime(&cli.command) && !runtime_bypass_enabled() {
        handle_runtime_execute_proxy(&ctx, &raw_args)
    } else {
        match cli.command {
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
                pull,
                wait,
                timeout_sec,
            } => handle_up(
                &ctx,
                provider,
                collector_only,
                workspace,
                pull,
                wait,
                timeout_sec,
                &runner,
            ),
            Commands::Down {
                provider,
                collector_only,
            } => handle_down(&ctx, provider, collector_only, &runner),
            Commands::Status {
                provider,
                collector_only,
            } => handle_status(&ctx, provider, collector_only, &runner),
            Commands::Ui { command } => handle_ui(&ctx, command, &runner),
            Commands::Runtime { command } => handle_runtime(&ctx, command),
            Commands::Shim { command } => handle_shim(&ctx, command, &runner),
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
            Commands::Doctor { strict } => handle_doctor(&ctx, strict),
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
        }
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

fn build_context(cli: &Cli) -> Result<Context, LuxError> {
    let config_path = resolve_config_path(cli.config.as_ref());
    let env_file = resolve_env_file(cli.env_file.as_ref(), &config_path);
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
    if let Ok(path) = env::var("LUX_CONFIG") {
        return PathBuf::from(path);
    }
    let mut base = default_config_dir();
    base.push("config.yaml");
    base
}

fn resolve_env_file(override_path: Option<&PathBuf>, config_path: &Path) -> PathBuf {
    if let Some(path) = override_path {
        return path.clone();
    }
    if let Ok(path) = env::var("LUX_ENV_FILE") {
        return PathBuf::from(path);
    }
    if config_path.exists() {
        if let Ok(cfg) = read_config(config_path) {
            return PathBuf::from(expand_path(&cfg.paths.trusted_root))
                .join("state")
                .join("compose.env");
        }
    }
    computed_default_paths_for_current_os()
        .map(|paths| {
            PathBuf::from(paths.trusted_root)
                .join("state")
                .join("compose.env")
        })
        .unwrap_or_else(|_| PathBuf::from("/var/lib/lux/state/compose.env"))
}

fn bundle_dir_from_exe_path(exe: &Path) -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    let mut push_candidate = |candidate: PathBuf| {
        if !candidates.iter().any(|existing| existing == &candidate) {
            candidates.push(candidate);
        }
    };

    if let Some(parent) = exe.parent() {
        push_candidate(parent.to_path_buf());
    }

    if let Ok(link_target) = fs::read_link(exe) {
        let resolved_target = if link_target.is_absolute() {
            link_target
        } else {
            exe.parent()
                .map_or_else(|| PathBuf::from("."), PathBuf::from)
                .join(link_target)
        };
        if let Some(parent) = resolved_target.parent() {
            push_candidate(parent.to_path_buf());
        }
        if let Ok(canonical_target) = fs::canonicalize(&resolved_target) {
            if let Some(parent) = canonical_target.parent() {
                push_candidate(parent.to_path_buf());
            }
        }
    }

    if let Ok(canonical_exe) = fs::canonicalize(exe) {
        if let Some(parent) = canonical_exe.parent() {
            push_candidate(parent.to_path_buf());
        }
    }

    candidates
        .into_iter()
        .find(|candidate| candidate.join("compose.yml").exists())
}

fn resolve_bundle_dir(override_path: Option<&PathBuf>) -> PathBuf {
    if let Some(path) = override_path {
        return path.clone();
    }
    if let Ok(path) = env::var("LUX_BUNDLE_DIR") {
        if !path.trim().is_empty() {
            return PathBuf::from(path);
        }
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(candidate) = bundle_dir_from_exe_path(&exe) {
            return candidate;
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
    trusted_root: PathBuf,
    state_root: PathBuf,
    runtime_root: PathBuf,
    secrets_root: PathBuf,
    shims_bin_dir: PathBuf,
    log_root: PathBuf,
    workspace_root: PathBuf,
}

fn required_home_dir() -> Result<PathBuf, LuxError> {
    let home = home_dir().ok_or_else(|| {
        LuxError::Config("unable to resolve $HOME; set HOME to an existing directory".to_string())
    })?;
    if !home.is_absolute() {
        return Err(LuxError::Config(format!(
            "resolved HOME path is not absolute: {}",
            home.display()
        )));
    }
    if !home.exists() {
        return Err(LuxError::Config(format!(
            "resolved HOME path does not exist: {}",
            home.display()
        )));
    }
    fs::canonicalize(&home).map_err(|err| {
        LuxError::Config(format!(
            "failed to canonicalize HOME directory {}: {}",
            home.display(),
            err
        ))
    })
}

fn default_paths_for_os(os: &str, home: &Path) -> Result<Paths, LuxError> {
    match os {
        "macos" => Ok(Paths {
            trusted_root: "/Users/Shared/Lux".to_string(),
            log_root: "/Users/Shared/Lux/logs".to_string(),
            workspace_root: home.to_string_lossy().to_string(),
        }),
        "linux" => Ok(Paths {
            trusted_root: "/var/lib/lux".to_string(),
            log_root: "/var/lib/lux/logs".to_string(),
            workspace_root: home.to_string_lossy().to_string(),
        }),
        other => Err(LuxError::Config(format!(
            "unsupported host operating system '{}' for default path computation; supported: macos, linux",
            other
        ))),
    }
}

fn computed_default_paths_for_current_os() -> Result<Paths, LuxError> {
    let home = required_home_dir()?;
    default_paths_for_os(env::consts::OS, &home)
}

fn build_default_config_yaml() -> Result<String, LuxError> {
    let defaults = computed_default_paths_for_current_os()?;
    let mut edits = SetupYamlEdits::default();
    edits.trusted_root = Some(defaults.trusted_root.clone());
    edits.log_root = Some(defaults.log_root);
    edits.workspace_root = Some(defaults.workspace_root);
    edits.shims_bin_dir = Some(
        Path::new(&defaults.trusted_root)
            .join("bin")
            .to_string_lossy()
            .to_string(),
    );
    edits.provider_api_key_secrets_files.insert(
        "codex".to_string(),
        Path::new(&defaults.trusted_root)
            .join("secrets")
            .join("codex.env")
            .to_string_lossy()
            .to_string(),
    );
    edits.provider_api_key_secrets_files.insert(
        "claude".to_string(),
        Path::new(&defaults.trusted_root)
            .join("secrets")
            .join("claude.env")
            .to_string_lossy()
            .to_string(),
    );
    let (patched, _changed) = patch_setup_config_yaml(DEFAULT_CONFIG_YAML, &edits)?;
    Ok(patched)
}

fn expand_home_path(input: &str, home: &Path, field: &str) -> Result<PathBuf, LuxError> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Err(LuxError::Config(format!(
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
        return Err(LuxError::Config(format!(
            "{field} uses unsupported '~' syntax; use '~/' or an absolute path"
        )));
    }
    Ok(PathBuf::from(trimmed))
}

fn canonicalize_policy_path(path: &Path, field: &str) -> Result<PathBuf, LuxError> {
    if !path.is_absolute() {
        return Err(LuxError::Config(format!(
            "{field} must be an absolute path: {}",
            path.display()
        )));
    }
    if path.exists() {
        return fs::canonicalize(path).map_err(|err| {
            LuxError::Config(format!(
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
            LuxError::Config(format!(
                "{field} is not canonicalizable: {}",
                path.display()
            ))
        })?;
        tail.push(name.to_os_string());
        cursor = cursor
            .parent()
            .ok_or_else(|| {
                LuxError::Config(format!(
                    "{field} is not canonicalizable: {}",
                    path.display()
                ))
            })?
            .to_path_buf();
    }

    let mut canonical = fs::canonicalize(&cursor).map_err(|err| {
        LuxError::Config(format!(
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

fn resolve_policy_path(input: &str, field: &str, home: &Path) -> Result<PathBuf, LuxError> {
    let expanded = expand_home_path(input, home, field)?;
    canonicalize_policy_path(&expanded, field)
}

fn path_is_within(path: &Path, root: &Path) -> bool {
    path == root || path.starts_with(root)
}

fn display_path_with_home(path: &Path, home: Option<&Path>) -> String {
    if let Some(home_path) = home {
        if path == home_path {
            return "$HOME".to_string();
        }
        if let Ok(relative) = path.strip_prefix(home_path) {
            if relative.as_os_str().is_empty() {
                return "$HOME".to_string();
            }
            return format!("$HOME/{}", relative.display());
        }
    }
    path.display().to_string()
}

fn resolve_config_policy_paths(cfg: &Config) -> Result<PolicyPaths, LuxError> {
    let home = required_home_dir()?;
    let workspace_root =
        resolve_policy_path(&cfg.paths.workspace_root, "paths.workspace_root", &home)?;
    let trusted_root = resolve_policy_path(&cfg.paths.trusted_root, "paths.trusted_root", &home)?;
    let log_root = resolve_policy_path(&cfg.paths.log_root, "paths.log_root", &home)?;
    let shims_bin_dir = resolve_policy_path(&cfg.shims.bin_dir, "shims.bin_dir", &home)?;
    let state_root = trusted_root.join("state");
    let runtime_root = trusted_root.join("runtime");
    let secrets_root = trusted_root.join("secrets");

    if !path_is_within(&workspace_root, &home) {
        return Err(LuxError::Config(format!(
            "paths.workspace_root must be under $HOME (home={}, workspace={})",
            display_path_with_home(&home, Some(&home)),
            display_path_with_home(&workspace_root, Some(&home))
        )));
    }
    if path_is_within(&trusted_root, &home) {
        return Err(LuxError::Config(format!(
            "paths.trusted_root must be outside $HOME to protect evidence integrity (home={}, trusted_root={})",
            display_path_with_home(&home, Some(&home)),
            display_path_with_home(&trusted_root, Some(&home))
        )));
    }
    if !path_is_within(&log_root, &trusted_root) {
        return Err(LuxError::Config(format!(
            "paths.log_root must be inside paths.trusted_root (trusted_root={}, log_root={})",
            display_path_with_home(&trusted_root, Some(&home)),
            display_path_with_home(&log_root, Some(&home))
        )));
    }
    if !path_is_within(&shims_bin_dir, &trusted_root) {
        return Err(LuxError::Config(format!(
            "shims.bin_dir must be inside paths.trusted_root (trusted_root={}, shims.bin_dir={})",
            display_path_with_home(&trusted_root, Some(&home)),
            display_path_with_home(&shims_bin_dir, Some(&home))
        )));
    }
    if path_is_within(&workspace_root, &log_root) || path_is_within(&log_root, &workspace_root) {
        return Err(LuxError::Config(format!(
            "paths.workspace_root and paths.log_root must not overlap (workspace={}, log_root={})",
            display_path_with_home(&workspace_root, Some(&home)),
            display_path_with_home(&log_root, Some(&home))
        )));
    }
    if path_is_within(&workspace_root, &shims_bin_dir)
        || path_is_within(&shims_bin_dir, &workspace_root)
    {
        return Err(LuxError::Config(format!(
            "paths.workspace_root and shims.bin_dir must not overlap (workspace={}, shims.bin_dir={})",
            display_path_with_home(&workspace_root, Some(&home)),
            display_path_with_home(&shims_bin_dir, Some(&home))
        )));
    }

    Ok(PolicyPaths {
        home,
        trusted_root,
        state_root,
        runtime_root,
        secrets_root,
        shims_bin_dir,
        log_root,
        workspace_root,
    })
}

fn default_config_dir() -> PathBuf {
    if let Ok(path) = env::var("LUX_CONFIG_DIR") {
        return PathBuf::from(path);
    }
    let mut base = home_dir().unwrap_or_else(|| PathBuf::from("."));
    base.push(".config");
    base.push("lux");
    base
}

fn ensure_parent(path: &Path) -> Result<(), LuxError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    Ok(())
}

#[derive(Debug)]
struct RuntimeHttpResponse {
    status: u16,
    body: Vec<u8>,
}

fn runtime_bypass_enabled() -> bool {
    match env::var(RUNTIME_BYPASS_ENV) {
        Ok(value) => matches!(value.as_str(), "1" | "true" | "yes"),
        Err(_) => false,
    }
}

fn should_route_through_runtime(command: &Commands) -> bool {
    matches!(
        command,
        Commands::Up { .. }
            | Commands::Down { .. }
            | Commands::Status { .. }
            | Commands::Ui { .. }
            | Commands::Run { .. }
    )
}

#[cfg(unix)]
fn runtime_control_plane_request(
    ctx: &Context,
    method: &str,
    path: &str,
    headers: &[(String, String)],
    body: Option<&[u8]>,
) -> Result<RuntimeHttpResponse, LuxError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    let socket_path = &paths.runtime_socket_path;
    let mut stream = UnixStream::connect(socket_path).map_err(|err| {
        LuxError::Process(format!(
            "failed to connect runtime control plane socket {}: {}",
            socket_path.display(),
            err
        ))
    })?;
    let mut request = format!(
        "{} {} HTTP/1.1\r\nHost: lux-runtime\r\nConnection: close\r\n",
        method, path
    );
    for (key, value) in headers {
        request.push_str(key);
        request.push_str(": ");
        request.push_str(value);
        request.push_str("\r\n");
    }
    if let Some(body) = body {
        request.push_str("Content-Length: ");
        request.push_str(&body.len().to_string());
        request.push_str("\r\n");
    }
    request.push_str("\r\n");
    stream.write_all(request.as_bytes())?;
    if let Some(body) = body {
        stream.write_all(body)?;
    }

    let mut raw = Vec::new();
    stream.read_to_end(&mut raw)?;
    let split = raw
        .windows(4)
        .position(|w| w == b"\r\n\r\n")
        .ok_or_else(|| {
            LuxError::Process("runtime response missing header delimiter".to_string())
        })?;
    let header_bytes = &raw[..split];
    let body_bytes = raw[split + 4..].to_vec();
    let header_text = String::from_utf8_lossy(header_bytes);
    let mut lines = header_text.lines();
    let status_line = lines
        .next()
        .ok_or_else(|| LuxError::Process("runtime response missing status line".to_string()))?;
    let status = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|s| s.parse::<u16>().ok())
        .ok_or_else(|| LuxError::Process("runtime response has invalid status".to_string()))?;
    let _parsed_headers: BTreeMap<String, String> = lines
        .filter_map(|line| line.split_once(':'))
        .map(|(key, value)| (key.trim().to_ascii_lowercase(), value.trim().to_string()))
        .collect();
    Ok(RuntimeHttpResponse {
        status,
        body: body_bytes,
    })
}

#[cfg(not(unix))]
fn runtime_control_plane_request(
    _ctx: &Context,
    _method: &str,
    _path: &str,
    _headers: &[(String, String)],
    _body: Option<&[u8]>,
) -> Result<RuntimeHttpResponse, LuxError> {
    Err(LuxError::Config(
        "runtime control plane is only supported on unix hosts".to_string(),
    ))
}

fn runtime_ping(ctx: &Context) -> Result<(), LuxError> {
    let response = runtime_control_plane_request(ctx, "GET", "/v1/healthz", &[], None)?;
    if response.status >= 400 {
        return Err(LuxError::Process(format!(
            "runtime control plane ping failed with status {}",
            response.status
        )));
    }
    Ok(())
}

fn ensure_runtime_running(ctx: &Context) -> Result<(), LuxError> {
    if runtime_ping(ctx).is_ok() {
        return Ok(());
    }
    runtime_up_internal(ctx, false)?;
    runtime_ping(ctx)
}

fn handle_runtime_execute_proxy(ctx: &Context, raw_args: &[String]) -> Result<(), LuxError> {
    ensure_runtime_running(ctx)?;
    let body = serde_json::to_vec(&json!({ "argv": raw_args }))?;
    let response = runtime_control_plane_request(
        ctx,
        "POST",
        "/v1/execute",
        &[("Content-Type".to_string(), "application/json".to_string())],
        Some(&body),
    )?;
    if response.status >= 400 {
        let text = String::from_utf8_lossy(&response.body).to_string();
        return Err(LuxError::Process(format!(
            "runtime execute request failed (HTTP {}): {}",
            response.status, text
        )));
    }
    let payload: serde_json::Value = serde_json::from_slice(&response.body).map_err(|err| {
        LuxError::Process(format!("runtime execute returned invalid JSON: {err}"))
    })?;
    let status_code = payload
        .get("status_code")
        .and_then(|v| v.as_i64())
        .unwrap_or(1);
    let stdout = payload
        .get("stdout")
        .and_then(|v| v.as_str())
        .unwrap_or_default();
    let stderr = payload
        .get("stderr")
        .and_then(|v| v.as_str())
        .unwrap_or_default();
    if !stdout.is_empty() {
        print!("{stdout}");
    }
    if !stderr.is_empty() {
        eprint!("{stderr}");
    }
    if status_code != 0 {
        std::process::exit(status_code as i32);
    }
    Ok(())
}

fn read_config_from_str(content: &str) -> Result<Config, LuxError> {
    let raw: serde_yaml::Value = serde_yaml::from_str(content)?;
    let has_explicit_trusted_root = raw
        .as_mapping()
        .and_then(|root| root.get(&serde_yaml::Value::String("paths".to_string())))
        .and_then(|paths| paths.as_mapping())
        .map(|paths| paths.contains_key(&serde_yaml::Value::String("trusted_root".to_string())))
        .unwrap_or(false);
    if !has_explicit_trusted_root {
        return Err(LuxError::Config(
            "paths.trusted_root must be explicitly set in config.yaml; run `lux setup` or add paths.trusted_root and retry".to_string(),
        ));
    }

    let cfg: Config = serde_yaml::from_str(content)?;
    if cfg.version != 2 {
        return Err(LuxError::Config(format!(
            "unsupported config version {}",
            cfg.version
        )));
    }
    validate_config(&cfg)?;
    Ok(cfg)
}

fn read_config(path: &Path) -> Result<Config, LuxError> {
    let content = fs::read_to_string(path)?;
    read_config_from_str(&content)
}

fn validate_config(cfg: &Config) -> Result<(), LuxError> {
    if env::consts::OS != "macos" && env::consts::OS != "linux" {
        return Err(LuxError::Config(format!(
            "unsupported host operating system '{}'; supported: macos, linux",
            env::consts::OS
        )));
    }
    let _ = resolve_config_policy_paths(cfg)?;
    if cfg.collector.idle_timeout_min == 0 {
        return Err(LuxError::Config(
            "collector.idle_timeout_min must be greater than 0".to_string(),
        ));
    }
    if cfg.collector.rotate_every_min == 0 {
        return Err(LuxError::Config(
            "collector.rotate_every_min must be greater than 0".to_string(),
        ));
    }
    if cfg.harness.api_port == 0 {
        return Err(LuxError::Config(
            "harness.api_port must be greater than 0".to_string(),
        ));
    }
    if cfg.runtime_control_plane.socket_path.contains('\n')
        || cfg.runtime_control_plane.socket_path.contains('\r')
    {
        return Err(LuxError::Config(
            "runtime_control_plane.socket_path contains an invalid newline".to_string(),
        ));
    }
    #[cfg(unix)]
    {
        let configured = cfg.runtime_control_plane.socket_path.trim();
        if !configured.is_empty() {
            let expanded = PathBuf::from(expand_path(configured));
            if unix_socket_path_too_long(&expanded) {
                return Err(LuxError::Config(format!(
                    "runtime_control_plane.socket_path is too long for unix sockets ({} bytes); set a shorter path",
                    expanded.as_os_str().as_bytes().len()
                )));
            }
        }
    }
    if cfg.providers.is_empty() {
        return Err(LuxError::Config(
            "config.providers must contain at least one provider".to_string(),
        ));
    }
    for (name, provider) in &cfg.providers {
        if provider.commands.tui.trim().is_empty() {
            return Err(LuxError::Config(format!(
                "providers.{name}.commands.tui must be non-empty"
            )));
        }
        if provider.commands.run_template.trim().is_empty() {
            return Err(LuxError::Config(format!(
                "providers.{name}.commands.run_template must be non-empty"
            )));
        }
        if provider.auth.api_key.secrets_file.trim().is_empty() {
            return Err(LuxError::Config(format!(
                "providers.{name}.auth.api_key.secrets_file must be non-empty"
            )));
        }
        if provider.auth.api_key.env_key.trim().is_empty() {
            return Err(LuxError::Config(format!(
                "providers.{name}.auth.api_key.env_key must be non-empty"
            )));
        }
        if provider.auth.host_state.paths.is_empty() {
            return Err(LuxError::Config(format!(
                "providers.{name}.auth.host_state.paths must contain at least one path"
            )));
        }
        if provider.ownership.root_comm.is_empty() {
            return Err(LuxError::Config(format!(
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

fn current_primary_gid() -> u32 {
    #[cfg(unix)]
    {
        let output = Command::new("id").arg("-g").output();
        if let Ok(output) = output {
            if output.status.success() {
                let text = String::from_utf8_lossy(&output.stdout);
                if let Ok(value) = text.trim().parse::<u32>() {
                    return value;
                }
            }
        }
    }
    0
}

fn current_uid() -> u32 {
    #[cfg(unix)]
    {
        let output = Command::new("id").arg("-u").output();
        if let Ok(output) = output {
            if output.status.success() {
                let text = String::from_utf8_lossy(&output.stdout);
                if let Ok(value) = text.trim().parse::<u32>() {
                    return value;
                }
            }
        }
    }
    0
}

#[cfg(unix)]
fn unix_socket_path_too_long(path: &Path) -> bool {
    path.as_os_str().as_bytes().len() >= UNIX_SOCKET_PATH_LIMIT_BYTES
}

#[cfg(unix)]
fn stable_path_hash(path: &Path) -> u64 {
    // Deterministic FNV-1a so fallback runtime socket paths remain stable per trusted root.
    const OFFSET: u64 = 0xcbf29ce484222325;
    const PRIME: u64 = 0x0000_0100_0000_01b3;

    let mut hash = OFFSET;
    for byte in path.as_os_str().as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(PRIME);
    }
    hash
}

#[cfg(unix)]
fn runtime_socket_fallback_path(anchor: &Path) -> PathBuf {
    let hash = stable_path_hash(anchor);
    let uid = current_uid();
    let candidates = vec![
        env::temp_dir()
            .join(format!("lux-runtime-u{uid}"))
            .join(format!("{hash:016x}"))
            .join("control_plane.sock"),
        PathBuf::from(format!(
            "/tmp/lux-runtime-u{uid}/{hash:016x}/control_plane.sock"
        )),
        PathBuf::from(format!("/tmp/lux-{hash:016x}/control_plane.sock")),
    ];
    for candidate in candidates {
        if !unix_socket_path_too_long(&candidate) {
            return candidate;
        }
    }
    PathBuf::from("/tmp/lux.sock")
}

fn effective_runtime_socket_path(cfg: &Config) -> PathBuf {
    let configured = cfg.runtime_control_plane.socket_path.trim();
    if !configured.is_empty() {
        return PathBuf::from(expand_path(configured));
    }
    let trusted_root = PathBuf::from(expand_path(&cfg.paths.trusted_root));
    let preferred = trusted_root.join("runtime").join("control_plane.sock");
    #[cfg(unix)]
    {
        if unix_socket_path_too_long(&preferred) {
            return runtime_socket_fallback_path(&trusted_root);
        }
    }
    preferred
}

fn effective_runtime_socket_gid(cfg: &Config) -> u32 {
    cfg.runtime_control_plane
        .socket_gid
        .unwrap_or_else(current_primary_gid)
}

fn config_to_env(cfg: &Config) -> BTreeMap<String, String> {
    let mut envs = BTreeMap::new();
    let tag = if cfg.release.tag.trim().is_empty() {
        format!("v{}", env!("CARGO_PKG_VERSION"))
    } else {
        cfg.release.tag.trim().to_string()
    };
    envs.insert("LUX_VERSION".to_string(), tag);
    let trusted_root = PathBuf::from(expand_path(&cfg.paths.trusted_root));
    let state_dir = trusted_root.join("state");
    let secrets_dir = trusted_root.join("secrets");
    envs.insert("LUX_LOG_ROOT".to_string(), expand_path(&cfg.paths.log_root));
    envs.insert(
        "LUX_TRUSTED_ROOT".to_string(),
        trusted_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_STATE_DIR".to_string(),
        state_dir.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_SECRETS_DIR".to_string(),
        secrets_dir.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_SHIMS_BIN_DIR".to_string(),
        expand_path(&cfg.shims.bin_dir),
    );
    envs.insert(
        "LUX_WORKSPACE_ROOT".to_string(),
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
    let runtime_socket = effective_runtime_socket_path(cfg);
    if let Some(runtime_dir) = runtime_socket.parent() {
        envs.insert(
            "LUX_RUNTIME_DIR".to_string(),
            runtime_dir.to_string_lossy().to_string(),
        );
    }
    envs.insert(
        "LUX_RUNTIME_GID".to_string(),
        effective_runtime_socket_gid(cfg).to_string(),
    );
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

fn write_env_file(path: &Path, envs: &BTreeMap<String, String>) -> Result<(), LuxError> {
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
            let test_path = path.join(".lux_write_test");
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
) -> Result<(), LuxError> {
    let apply = !no_apply && !dry_run;
    if ctx.json && !defaults {
        return Err(LuxError::Process(
            "--json is only supported with `lux setup --defaults`".to_string(),
        ));
    }
    if !defaults && !io::stdin().is_terminal() {
        return Err(LuxError::Process(
            "interactive setup requires a TTY; re-run with `--defaults` for non-interactive mode"
                .to_string(),
        ));
    }

    let config_path = &ctx.config_path;
    let config_exists = config_path.exists();
    let home_for_display = required_home_dir().ok();
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
            return Err(LuxError::Config(format!(
                "config is invalid. Please edit {} and try again. ({})",
                display_path_with_home(config_path, home_for_display.as_deref()),
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
                return Err(LuxError::Process(format!(
                    "provider '{provider_name}' uses auth_mode=api_key but secrets file is missing at {}; set {} in your environment or create the secrets file manually",
                    display_path_with_home(&secrets_file, home_for_display.as_deref()),
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
        if let Ok(doctor_checks) = collect_doctor_checks(ctx, &base_cfg) {
            for check in doctor_checks.into_iter().filter(|check| !check.ok) {
                warnings.push(format!("doctor:{}: {}", check.id, check.message));
            }
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

    fn manual_secrets_instructions(
        env_key: &str,
        secrets_file: &Path,
        home_for_display: Option<&Path>,
    ) -> String {
        let dir = secrets_file.parent().unwrap_or_else(|| Path::new("."));
        format!(
            "mkdir -p {dir}\nchmod 700 {dir}\nprintf '{env_key}=%s\\n' 'YOUR_KEY' > {file}\nchmod 600 {file}",
            dir = display_path_with_home(dir, home_for_display),
            file = display_path_with_home(secrets_file, home_for_display),
            env_key = env_key
        )
    }

    fn print_step(step: usize, total: usize, title: &str) {
        println!();
        println!(
            "{} {}",
            style(format!("Lux Setup ({step}/{total})")).bold().cyan(),
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
    println!("{}", style("Lux Setup").bold().cyan());
    println!(
        "{}",
        style("Welcome to Lux! The blackbox for your ai agents. 
For when something goes wrong, and you don't know what your agent did.")
    );
    println!(
        "{}",
        style("
Without you touching your workflow, Lux automatically records
everything your agent does in each session. 

For when you want to:
- find that old conversation you forgot about 
- figure out what your agent has done while you weren't watching
- or even point your current agent session to the logs to help it debug

But before we start, we just have to answer four questions:
")
    );

/* TO DO: want a user input here for the user to click enter to confirm start*/


    // println!();
    // println!(
    //     "{}",
    //     style(format!(
    //         "you can manually edit the config file at: {}",
    //         display_path_with_home(config_path, home_for_display.as_deref())
    //     ))
    //     .dim()
    // );
    // println!(
    //     "{}",
    //     style("Updates config.yaml in place (preserves comments/formatting).").dim()
    // );
    // println!(
    //     "{}",
    //     style("Can optionally create provider secrets files (never prints secret values).").dim()
    // );

    let mut trusted_root_state = base_cfg.paths.trusted_root.clone();
    let mut log_root_state = base_cfg.paths.log_root.clone();
    let mut workspace_root_state = base_cfg.paths.workspace_root.clone();
    let mut shims_bin_dir_state = base_cfg.shims.bin_dir.clone();
    let mut provider_auth_state: BTreeMap<String, String> = BTreeMap::new();
    for (provider_name, provider) in &base_cfg.providers {
        provider_auth_state.insert(
            provider_name.clone(),
            provider.auth_mode.as_str().to_string(),
        );
    }

    let mut pending_secrets: Vec<PendingSecretWrite> = Vec::new();
    let mut missing_api_key_secrets: Vec<(String, String, PathBuf)> = Vec::new();
    let default_paths = computed_default_paths_for_current_os()?;

    let (patched_yaml, cfg_after_yaml, should_write_config) = loop {
        warnings.clear();
        pending_secrets.clear();
        missing_api_key_secrets.clear();

        print_step(1, total_steps, "Paths");
        println!(
            "{}",
            style("We need to decide:
- what folder your logs will be stored in
- what folders you want your agents to have access to
")
        );
        println!(
            "{}",
            style("Don't change the default log directory unless you have a good reason to")
        );
        println!(
            "{}",
            style(
                "Path policies for custom mounts:
- trusted_root must be outside $HOME
- log_root must be inside trusted_root
- shims.bin_dir must be inside trusted_root
- workspace_root must be under $HOME
- workspace_root must not overlap log_root or shims.bin_dir"
            )
            .dim()
        );
        println!(
            "{}",
            style(format!(
                "Default trusted root for this host: {}",
                default_paths.trusted_root
            ))
            .dim()
        );
        let previous_trusted_root = trusted_root_state.clone();
        trusted_root_state = Input::<String>::with_theme(&theme)
            .with_prompt("Select trusted root (outside $HOME)")
            .default(trusted_root_state.clone())
            .interact_text()?;

        let previous_default_log = Path::new(&previous_trusted_root)
            .join("logs")
            .to_string_lossy()
            .to_string();
        let previous_default_shims_bin = Path::new(&previous_trusted_root)
            .join("bin")
            .to_string_lossy()
            .to_string();
        let suggested_log_root = Path::new(&trusted_root_state)
            .join("logs")
            .to_string_lossy()
            .to_string();
        let suggested_shims_bin_dir = Path::new(&trusted_root_state)
            .join("bin")
            .to_string_lossy()
            .to_string();
        if trusted_root_state != previous_trusted_root {
            if log_root_state == previous_default_log || log_root_state == base_cfg.paths.log_root {
                log_root_state = suggested_log_root.clone();
            }
            if shims_bin_dir_state == previous_default_shims_bin
                || shims_bin_dir_state == base_cfg.shims.bin_dir
            {
                shims_bin_dir_state = suggested_shims_bin_dir.clone();
            }
        }

        println!(
            "{}",
            style(format!(
                "Default log root for this trusted root: {}",
                suggested_log_root
            ))
            .dim()
        );
        log_root_state = Input::<String>::with_theme(&theme)
            .with_prompt("Select log root (inside trusted root)")
            .default(log_root_state.clone())
            .interact_text()?;

        println!(
            "{}",
            style(format!(
                "Default shims bin dir for this trusted root: {}",
                suggested_shims_bin_dir
            ))
            .dim()
        );
        shims_bin_dir_state = Input::<String>::with_theme(&theme)
            .with_prompt("Select shims bin dir (inside trusted root)")
            .default(shims_bin_dir_state.clone())
            .interact_text()?;

        println!("{}", style("Great! Now choose your agent's workspace"));
        println!(
            "{}",
            style(
                "This is the host directory mounted into the agent container at /work.
For safety and policy compliance, workspace must be under $HOME."
            )
            .dim()
        );
        println!(
            "{}",
            style(format!(
                "Default workspace for this host: {}",
                display_path_with_home(
                    Path::new(&default_paths.workspace_root),
                    home_for_display.as_deref()
                )
            ))
            .dim()
        );
        workspace_root_state = Input::<String>::with_theme(&theme)
            .with_prompt("Select workspace root (under $HOME)")
            .default(workspace_root_state.clone())
            .interact_text()?;

        print_step(2, total_steps, "Provider Auth");
        println!("{}", style("Do you use an API key or not?") );
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
                            display_path_with_home(&host_path, home_for_display.as_deref())
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
                        display_path_with_home(&item.secrets_file, home_for_display.as_deref())
                    ))
                    .default(false)
                    .interact()?
            } else {
                Confirm::with_theme(&theme)
                    .with_prompt(format!(
                        "Create secrets file for provider '{}' at {} now?",
                        item.provider,
                        display_path_with_home(&item.secrets_file, home_for_display.as_deref())
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
        desired_cfg.paths.trusted_root = trusted_root_state.clone();
        desired_cfg.paths.log_root = log_root_state.clone();
        desired_cfg.paths.workspace_root = workspace_root_state.clone();
        desired_cfg.shims.bin_dir = shims_bin_dir_state.clone();
        for (provider_name, auth_mode) in &provider_auth_state {
            let provider = desired_cfg
                .providers
                .get_mut(provider_name)
                .ok_or_else(|| {
                    LuxError::Config(format!("provider missing from config: {provider_name}"))
                })?;
            provider.auth_mode = match auth_mode.as_str() {
                "api_key" => AuthMode::ApiKey,
                "host_state" => AuthMode::HostState,
                other => return Err(LuxError::Config(format!("unsupported auth_mode '{other}'"))),
            };
        }
        let resolved_policy_paths = match resolve_config_policy_paths(&desired_cfg) {
            Ok(paths) => paths,
            Err(err) => {
                println!();
                println!("{}", style("Path validation error").bold().red());
                println!("{}", style(err.to_string()).red());
                println!(
                    "{}",
                    style("Please update the path values and try again.")
                        .yellow()
                        .dim()
                );
                continue;
            }
        };
        validate_config(&desired_cfg)?;

        let mut yaml_edits = SetupYamlEdits::default();
        if desired_cfg.paths.trusted_root != base_cfg.paths.trusted_root {
            yaml_edits.trusted_root = Some(desired_cfg.paths.trusted_root.clone());
        }
        if desired_cfg.paths.log_root != base_cfg.paths.log_root {
            yaml_edits.log_root = Some(desired_cfg.paths.log_root.clone());
        }
        if desired_cfg.paths.workspace_root != base_cfg.paths.workspace_root {
            yaml_edits.workspace_root = Some(desired_cfg.paths.workspace_root.clone());
        }
        if desired_cfg.shims.bin_dir != base_cfg.shims.bin_dir {
            yaml_edits.shims_bin_dir = Some(desired_cfg.shims.bin_dir.clone());
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
        println!(
            "{} {}",
            style("Config:").bold(),
            display_path_with_home(config_path, home_for_display.as_deref())
        );

        println!("\n{}", style("Paths").bold());
        if desired_cfg.paths.trusted_root == base_cfg.paths.trusted_root {
            println!(
                "  {} {}",
                style("paths.trusted_root:").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.paths.trusted_root),
                    home_for_display.as_deref()
                ))
                .dim()
            );
        } else {
            println!(
                "  {} {} {} {}",
                style("paths.trusted_root:").dim(),
                style(display_path_with_home(
                    Path::new(&base_cfg.paths.trusted_root),
                    home_for_display.as_deref()
                ))
                .dim(),
                style("->").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.paths.trusted_root),
                    home_for_display.as_deref()
                ))
                .green()
            );
        }
        println!(
            "  {} {}",
            style("resolved trusted root:").dim(),
            style(display_path_with_home(
                &resolved_policy_paths.trusted_root,
                home_for_display.as_deref()
            ))
            .dim()
        );
        if desired_cfg.paths.log_root == base_cfg.paths.log_root {
            println!(
                "  {} {}",
                style("paths.log_root:").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.paths.log_root),
                    home_for_display.as_deref()
                ))
                .dim()
            );
        } else {
            println!(
                "  {} {} {} {}",
                style("paths.log_root:").dim(),
                style(display_path_with_home(
                    Path::new(&base_cfg.paths.log_root),
                    home_for_display.as_deref()
                ))
                .dim(),
                style("->").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.paths.log_root),
                    home_for_display.as_deref()
                ))
                .green()
            );
        }
        println!(
            "  {} {}",
            style("resolved log root:").dim(),
            style(display_path_with_home(
                &resolved_policy_paths.log_root,
                home_for_display.as_deref()
            ))
            .dim()
        );
        if desired_cfg.paths.workspace_root == base_cfg.paths.workspace_root {
            println!(
                "  {} {}",
                style("paths.workspace_root:").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.paths.workspace_root),
                    home_for_display.as_deref()
                ))
                .dim()
            );
        } else {
            println!(
                "  {} {} {} {}",
                style("paths.workspace_root:").dim(),
                style(display_path_with_home(
                    Path::new(&base_cfg.paths.workspace_root),
                    home_for_display.as_deref()
                ))
                .dim(),
                style("->").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.paths.workspace_root),
                    home_for_display.as_deref()
                ))
                .green()
            );
        }
        println!(
            "  {} {}",
            style("resolved workspace root:").dim(),
            style(display_path_with_home(
                &resolved_policy_paths.workspace_root,
                home_for_display.as_deref()
            ))
            .dim()
        );
        if desired_cfg.shims.bin_dir == base_cfg.shims.bin_dir {
            println!(
                "  {} {}",
                style("shims.bin_dir:").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.shims.bin_dir),
                    home_for_display.as_deref()
                ))
                .dim()
            );
        } else {
            println!(
                "  {} {} {} {}",
                style("shims.bin_dir:").dim(),
                style(display_path_with_home(
                    Path::new(&base_cfg.shims.bin_dir),
                    home_for_display.as_deref()
                ))
                .dim(),
                style("->").dim(),
                style(display_path_with_home(
                    Path::new(&desired_cfg.shims.bin_dir),
                    home_for_display.as_deref()
                ))
                .green()
            );
        }
        println!(
            "  {} {}",
            style("resolved shims bin dir:").dim(),
            style(display_path_with_home(
                &resolved_policy_paths.shims_bin_dir,
                home_for_display.as_deref()
            ))
            .dim()
        );

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
                    style(display_path_with_home(
                        &item.path,
                        home_for_display.as_deref()
                    ))
                    .dim(),
                );
            }
            for (provider_name, env_key, secrets_file) in &missing_api_key_secrets {
                println!(
                    "  {} {} {}",
                    style(format!("{provider_name}:")).dim(),
                    style("missing").red(),
                    style(format!(
                        "{env_key} at {}",
                        display_path_with_home(secrets_file, home_for_display.as_deref())
                    ))
                    .dim(),
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
                        manual_secrets_instructions(
                            env_key,
                            secrets_file,
                            home_for_display.as_deref()
                        )
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
            style(
                "Manual secrets next steps (required before `lux up --provider <name>` will work):"
            )
            .yellow()
            .bold()
        );
        for (provider_name, env_key, secrets_file) in &missing_api_key_secrets {
            println!(
                "\n{} {}:\n{}",
                style("Provider").dim(),
                style(format!("'{provider_name}' ({env_key})")).bold(),
                manual_secrets_instructions(env_key, secrets_file, home_for_display.as_deref())
            );
        }
    }

    if apply {
        println!();
        println!("{}", style("Applying config...").cyan().bold());
        let _ = apply_config(ctx, &cfg_after_yaml)?;
    }
    if let Ok(doctor_checks) = collect_doctor_checks(ctx, &cfg_after_yaml) {
        let failed: Vec<DoctorCheck> = doctor_checks
            .into_iter()
            .filter(|check| !check.ok)
            .collect();
        if !failed.is_empty() {
            println!();
            println!("{}", style("Readiness findings").bold().yellow());
            for check in failed {
                println!("  - {} ({}) {}", check.id, check.severity, check.message);
                println!("    remediation: {}", check.remediation);
            }
        }
    }
    println!();
    println!("{}", style("That's it!"));
    println!(
        "{}",
        style("Now go spin up Lux and start keeping track of your agents.").dim()
    );
    println!(
        "{}",
        style("Install shims once, then keep using your provider CLIs as usual.").dim()
    );

    println!();
    println!("{}", style("Next steps").bold().cyan());
    let provider_names: Vec<String> = cfg_after_yaml.providers.keys().cloned().collect();
    if !apply {
        println!("  lux config apply");
    }
    println!("  lux runtime up");
    println!("  lux ui up --wait");
    println!("  lux shim enable");
    if cfg_after_yaml.providers.contains_key("codex") {
        println!("  codex");
    } else if let Some(example) = cfg_after_yaml.providers.keys().next() {
        println!("  {example}");
    }
    println!("  Available providers: {}", provider_names.join(", "));

    if let Ok(policy) = resolve_config_policy_paths(&cfg_after_yaml) {
        let needs_path_fix = cfg_after_yaml.providers.keys().any(|provider| {
            let shim_path = shim_path_for_provider(&policy.shims_bin_dir, provider);
            let (path_precedence_ok, _) = shim_path_precedence_ok(provider, &shim_path);
            !path_precedence_ok
        });
        if needs_path_fix {
            println!();
            println!("{}", style("PATH remediation").bold().yellow());
            println!(
                "  Put {} first in PATH before other provider binaries.",
                display_path_with_home(&policy.shims_bin_dir, home_for_display.as_deref())
            );
            println!("  Re-run: lux doctor --strict");
        }
    }

    Ok(())
}

fn handle_config(ctx: &Context, command: ConfigCommand) -> Result<(), LuxError> {
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
                    .map_err(|err| LuxError::Process(format!("failed to launch editor: {err}")))?;
                if !status.success() {
                    return Err(LuxError::Process("editor exited with error".to_string()));
                }
                output(ctx, json!({"path": ctx.config_path}))
            } else {
                Err(LuxError::Process(
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
                    return Err(LuxError::Config(format!(
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

fn apply_config(ctx: &Context, cfg: &Config) -> Result<(PathBuf, PathBuf), LuxError> {
    fn create_log_root_with_guidance(log_root: &Path) -> Result<(), LuxError> {
        fs::create_dir_all(log_root).map_err(|err| {
            if err.kind() == io::ErrorKind::PermissionDenied {
                if env::consts::OS == "linux" && log_root.starts_with(Path::new("/var/lib/lux")) {
                    return LuxError::Config(format!(
                        "failed to create paths.log_root at {}: permission denied.\n\
Linux default log root often needs a one-time setup:\n  sudo mkdir -p /var/lib/lux/logs\n  sudo chown -R $USER /var/lib/lux/logs\n\
Then re-run `lux config apply`.",
                        log_root.display()
                    ));
                }
                return LuxError::Config(format!(
                    "failed to create paths.log_root at {}: permission denied.\n\
Choose a writable log root outside $HOME or create this directory with sufficient permissions.",
                    log_root.display()
                ));
            }
            LuxError::Io(err)
        })
    }

    fn create_dir_with_guidance(field: &str, path: &Path) -> Result<(), LuxError> {
        fs::create_dir_all(path).map_err(|err| {
            if err.kind() == io::ErrorKind::PermissionDenied {
                if env::consts::OS == "linux" && path.starts_with(Path::new("/var/lib/lux")) {
                    return LuxError::Config(format!(
                        "failed to create {field} at {}: permission denied.\n\
Linux default trusted root often needs a one-time setup:\n  sudo mkdir -p /var/lib/lux\n  sudo chown -R $USER /var/lib/lux\n\
Then re-run `lux config apply`.",
                        path.display()
                    ));
                }
                return LuxError::Config(format!(
                    "failed to create {field} at {}: permission denied.\n\
Choose a writable trusted root outside $HOME or create this directory with sufficient permissions.",
                    path.display()
                ));
            }
            LuxError::Io(err)
        })
    }

    let policy_paths = resolve_config_policy_paths(cfg)?;
    let mut envs = config_to_env(cfg);
    envs.insert(
        "LUX_LOG_ROOT".to_string(),
        policy_paths.log_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_WORKSPACE_ROOT".to_string(),
        policy_paths.workspace_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_TRUSTED_ROOT".to_string(),
        policy_paths.trusted_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_STATE_DIR".to_string(),
        policy_paths.state_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_RUNTIME_DIR".to_string(),
        policy_paths.runtime_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_SECRETS_DIR".to_string(),
        policy_paths.secrets_root.to_string_lossy().to_string(),
    );
    envs.insert(
        "LUX_SHIMS_BIN_DIR".to_string(),
        policy_paths.shims_bin_dir.to_string_lossy().to_string(),
    );
    write_env_file(&ctx.env_file, &envs)?;
    let log_root = policy_paths.log_root;
    create_log_root_with_guidance(&log_root)?;
    create_dir_with_guidance("paths.trusted_root", &policy_paths.trusted_root)?;
    create_dir_with_guidance("state root", &policy_paths.state_root)?;
    create_dir_with_guidance("runtime root", &policy_paths.runtime_root)?;
    create_dir_with_guidance("secrets root", &policy_paths.secrets_root)?;
    create_dir_with_guidance("shims.bin_dir", &policy_paths.shims_bin_dir)?;
    let workspace_root = policy_paths.workspace_root;
    fs::create_dir_all(&workspace_root).map_err(|err| {
        if err.kind() == io::ErrorKind::PermissionDenied {
            return LuxError::Config(format!(
                "failed to create paths.workspace_root at {}: permission denied.\n\
Choose a writable workspace under $HOME.",
                workspace_root.display()
            ));
        }
        LuxError::Io(err)
    })?;
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

fn write_atomic_text_file(path: &Path, content: &str, mode: Option<u32>) -> Result<(), LuxError> {
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
            .unwrap_or_else(|| "lux".to_string()),
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
) -> Result<(), LuxError> {
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
) -> Result<(), LuxError> {
    if path.exists() && !overwrite_allowed {
        return Err(LuxError::Process(format!(
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
        return Err(LuxError::Config(
            "provider env_key must be non-empty".to_string(),
        ));
    }
    let quoted = shell_single_quote(value);
    let content = format!("{env_key}={quoted}\n");
    write_atomic_text_file(path, &content, Some(0o600))
}

#[derive(Debug, Clone, Default)]
struct SetupYamlEdits {
    trusted_root: Option<String>,
    log_root: Option<String>,
    workspace_root: Option<String>,
    shims_bin_dir: Option<String>,
    provider_auth_modes: BTreeMap<String, String>,
    provider_api_key_secrets_files: BTreeMap<String, String>,
}

fn is_blank_or_comment(line: &str) -> bool {
    let trimmed = line.trim();
    trimmed.is_empty() || trimmed.starts_with('#')
}

fn leading_space_count(line: &str) -> Result<usize, LuxError> {
    let mut count = 0usize;
    for ch in line.chars() {
        match ch {
            ' ' => count += 1,
            '\t' => {
                return Err(LuxError::Config(
                    "tabs are not supported in config.yaml indentation".to_string(),
                ))
            }
            _ => break,
        }
    }
    Ok(count)
}

fn match_block_key_line(line: &str, key: &str) -> Result<Option<usize>, LuxError> {
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

fn match_scalar_key_line(line: &str, key: &str) -> Result<Option<usize>, LuxError> {
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
) -> Result<(usize, usize, usize), LuxError> {
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
    Err(LuxError::Config(format!(
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
) -> Result<(String, bool), LuxError> {
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
        return Err(LuxError::Config(format!(
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
) -> Result<bool, LuxError> {
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
    Err(LuxError::Config(format!(
        "could not find scalar key '{key}:' within YAML block"
    )))
}

fn patch_setup_config_yaml(
    content: &str,
    edits: &SetupYamlEdits,
) -> Result<(String, bool), LuxError> {
    let mut lines: Vec<String> = content.split('\n').map(|s| s.to_string()).collect();
    // `split('\n')` leaves a trailing empty line if the input ends with '\n'. We'll normalize to
    // always end with one newline when writing back.
    if lines.last().map(|s| s.is_empty()).unwrap_or(false) {
        // Keep the trailing empty line as a sentinel and patch within it safely.
    }

    let mut changed = false;

    if edits.trusted_root.is_some() || edits.log_root.is_some() || edits.workspace_root.is_some() {
        let (_paths_line, paths_body_start, paths_body_end) =
            find_block_range(&lines, 0, "paths", 0)?;
        let paths_indent = 0usize;
        if let Some(value) = edits.trusted_root.as_deref() {
            changed |= patch_scalar_in_block(
                &mut lines,
                paths_body_start,
                paths_body_end,
                paths_indent,
                "trusted_root",
                value,
            )?;
        }
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

    if let Some(value) = edits.shims_bin_dir.as_deref() {
        let (_shims_line, shims_body_start, shims_body_end) =
            find_block_range(&lines, 0, "shims", 0)?;
        changed |= patch_scalar_in_block(
            &mut lines,
            shims_body_start,
            shims_body_end,
            0usize,
            "bin_dir",
            value,
        )?;
    }

    if !edits.provider_auth_modes.is_empty() || !edits.provider_api_key_secrets_files.is_empty() {
        let (_providers_line, providers_body_start, providers_body_end) =
            find_block_range(&lines, 0, "providers", 0)?;
        let providers_indent = 0usize;
        let mut provider_names = std::collections::BTreeSet::new();
        provider_names.extend(edits.provider_auth_modes.keys().cloned());
        provider_names.extend(edits.provider_api_key_secrets_files.keys().cloned());
        for provider_name in provider_names {
            // Find provider block within providers block.
            let mut provider_line_idx: Option<usize> = None;
            for idx in providers_body_start..providers_body_end {
                let line = &lines[idx];
                let Some(indent) = match_block_key_line(line, &provider_name)? else {
                    continue;
                };
                if indent <= providers_indent {
                    continue;
                }
                provider_line_idx = Some(idx);
                break;
            }
            let Some(provider_line_idx) = provider_line_idx else {
                return Err(LuxError::Config(format!(
                    "could not find provider block '{}:' in config.yaml",
                    &provider_name
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
            if let Some(auth_mode) = edits.provider_auth_modes.get(&provider_name) {
                changed |= patch_scalar_in_block(
                    &mut lines,
                    provider_body_start,
                    provider_body_end,
                    provider_indent,
                    "auth_mode",
                    auth_mode,
                )?;
            }
            if let Some(secrets_file) = edits.provider_api_key_secrets_files.get(&provider_name) {
                changed |= patch_scalar_in_block(
                    &mut lines,
                    provider_body_start,
                    provider_body_end,
                    provider_indent,
                    "secrets_file",
                    secrets_file,
                )?;
            }
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
    base.push(".lux");
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
    trusted_root: PathBuf,
    runtime_dir: PathBuf,
    runtime_socket_path: PathBuf,
    runtime_pid_path: PathBuf,
    runtime_events_path: PathBuf,
    state_dir: PathBuf,
    state_active_run_path: PathBuf,
    state_active_provider_path: PathBuf,
    secrets_dir: PathBuf,
    shim_bin_dir: PathBuf,
    log_root: PathBuf,
    workspace_root: PathBuf,
    install_dir: PathBuf,
    versions_dir: PathBuf,
    current_link: PathBuf,
    bin_dir: PathBuf,
    bin_path: PathBuf,
}

fn resolve_runtime_paths(ctx: &Context) -> Result<(RuntimePaths, bool), LuxError> {
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
    let runtime_socket_path = effective_runtime_socket_path(&cfg);
    let runtime_dir = runtime_socket_path
        .parent()
        .map(PathBuf::from)
        .unwrap_or_else(|| policy_paths.runtime_root.clone());
    let install_dir = default_install_dir();
    let versions_dir = install_dir.join("versions");
    let current_link = install_dir.join("current");
    let bin_dir = default_bin_dir();
    let bin_path = bin_dir.join("lux");
    Ok((
        RuntimePaths {
            config_dir,
            config_path: ctx.config_path.clone(),
            env_file: ctx.env_file.clone(),
            bundle_dir: ctx.bundle_dir.clone(),
            trusted_root: policy_paths.trusted_root.clone(),
            runtime_dir: runtime_dir.clone(),
            runtime_socket_path: runtime_socket_path.clone(),
            runtime_pid_path: runtime_dir.join("control_plane.pid"),
            runtime_events_path: runtime_dir.join("events.jsonl"),
            state_dir: policy_paths.state_root.clone(),
            state_active_run_path: active_run_state_path(&policy_paths.state_root),
            state_active_provider_path: active_provider_state_path(&policy_paths.state_root),
            secrets_dir: policy_paths.secrets_root.clone(),
            shim_bin_dir: policy_paths.shims_bin_dir.clone(),
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

fn release_platform() -> Result<(String, String), LuxError> {
    let os = match env::consts::OS {
        "macos" => "darwin",
        "linux" => "linux",
        value => {
            return Err(LuxError::Config(format!(
                "unsupported operating system for update: {value}"
            )))
        }
    };
    let arch = match env::consts::ARCH {
        "x86_64" => "amd64",
        "aarch64" => "arm64",
        value => {
            return Err(LuxError::Config(format!(
                "unsupported architecture for update: {value}"
            )))
        }
    };
    Ok((os.to_string(), arch.to_string()))
}

fn release_base_url_root() -> String {
    let raw = env::var("LUX_RELEASE_BASE_URL")
        .unwrap_or_else(|_| "https://github.com/scottmaran/lux/releases/download".to_string());
    raw.trim_end_matches('/').to_string()
}

fn build_update_plan(paths: &RuntimePaths, target_version: &str) -> Result<UpdatePlan, LuxError> {
    let target_version_tag = target_version.trim_start_matches('v').to_string();
    let (os, arch) = release_platform()?;
    let bundle_name = format!("lux_{}_{}_{}.tar.gz", target_version_tag, os, arch);
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

fn list_installed_version_tags(paths: &RuntimePaths) -> Result<Vec<String>, LuxError> {
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

fn fetch_latest_release_tag() -> Result<String, LuxError> {
    let url = "https://api.github.com/repos/scottmaran/lux/releases/latest";
    let client = reqwest::blocking::Client::new();
    let response = client
        .get(url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", "lux-cli")
        .send()?;
    let status = response.status();
    if !status.is_success() {
        let body = response.text().unwrap_or_default();
        return Err(LuxError::Process(format!(
            "failed to resolve latest release: HTTP {} {}",
            status, body
        )));
    }
    let payload: GitHubReleasePayload = response.json()?;
    Ok(normalize_version_tag(&payload.tag_name))
}

fn download_file(url: &str, path: &Path) -> Result<(), LuxError> {
    let client = reqwest::blocking::Client::new();
    let response = client.get(url).header("User-Agent", "lux-cli").send()?;
    let status = response.status();
    if !status.is_success() {
        let body = response.text().unwrap_or_default();
        return Err(LuxError::Process(format!(
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

fn sha256_file(path: &Path) -> Result<String, LuxError> {
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
    Err(LuxError::Process(
        "no SHA256 tool found (expected shasum, sha256sum, or openssl)".to_string(),
    ))
}

fn verify_bundle_checksum(bundle_path: &Path, checksum_path: &Path) -> Result<(), LuxError> {
    let checksum_content = fs::read_to_string(checksum_path)?;
    let Some(expected) = parse_checksum(&checksum_content) else {
        return Err(LuxError::Process(format!(
            "invalid checksum file: {}",
            checksum_path.display()
        )));
    };
    let actual = sha256_file(bundle_path)?;
    if expected != actual {
        return Err(LuxError::Process(format!(
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

fn tar_list_entries(bundle_path: &Path) -> Result<Vec<String>, LuxError> {
    let output = Command::new("tar")
        .arg("-tzf")
        .arg(bundle_path)
        .output()
        .map_err(|err| LuxError::Process(format!("failed to run tar: {err}")))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(LuxError::Process(format!(
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
                // Allow only top-level directory marker entries (e.g. "lux_0.1.0_darwin_arm64").
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

fn extract_bundle(bundle_path: &Path, destination_dir: &Path) -> Result<(), LuxError> {
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
        .map_err(|err| LuxError::Process(format!("failed to run tar: {err}")))?;
    if !status.success() {
        return Err(LuxError::Process(format!(
            "tar extraction failed with status {status}"
        )));
    }
    Ok(())
}

fn force_symlink(target: &Path, link_path: &Path) -> Result<(), LuxError> {
    ensure_parent(link_path)?;
    match fs::symlink_metadata(link_path) {
        Ok(meta) => {
            if meta.file_type().is_symlink() || meta.file_type().is_file() {
                fs::remove_file(link_path)?;
            } else {
                return Err(LuxError::Process(format!(
                    "refusing to replace directory with symlink: {}",
                    link_path.display()
                )));
            }
        }
        Err(err) if err.kind() == io::ErrorKind::NotFound => {}
        Err(err) => return Err(LuxError::Io(err)),
    }
    #[cfg(unix)]
    {
        symlink(target, link_path)?;
        return Ok(());
    }
    #[allow(unreachable_code)]
    Err(LuxError::Config(
        "update is not supported on this platform".to_string(),
    ))
}

fn temp_download_dir() -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    env::temp_dir().join(format!("lux-update-{}-{}", std::process::id(), nanos))
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
) -> Result<Vec<PathBuf>, LuxError> {
    let files = configured_compose_files(ctx, ui, runtime_overrides);
    for path in &files {
        if !path.exists() {
            return Err(LuxError::Config(format!(
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
) -> Result<Vec<String>, LuxError> {
    let files = compose_files(ctx, ui, runtime_overrides)?;
    if !ctx.env_file.exists() {
        let policy_paths = resolve_config_policy_paths(cfg)?;
        let mut envs = config_to_env(cfg);
        envs.insert(
            "LUX_LOG_ROOT".to_string(),
            policy_paths.log_root.to_string_lossy().to_string(),
        );
        envs.insert(
            "LUX_WORKSPACE_ROOT".to_string(),
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
) -> Result<LifecycleTarget, LuxError> {
    if collector_only {
        if provider.is_some() {
            return Err(LuxError::Config(
                "--collector-only conflicts with --provider".to_string(),
            ));
        }
        return Ok(LifecycleTarget::CollectorOnly);
    }
    let provider = provider.ok_or_else(|| {
        LuxError::Config("missing required --provider for this command".to_string())
    })?;
    if provider.trim().is_empty() {
        return Err(LuxError::Config("--provider must be non-empty".to_string()));
    }
    Ok(LifecycleTarget::Provider(provider))
}

fn provider_from_config<'a>(cfg: &'a Config, provider: &str) -> Result<&'a Provider, LuxError> {
    cfg.providers.get(provider).ok_or_else(|| {
        LuxError::Config(format!(
            "provider '{provider}' is not defined in config.providers"
        ))
    })
}

fn active_provider_state_path(state_root: &Path) -> PathBuf {
    state_root.join(".active_provider.json")
}

fn load_active_provider_state(state_root: &Path) -> Result<Option<ActiveProviderState>, LuxError> {
    let state_path = active_provider_state_path(state_root);
    if !state_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&state_path)?;
    let parsed: ActiveProviderState = serde_json::from_str(&content)?;
    Ok(Some(parsed))
}

fn write_active_provider_state(
    state_root: &Path,
    provider: &str,
    auth_mode: &AuthMode,
    run_id: &str,
) -> Result<(), LuxError> {
    fs::create_dir_all(state_root)?;
    let state = ActiveProviderState {
        provider: provider.to_string(),
        auth_mode: auth_mode.as_str().to_string(),
        run_id: run_id.to_string(),
        started_at: Utc::now().to_rfc3339(),
    };
    let path = active_provider_state_path(state_root);
    let tmp_path = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&state)?;
    fs::write(&tmp_path, format!("{body}\n"))?;
    fs::rename(&tmp_path, &path)?;
    Ok(())
}

fn clear_active_provider_state(state_root: &Path) -> Result<(), LuxError> {
    let path = active_provider_state_path(state_root);
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
    tui_cmd_override: Option<&str>,
) -> Result<ProviderRuntimeCompose, LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let runtime_dir = resolve_config_policy_paths(&cfg)?.runtime_root;
    fs::create_dir_all(&runtime_dir)?;

    let override_file = runtime_dir.join(format!("compose.provider.{provider_name}.yml"));
    let mut warnings = Vec::new();

    let mut agent = ComposeServiceOverride::default();
    let mut harness = ComposeServiceOverride::default();

    harness.environment.push(format!(
        "HARNESS_TUI_CMD={}",
        tui_cmd_override.unwrap_or(provider.commands.tui.as_str())
    ));
    harness.environment.push(format!(
        "HARNESS_RUN_CMD_TEMPLATE={}",
        provider.commands.run_template
    ));

    agent
        .environment
        .push(format!("LUX_PROVIDER={provider_name}"));
    agent
        .environment
        .push(format!("LUX_AUTH_MODE={}", provider.auth_mode.as_str()));
    agent.environment.push(format!(
        "LUX_PROVIDER_MOUNT_HOST_STATE_IN_API_MODE={}",
        if provider.mount_host_state_in_api_mode {
            "true"
        } else {
            "false"
        }
    ));
    agent.environment.push(format!(
        "LUX_PROVIDER_ENV_KEY={}",
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
            let mount_dst = format!("/run/lux/provider_host_state/{host_state_count}");
            agent
                .volumes
                .push(format!("{}:{}:ro", host_path.to_string_lossy(), mount_dst));
            agent.environment.push(format!(
                "LUX_PROVIDER_HOST_STATE_SRC_{host_state_count}={mount_dst}"
            ));
            agent.environment.push(format!(
                "LUX_PROVIDER_HOST_STATE_DST_{host_state_count}={}",
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
    agent
        .environment
        .push(format!("LUX_PROVIDER_HOST_STATE_COUNT={host_state_count}"));

    if provider.auth_mode == AuthMode::ApiKey {
        let secrets_file = PathBuf::from(expand_path(&provider.auth.api_key.secrets_file));
        if !secrets_file.exists() {
            return Err(LuxError::Config(format!(
                "provider '{provider_name}': API secrets file not found: {}",
                secrets_file.display()
            )));
        }
        if !secrets_file.is_file() {
            return Err(LuxError::Config(format!(
                "provider '{provider_name}': API secrets path is not a file: {}",
                secrets_file.display()
            )));
        }
        let container_secrets = "/run/lux/provider_secrets.env";
        agent.volumes.push(format!(
            "{}:{}:ro",
            secrets_file.to_string_lossy(),
            container_secrets
        ));
        agent
            .environment
            .push(format!("LUX_PROVIDER_SECRETS_FILE={container_secrets}"));
    } else {
        agent
            .environment
            .push("LUX_PROVIDER_SECRETS_FILE=".to_string());
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
    format!("lux__{}", Utc::now().format("%Y_%m_%d_%H_%M_%S"))
}

fn active_run_state_path(state_root: &Path) -> PathBuf {
    state_root.join(".active_run.json")
}

fn load_active_run_state(state_root: &Path) -> Result<Option<ActiveRunState>, LuxError> {
    let state_path = active_run_state_path(state_root);
    if !state_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&state_path)?;
    let parsed: ActiveRunState = serde_json::from_str(&content)?;
    Ok(Some(parsed))
}

fn write_active_run_state(
    state_root: &Path,
    run_id: &str,
    workspace_root: &Path,
) -> Result<(), LuxError> {
    fs::create_dir_all(state_root)?;
    let state = ActiveRunState {
        run_id: run_id.to_string(),
        started_at: Utc::now().to_rfc3339(),
        workspace_root: Some(workspace_root.to_string_lossy().to_string()),
    };
    let path = active_run_state_path(state_root);
    let tmp_path = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(&state)?;
    fs::write(&tmp_path, format!("{body}\n"))?;
    fs::rename(&tmp_path, &path)?;
    Ok(())
}

fn clear_active_run_state(state_root: &Path) -> Result<(), LuxError> {
    let path = active_run_state_path(state_root);
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn run_root(log_root: &Path, run_id: &str) -> PathBuf {
    log_root.join(run_id)
}

fn list_run_ids(log_root: &Path) -> Result<Vec<String>, LuxError> {
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
        if name.starts_with("lux__") {
            run_ids.push(name);
        }
    }
    run_ids.sort();
    Ok(run_ids)
}

fn resolve_latest_run_id(log_root: &Path) -> Result<Option<String>, LuxError> {
    let runs = list_run_ids(log_root)?;
    Ok(runs.last().cloned())
}

fn compose_env_for_run(
    run_id: Option<&str>,
    workspace_root: Option<&Path>,
) -> BTreeMap<String, String> {
    let mut envs = BTreeMap::new();
    if let Some(run_id) = run_id {
        envs.insert("LUX_RUN_ID".to_string(), run_id.to_string());
    }
    if let Some(workspace_root) = workspace_root {
        envs.insert(
            "LUX_WORKSPACE_ROOT".to_string(),
            workspace_root.to_string_lossy().to_string(),
        );
    }
    envs
}

fn resolve_default_run_id(log_root: &Path, state_root: &Path) -> Result<String, LuxError> {
    match load_active_run_state(state_root)? {
        Some(state) => {
            if run_root(log_root, &state.run_id).exists() {
                Ok(state.run_id)
            } else {
                clear_active_run_state(state_root)?;
                Err(LuxError::Process(
                    "no active run found; use --run-id or --latest".to_string(),
                ))
            }
        }
        None => Err(LuxError::Process(
            "no active run found; use --run-id or --latest".to_string(),
        )),
    }
}

fn resolve_run_id_from_selector(
    log_root: &Path,
    state_root: &Path,
    run_id: Option<&str>,
    latest: bool,
) -> Result<String, LuxError> {
    if let Some(run_id) = run_id {
        if !run_root(log_root, run_id).exists() {
            return Err(LuxError::Process(format!("run not found: {run_id}")));
        }
        return Ok(run_id.to_string());
    }
    if latest {
        return resolve_latest_run_id(log_root)?.ok_or_else(|| {
            LuxError::Process("no run directories found under log root".to_string())
        });
    }
    resolve_default_run_id(log_root, state_root)
}

fn validate_workspace_policy(
    workspace_root: &Path,
    home: &Path,
    log_root: &Path,
    field: &str,
) -> Result<(), LuxError> {
    if !path_is_within(workspace_root, home) {
        return Err(LuxError::Config(format!(
            "{field} must be under $HOME (home={}, workspace={})",
            display_path_with_home(home, Some(home)),
            display_path_with_home(workspace_root, Some(home))
        )));
    }
    if path_is_within(workspace_root, log_root) || path_is_within(log_root, workspace_root) {
        return Err(LuxError::Config(format!(
            "{field} must not overlap log root (workspace={}, log_root={})",
            display_path_with_home(workspace_root, Some(home)),
            display_path_with_home(log_root, Some(home))
        )));
    }
    Ok(())
}

fn resolve_effective_workspace_root(
    cfg: &Config,
    workspace_override: Option<&str>,
) -> Result<PathBuf, LuxError> {
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
) -> Result<PathBuf, LuxError> {
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
) -> Result<PathBuf, LuxError> {
    let policy = resolve_config_policy_paths(cfg)?;
    let host_start_dir = match start_dir {
        Some(raw) => resolve_policy_path(raw, "--start-dir", &policy.home)?,
        None => {
            let cwd = env::current_dir().map_err(|err| {
                LuxError::Process(format!(
                    "failed to resolve current working directory for default --start-dir: {}",
                    err
                ))
            })?;
            canonicalize_policy_path(&cwd, "current working directory")
                .map_err(|err| LuxError::Process(err.to_string()))?
        }
    };
    if !path_is_within(&host_start_dir, workspace_root) {
        return Err(LuxError::Config(format!(
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
) -> Result<String, LuxError> {
    let relative = host_start_dir.strip_prefix(workspace_root).map_err(|_| {
        LuxError::Config(format!(
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
) -> Result<Vec<String>, LuxError> {
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
) -> Result<bool, LuxError> {
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
) -> Result<bool, LuxError> {
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

fn provider_mismatch_error(active_provider: &str, requested_provider: &str) -> LuxError {
    LuxError::Process(format!(
        "provider mismatch: active provider is '{active_provider}', requested '{requested_provider}'. \
Run `lux down --provider {active_provider}` first."
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
            partial_outcome: None,
        };
    }
    ProcessErrorDetails {
        error_code: "process_command_failed".to_string(),
        hint: None,
        command: Some(command.to_string()),
        raw_stderr: None,
        partial_outcome: None,
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
) -> Result<CommandOutput, LuxError> {
    let command = render_docker_command(args);
    let cmd_output = runner
        .run(args, &ctx.bundle_dir, env_overrides, capture_output)
        .map_err(|err| {
            let details = docker_spawn_error_details(&err, &command);
            LuxError::ProcessDetailed {
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
        return Err(LuxError::ProcessDetailed {
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
                partial_outcome: None,
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
) -> Result<(), LuxError> {
    let _ = execute_docker(ctx, runner, args, env_overrides, capture_output, true)?;
    output(ctx, json_payload)
}

fn append_harness_tui_run_args(args: &mut Vec<String>, container_workdir: &str) {
    args.push("run".to_string());
    args.push("--rm".to_string());
    args.push("-e".to_string());
    args.push("HARNESS_MODE=tui".to_string());
    args.push("-e".to_string());
    args.push(format!("HARNESS_AGENT_WORKDIR={container_workdir}"));
    args.push("harness".to_string());
}

fn handle_ui<R: DockerRunner>(
    ctx: &Context,
    command: UiCommand,
    runner: &R,
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    match command {
        UiCommand::Up {
            wait,
            timeout_sec,
            pull,
        } => {
            if timeout_sec.is_some() && !wait {
                return Err(LuxError::Config(
                    "--timeout-sec requires --wait".to_string(),
                ));
            }
            let mut args = compose_base_args(ctx, &cfg, true, &[])?;
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
            args.push("ui".to_string());
            run_docker_command(
                ctx,
                runner,
                &args,
                &BTreeMap::new(),
                json!({"action":"ui_up"}),
                true,
            )
        }
        UiCommand::Down => {
            let mut args = compose_base_args(ctx, &cfg, true, &[])?;
            args.push("stop".to_string());
            args.push("ui".to_string());
            run_docker_command(
                ctx,
                runner,
                &args,
                &BTreeMap::new(),
                json!({"action":"ui_down"}),
                true,
            )
        }
        UiCommand::Status => {
            let mut args = compose_base_args(ctx, &cfg, true, &[])?;
            args.push("ps".to_string());
            args.push("--format".to_string());
            args.push("json".to_string());
            args.push("ui".to_string());
            let cmd_output = execute_docker(ctx, runner, &args, &BTreeMap::new(), true, false)?;
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
        UiCommand::Url => {
            let payload = json!({"url":"http://127.0.0.1:8090"});
            output(ctx, payload)
        }
    }
}

#[cfg(unix)]
fn set_path_group(path: &Path, gid: u32) -> Result<(), LuxError> {
    let status = Command::new("chgrp")
        .arg(gid.to_string())
        .arg(path)
        .status()
        .map_err(|err| {
            LuxError::Process(format!(
                "failed to run chgrp for {}: {}",
                path.display(),
                err
            ))
        })?;
    if !status.success() {
        return Err(LuxError::Process(format!(
            "failed to set group {} on {}; check runtime_control_plane.socket_gid and filesystem permissions",
            gid,
            path.display()
        )));
    }
    Ok(())
}

#[cfg(unix)]
fn ensure_runtime_permissions(
    cfg: &Config,
    runtime_dir: &Path,
    socket_path: Option<&Path>,
) -> Result<(), LuxError> {
    use std::os::unix::fs::PermissionsExt;

    fs::create_dir_all(runtime_dir)?;
    fs::set_permissions(runtime_dir, fs::Permissions::from_mode(0o770))?;
    let gid = effective_runtime_socket_gid(cfg);
    if cfg.runtime_control_plane.socket_gid.is_some() {
        set_path_group(runtime_dir, gid)?;
    } else {
        let _ = set_path_group(runtime_dir, gid);
    }
    if let Some(socket_path) = socket_path {
        fs::set_permissions(socket_path, fs::Permissions::from_mode(0o660))?;
        if cfg.runtime_control_plane.socket_gid.is_some() {
            set_path_group(socket_path, gid)?;
        } else {
            let _ = set_path_group(socket_path, gid);
        }
    }
    Ok(())
}

fn process_is_alive(pid: u32) -> bool {
    if pid == 0 {
        return false;
    }
    Command::new("kill")
        .arg("-0")
        .arg(pid.to_string())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn read_pid_file(path: &Path) -> Option<u32> {
    let text = fs::read_to_string(path).ok()?;
    text.trim().parse::<u32>().ok()
}

fn runtime_cleanup_artifacts(paths: &RuntimePaths) {
    let _ = fs::remove_file(&paths.runtime_socket_path);
    let _ = fs::remove_file(&paths.runtime_pid_path);
}

fn runtime_emit_event(
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
    events_path: &Path,
    event_type: &str,
    severity: &str,
    payload: serde_json::Value,
) -> Result<RuntimeEvent, LuxError> {
    let (lock, condvar) = &**shared;
    let mut state = lock
        .lock()
        .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
    state.next_event_id = state.next_event_id.saturating_add(1);
    let event = RuntimeEvent {
        id: state.next_event_id,
        ts: Utc::now().to_rfc3339(),
        event_type: event_type.to_string(),
        severity: severity.to_string(),
        payload,
    };
    state.events.push_back(event.clone());
    while state.events.len() > 512 {
        let _ = state.events.pop_front();
    }
    condvar.notify_all();
    drop(state);

    ensure_parent(events_path)?;
    let line = serde_json::to_string(&event)?;
    let mut content = line;
    content.push('\n');
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(events_path)?;
    file.write_all(content.as_bytes())?;
    Ok(event)
}

fn runtime_emit_warning(
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
    events_path: &Path,
    message: &str,
) -> Result<(), LuxError> {
    let warning = RuntimeWarning {
        ts: Utc::now().to_rfc3339(),
        message: message.to_string(),
    };
    {
        let (lock, _) = &**shared;
        let mut state = lock
            .lock()
            .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
        state.warnings.push_back(warning);
        while state.warnings.len() > 128 {
            let _ = state.warnings.pop_front();
        }
    }
    let _ = runtime_emit_event(
        shared,
        events_path,
        "collector.lag.degradation",
        "warn",
        json!({ "message": message }),
    )?;
    Ok(())
}

fn runtime_command_event_type(
    argv: &[String],
    status_code: i32,
) -> Option<(&'static str, &'static str)> {
    let ok = status_code == 0;
    let has = |flag: &str| argv.iter().any(|item| item == flag);
    let cmd = argv
        .iter()
        .find(|item| !item.starts_with('-'))
        .map(|s| s.as_str())
        .unwrap_or("");
    match cmd {
        "up" if has("--collector-only") => Some(("run.started", if ok { "info" } else { "error" })),
        "down" if has("--collector-only") => {
            Some(("run.stopped", if ok { "info" } else { "error" }))
        }
        "up" if has("--provider") => Some(("session.started", if ok { "info" } else { "error" })),
        "down" if has("--provider") => Some(("session.ended", if ok { "info" } else { "error" })),
        "run" => Some(("job.completed", if ok { "info" } else { "error" })),
        _ => None,
    }
}

fn runtime_record_command_events(
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
    events_path: &Path,
    argv: &[String],
    status_code: i32,
) -> Result<(), LuxError> {
    if argv.iter().any(|item| item == "run") {
        let _ = runtime_emit_event(
            shared,
            events_path,
            "job.submitted",
            "info",
            json!({"argv": argv}),
        )?;
    }
    if let Some((event_type, severity)) = runtime_command_event_type(argv, status_code) {
        let _ = runtime_emit_event(
            shared,
            events_path,
            event_type,
            severity,
            json!({"argv": argv, "status_code": status_code}),
        )?;
    }
    Ok(())
}

fn runtime_run_cli_subprocess(ctx: &Context, argv: &[String]) -> Result<CommandOutput, LuxError> {
    let exe = env::current_exe()?;
    let mut cmd = Command::new(exe);
    cmd.args(argv);
    cmd.env(RUNTIME_BYPASS_ENV, "1");
    cmd.env("LUX_CONFIG", ctx.config_path.to_string_lossy().to_string());
    cmd.env("LUX_ENV_FILE", ctx.env_file.to_string_lossy().to_string());
    cmd.env(
        "LUX_BUNDLE_DIR",
        ctx.bundle_dir.to_string_lossy().to_string(),
    );
    let output = cmd
        .output()
        .map_err(|err| LuxError::Process(format!("failed to run delegated command: {err}")))?;
    let status_code = output
        .status
        .code()
        .unwrap_or(if output.status.success() { 0 } else { 1 });
    Ok(CommandOutput {
        status_code,
        stdout: output.stdout,
        stderr: output.stderr,
    })
}

#[derive(Debug)]
struct RuntimeIncomingRequest {
    method: String,
    path: String,
    query: BTreeMap<String, String>,
    headers: BTreeMap<String, String>,
    body: Vec<u8>,
}

fn parse_query_map(query: &str) -> BTreeMap<String, String> {
    let mut result = BTreeMap::new();
    for pair in query.split('&') {
        if pair.trim().is_empty() {
            continue;
        }
        if let Some((key, value)) = pair.split_once('=') {
            result.insert(key.to_string(), value.to_string());
        } else {
            result.insert(pair.to_string(), String::new());
        }
    }
    result
}

#[cfg(unix)]
fn runtime_read_http_request(
    stream: &mut UnixStream,
) -> Result<Option<RuntimeIncomingRequest>, LuxError> {
    stream
        .set_read_timeout(Some(Duration::from_secs(10)))
        .map_err(LuxError::Io)?;
    let mut buf = Vec::new();
    let mut header_end: Option<usize> = None;
    let mut chunk = [0u8; 1024];
    while header_end.is_none() {
        let read = stream.read(&mut chunk)?;
        if read == 0 {
            if buf.is_empty() {
                return Ok(None);
            }
            break;
        }
        buf.extend_from_slice(&chunk[..read]);
        if let Some(pos) = buf.windows(4).position(|window| window == b"\r\n\r\n") {
            header_end = Some(pos);
        }
        if buf.len() > 1024 * 1024 {
            return Err(LuxError::Process(
                "runtime request headers too large".to_string(),
            ));
        }
    }
    let header_end = header_end
        .ok_or_else(|| LuxError::Process("runtime request missing header delimiter".to_string()))?;
    let header_text = String::from_utf8_lossy(&buf[..header_end]);
    let mut lines = header_text.lines();
    let request_line = lines
        .next()
        .ok_or_else(|| LuxError::Process("runtime request missing request line".to_string()))?;
    let mut request_parts = request_line.split_whitespace();
    let method = request_parts
        .next()
        .ok_or_else(|| LuxError::Process("runtime request missing method".to_string()))?
        .to_string();
    let target = request_parts
        .next()
        .ok_or_else(|| LuxError::Process("runtime request missing target".to_string()))?;
    let (path, query) = if let Some((path, query)) = target.split_once('?') {
        (path.to_string(), parse_query_map(query))
    } else {
        (target.to_string(), BTreeMap::new())
    };
    let mut headers = BTreeMap::new();
    for line in lines {
        if let Some((key, value)) = line.split_once(':') {
            headers.insert(key.trim().to_ascii_lowercase(), value.trim().to_string());
        }
    }
    let content_length = headers
        .get("content-length")
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(0);
    let body_start = header_end + 4;
    while buf.len() < body_start + content_length {
        let read = stream.read(&mut chunk)?;
        if read == 0 {
            break;
        }
        buf.extend_from_slice(&chunk[..read]);
    }
    if buf.len() < body_start + content_length {
        return Err(LuxError::Process(
            "runtime request ended before full body was received".to_string(),
        ));
    }
    let body = buf[body_start..body_start + content_length].to_vec();
    Ok(Some(RuntimeIncomingRequest {
        method,
        path,
        query,
        headers,
        body,
    }))
}

#[cfg(unix)]
fn runtime_write_json_response(
    stream: &mut UnixStream,
    status: u16,
    payload: &serde_json::Value,
) -> Result<(), LuxError> {
    let status_text = match status {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        500 => "Internal Server Error",
        503 => "Service Unavailable",
        _ => "OK",
    };
    let body = serde_json::to_vec(payload)?;
    let header = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        status,
        status_text,
        body.len()
    );
    stream.write_all(header.as_bytes())?;
    stream.write_all(&body)?;
    Ok(())
}

#[cfg(unix)]
fn runtime_write_text_response(
    stream: &mut UnixStream,
    status: u16,
    content_type: &str,
    body: &str,
) -> Result<(), LuxError> {
    let status_text = match status {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        500 => "Internal Server Error",
        503 => "Service Unavailable",
        _ => "OK",
    };
    let bytes = body.as_bytes();
    let header = format!(
        "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        status,
        status_text,
        content_type,
        bytes.len()
    );
    stream.write_all(header.as_bytes())?;
    stream.write_all(bytes)?;
    Ok(())
}

#[cfg(unix)]
fn runtime_send_sse_event(stream: &mut UnixStream, event: &RuntimeEvent) -> Result<(), LuxError> {
    let data = serde_json::to_string(event)?;
    let frame = format!(
        "id: {}\nevent: {}\ndata: {}\n\n",
        event.id, event.event_type, data
    );
    stream.write_all(frame.as_bytes())?;
    stream.flush()?;
    Ok(())
}

fn runtime_collect_stack_status(
    ctx: &Context,
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
) -> Result<serde_json::Value, LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let runner = RealDockerRunner;
    let policy = resolve_config_policy_paths(&cfg)?;
    let active_run = load_active_run_state(&policy.state_root)?;
    let active_run_id = active_run.as_ref().map(|state| state.run_id.clone());
    let active_workspace = active_run
        .as_ref()
        .map(|state| resolve_active_run_workspace_root(&cfg, state))
        .transpose()?;
    let run_env = compose_env_for_run(active_run_id.as_deref(), active_workspace.as_deref());
    let collector_running =
        collector_is_running(ctx, &runner, &cfg, false, &run_env).unwrap_or(false);
    let provider_running =
        provider_plane_is_running(ctx, &runner, &cfg, false, &run_env).unwrap_or(false);
    let ui_running = running_services(ctx, &runner, &cfg, true, &[], &BTreeMap::new(), &["ui"])
        .map(|rows| rows.iter().any(|item| item == "ui"))
        .unwrap_or(false);
    let rotation_pending = {
        let (lock, _) = &**shared;
        let state = lock
            .lock()
            .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
        state.rotation_pending
    };
    Ok(json!({
        "runtime": {
            "socket_path": effective_runtime_socket_path(&cfg),
            "auto_started": true
        },
        "stack": {
            "collector_running": collector_running,
            "provider_running": provider_running,
            "ui_running": ui_running,
            "rotation_pending": rotation_pending,
            "active_run_id": active_run_id
        }
    }))
}

fn runtime_collect_run_status(
    ctx: &Context,
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
) -> Result<serde_json::Value, LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let active = load_active_run_state(&policy.state_root)?;
    let pending_rotation = {
        let (lock, _) = &**shared;
        let state = lock
            .lock()
            .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
        state.rotation_pending
    };
    if let Some(active) = active {
        return Ok(json!({
            "active_run": active,
            "pending_rotation": pending_rotation,
            "rotate_every_min": cfg.collector.rotate_every_min
        }));
    }
    Ok(json!({
        "active_run": null,
        "pending_rotation": pending_rotation,
        "rotate_every_min": cfg.collector.rotate_every_min
    }))
}

fn runtime_collect_session_job_status(ctx: &Context) -> Result<serde_json::Value, LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let active = load_active_run_state(&policy.state_root)?;
    let Some(active) = active else {
        return Ok(json!({
            "active_run_id": null,
            "sessions": {"count": 0},
            "jobs": {"count": 0, "running": 0, "finished": 0}
        }));
    };
    let run_root = run_root(&log_root, &active.run_id);
    let sessions_dir = run_root.join("harness").join("sessions");
    let jobs_dir = run_root.join("harness").join("jobs");
    let session_count = fs::read_dir(&sessions_dir)
        .ok()
        .map(|entries| {
            entries
                .filter_map(Result::ok)
                .filter(|entry| entry.file_type().map(|t| t.is_dir()).unwrap_or(false))
                .count()
        })
        .unwrap_or(0);
    let mut job_count = 0usize;
    let mut running = 0usize;
    let mut finished = 0usize;
    if let Ok(entries) = fs::read_dir(&jobs_dir) {
        for entry in entries.flatten() {
            if !entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                continue;
            }
            job_count += 1;
            let status_path = entry.path().join("status.json");
            let status_value = read_json_value(&status_path);
            let state = status_value
                .as_ref()
                .and_then(|value| value.get("status"))
                .and_then(|value| value.as_str())
                .unwrap_or_default()
                .to_string();
            if state.eq_ignore_ascii_case("running") || state.eq_ignore_ascii_case("submitted") {
                running += 1;
            } else if !state.is_empty() {
                finished += 1;
            }
        }
    }
    Ok(json!({
        "active_run_id": active.run_id,
        "sessions": {"count": session_count},
        "jobs": {"count": job_count, "running": running, "finished": finished}
    }))
}

fn runtime_collect_collector_pipeline(ctx: &Context) -> Result<serde_json::Value, LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let active = load_active_run_state(&policy.state_root)?;
    let Some(active) = active else {
        return Ok(json!({"active_run_id": null, "pipeline": []}));
    };
    let run_root = run_root(&log_root, &active.run_id);
    let pipeline_files = vec![
        (
            "raw.audit",
            run_root.join("collector").join("raw").join("audit.log"),
        ),
        (
            "raw.ebpf",
            run_root.join("collector").join("raw").join("ebpf.jsonl"),
        ),
        (
            "filtered.timeline",
            run_root
                .join("collector")
                .join("filtered")
                .join("filtered_timeline.jsonl"),
        ),
    ];
    let mut rows = Vec::new();
    for (name, path) in pipeline_files {
        let meta = fs::metadata(&path).ok();
        let size_bytes = meta.as_ref().map(|m| m.len()).unwrap_or(0);
        let modified = meta
            .and_then(|m| m.modified().ok())
            .map(DateTime::<Utc>::from)
            .map(|dt| dt.to_rfc3339());
        rows.push(json!({
            "name": name,
            "path": path,
            "present": path.exists(),
            "size_bytes": size_bytes,
            "modified_at": modified
        }));
    }
    Ok(json!({
        "active_run_id": active.run_id,
        "pipeline": rows
    }))
}

fn runtime_collect_warnings(
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
) -> Result<serde_json::Value, LuxError> {
    let (lock, _) = &**shared;
    let state = lock
        .lock()
        .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
    Ok(json!({
        "warnings": state.warnings,
        "recent_errors": state.events.iter().rev().filter(|event| event.severity == "error").take(20).cloned().collect::<Vec<RuntimeEvent>>()
    }))
}

fn read_json_value(path: &Path) -> Option<serde_json::Value> {
    let content = fs::read_to_string(path).ok()?;
    serde_json::from_str(&content).ok()
}

fn parse_rfc3339_utc(value: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(value)
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
}

fn runtime_scheduler_tick(
    ctx: &Context,
    shared: &Arc<(Mutex<RuntimeSharedState>, Condvar)>,
    events_path: &Path,
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let runner = RealDockerRunner;
    let active = load_active_run_state(&resolve_config_policy_paths(&cfg)?.state_root)?;
    let Some(active) = active else {
        return Ok(());
    };
    let active_workspace = resolve_active_run_workspace_root(&cfg, &active)?;
    let run_env = compose_env_for_run(Some(&active.run_id), Some(&active_workspace));
    let provider_running =
        provider_plane_is_running(ctx, &runner, &cfg, false, &run_env).unwrap_or(false);
    let collector_running =
        collector_is_running(ctx, &runner, &cfg, false, &run_env).unwrap_or(false);

    {
        let (lock, _) = &**shared;
        let mut state = lock
            .lock()
            .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
        if provider_running {
            state.last_provider_activity_at = Some(Utc::now().to_rfc3339());
        }
    }

    if collector_running && !provider_running {
        let idle_ref = {
            let (lock, _) = &**shared;
            let state = lock
                .lock()
                .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
            state
                .last_provider_activity_at
                .as_ref()
                .and_then(|value| parse_rfc3339_utc(value))
        }
        .or_else(|| parse_rfc3339_utc(&active.started_at));
        if let Some(idle_since) = idle_ref {
            let idle_age = Utc::now() - idle_since;
            if idle_age.num_minutes() >= cfg.collector.idle_timeout_min as i64 {
                let output = runtime_run_cli_subprocess(
                    ctx,
                    &["down".to_string(), "--collector-only".to_string()],
                )?;
                if output.status_code == 0 {
                    let _ = runtime_emit_event(
                        shared,
                        events_path,
                        "run.stopped",
                        "info",
                        json!({"reason":"idle_timeout", "idle_timeout_min": cfg.collector.idle_timeout_min}),
                    );
                } else {
                    let _ = runtime_emit_warning(
                        shared,
                        events_path,
                        "collector idle-timeout stop failed; collector left running",
                    );
                }
            }
        }
    }

    let active_started = parse_rfc3339_utc(&active.started_at);
    if let Some(started_at) = active_started {
        let run_age = Utc::now() - started_at;
        if run_age.num_minutes() >= cfg.collector.rotate_every_min as i64 {
            if provider_running {
                let should_emit = {
                    let (lock, _) = &**shared;
                    let mut state = lock.lock().map_err(|_| {
                        LuxError::Process("runtime state lock poisoned".to_string())
                    })?;
                    let already_pending = state.rotation_pending;
                    state.rotation_pending = true;
                    !already_pending
                };
                if should_emit {
                    let _ = runtime_emit_event(
                        shared,
                        events_path,
                        "collector.lag.degradation",
                        "warn",
                        json!({"reason":"rotation_deferred_provider_active"}),
                    );
                }
            } else if collector_running {
                let _ = runtime_emit_event(
                    shared,
                    events_path,
                    "run.stopped",
                    "info",
                    json!({"reason":"rotation_cutover_start", "run_id": active.run_id}),
                );
                let stop_out = runtime_run_cli_subprocess(
                    ctx,
                    &["down".to_string(), "--collector-only".to_string()],
                )?;
                thread::sleep(Duration::from_secs(2));
                let start_out = runtime_run_cli_subprocess(
                    ctx,
                    &[
                        "up".to_string(),
                        "--collector-only".to_string(),
                        "--wait".to_string(),
                    ],
                )?;
                if stop_out.status_code == 0 && start_out.status_code == 0 {
                    {
                        let (lock, _) = &**shared;
                        let mut state = lock.lock().map_err(|_| {
                            LuxError::Process("runtime state lock poisoned".to_string())
                        })?;
                        state.rotation_pending = false;
                    }
                    let _ = runtime_emit_event(
                        shared,
                        events_path,
                        "run.started",
                        "info",
                        json!({"reason":"rotation_cutover_complete"}),
                    );
                } else {
                    let _ = runtime_emit_event(
                        shared,
                        events_path,
                        "attribution.uncertainty.warning",
                        "error",
                        json!({"reason":"rotation_cutover_failed"}),
                    );
                    let _ = runtime_emit_warning(
                        shared,
                        events_path,
                        "rotation cutover failed; active run may require manual recovery",
                    );
                }
            }
        }
    }

    Ok(())
}

fn runtime_scheduler_loop(
    ctx: Context,
    shared: Arc<(Mutex<RuntimeSharedState>, Condvar)>,
    events_path: PathBuf,
) {
    loop {
        {
            let (lock, _) = &*shared;
            let state = match lock.lock() {
                Ok(state) => state,
                Err(_) => return,
            };
            if state.shutdown {
                return;
            }
        }
        if let Err(err) = runtime_scheduler_tick(&ctx, &shared, &events_path) {
            let _ = runtime_emit_warning(
                &shared,
                &events_path,
                &format!("runtime scheduler tick failed: {err}"),
            );
        }
        thread::sleep(Duration::from_secs(30));
    }
}

#[cfg(unix)]
fn runtime_handle_connection(
    mut stream: UnixStream,
    ctx: Context,
    shared: Arc<(Mutex<RuntimeSharedState>, Condvar)>,
    events_path: PathBuf,
) -> Result<(), LuxError> {
    let request = runtime_read_http_request(&mut stream)?;
    let Some(request) = request else {
        return Ok(());
    };
    match (request.method.as_str(), request.path.as_str()) {
        ("GET", "/v1/healthz") => {
            runtime_write_json_response(
                &mut stream,
                200,
                &json!({
                    "ok": true,
                    "ts": Utc::now().to_rfc3339(),
                }),
            )?;
        }
        ("GET", "/v1/stack/status") => {
            let payload = runtime_collect_stack_status(&ctx, &shared)?;
            runtime_write_json_response(&mut stream, 200, &payload)?;
        }
        ("GET", "/v1/run/status") => {
            let payload = runtime_collect_run_status(&ctx, &shared)?;
            runtime_write_json_response(&mut stream, 200, &payload)?;
        }
        ("GET", "/v1/session-job/status") => {
            let payload = runtime_collect_session_job_status(&ctx)?;
            runtime_write_json_response(&mut stream, 200, &payload)?;
        }
        ("GET", "/v1/collector/pipeline/status") => {
            let payload = runtime_collect_collector_pipeline(&ctx)?;
            runtime_write_json_response(&mut stream, 200, &payload)?;
        }
        ("GET", "/v1/warnings") => {
            let payload = runtime_collect_warnings(&shared)?;
            runtime_write_json_response(&mut stream, 200, &payload)?;
        }
        ("GET", "/v1/events") => {
            let mut last_event_id = request
                .headers
                .get("last-event-id")
                .and_then(|value| value.parse::<u64>().ok())
                .unwrap_or(0);
            if let Some(value) = request.query.get("last_event_id") {
                if let Ok(parsed) = value.parse::<u64>() {
                    last_event_id = parsed;
                }
            }
            let header = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n";
            stream.write_all(header.as_bytes())?;
            loop {
                let (pending, shutdown) = {
                    let (lock, condvar) = &*shared;
                    let mut state = lock.lock().map_err(|_| {
                        LuxError::Process("runtime state lock poisoned".to_string())
                    })?;
                    let available: Vec<RuntimeEvent> = state
                        .events
                        .iter()
                        .filter(|event| event.id > last_event_id)
                        .cloned()
                        .collect();
                    if available.is_empty() && !state.shutdown {
                        let (guard, _) = condvar
                            .wait_timeout(state, Duration::from_secs(15))
                            .map_err(|_| {
                                LuxError::Process("runtime condition wait failed".to_string())
                            })?;
                        state = guard;
                    }
                    let events: Vec<RuntimeEvent> = state
                        .events
                        .iter()
                        .filter(|event| event.id > last_event_id)
                        .cloned()
                        .collect();
                    (events, state.shutdown)
                };
                if pending.is_empty() {
                    if shutdown {
                        break;
                    }
                    stream.write_all(b": keepalive\n\n")?;
                    stream.flush()?;
                    continue;
                }
                for event in pending {
                    last_event_id = event.id;
                    runtime_send_sse_event(&mut stream, &event)?;
                }
                if shutdown {
                    break;
                }
            }
        }
        ("POST", "/v1/execute") => {
            let request_body: RuntimeExecuteRequest = serde_json::from_slice(&request.body)
                .map_err(|err| {
                    LuxError::Process(format!("invalid runtime execute request body: {err}"))
                })?;
            if request_body.argv.is_empty() {
                return runtime_write_json_response(
                    &mut stream,
                    400,
                    &json!({"error":"argv must not be empty"}),
                );
            }
            let output = runtime_run_cli_subprocess(&ctx, &request_body.argv)?;
            let _ = runtime_record_command_events(
                &shared,
                &events_path,
                &request_body.argv,
                output.status_code,
            );
            if request_body.argv.iter().any(|item| item == "--provider")
                || request_body.argv.iter().any(|item| item == "run")
            {
                let (lock, _) = &*shared;
                let mut state = lock
                    .lock()
                    .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
                state.last_provider_activity_at = Some(Utc::now().to_rfc3339());
            }
            runtime_write_json_response(
                &mut stream,
                200,
                &json!({
                    "status_code": output.status_code,
                    "stdout": String::from_utf8_lossy(&output.stdout),
                    "stderr": String::from_utf8_lossy(&output.stderr)
                }),
            )?;
        }
        ("POST", "/v1/runtime/down") => {
            {
                let (lock, condvar) = &*shared;
                let mut state = lock
                    .lock()
                    .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
                state.shutdown = true;
                condvar.notify_all();
            }
            let _ = runtime_emit_event(
                &shared,
                &events_path,
                "runtime.stopped",
                "info",
                json!({"reason":"runtime_down_requested"}),
            );
            runtime_write_json_response(&mut stream, 200, &json!({"ok": true}))?;
        }
        _ => {
            runtime_write_text_response(
                &mut stream,
                404,
                "application/json",
                "{\"error\":\"not found\"}",
            )?;
        }
    }
    Ok(())
}

fn runtime_status_payload(ctx: &Context) -> Result<serde_json::Value, LuxError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    let running = runtime_ping(ctx).is_ok();
    let pid = read_pid_file(&paths.runtime_pid_path);
    Ok(json!({
        "running": running,
        "socket_path": paths.runtime_socket_path,
        "pid_path": paths.runtime_pid_path,
        "pid": pid
    }))
}

fn runtime_up_internal(ctx: &Context, emit_output: bool) -> Result<(), LuxError> {
    #[cfg(not(unix))]
    {
        let _ = (ctx, emit_output);
        return Err(LuxError::Config(
            "runtime control plane is only supported on unix hosts".to_string(),
        ));
    }
    #[cfg(unix)]
    {
        let cfg = if ctx.config_path.exists() {
            read_config(&ctx.config_path)?
        } else {
            Config::default()
        };
        let (paths, _) = resolve_runtime_paths(ctx)?;
        if runtime_ping(ctx).is_ok() {
            if emit_output {
                return output(
                    ctx,
                    json!({"running": true, "already_running": true, "socket_path": paths.runtime_socket_path}),
                );
            }
            return Ok(());
        }
        if let Some(pid) = read_pid_file(&paths.runtime_pid_path) {
            if process_is_alive(pid) {
                return Err(LuxError::Process(format!(
                    "runtime pid {} is alive but socket {} is unavailable; run `lux runtime down` and retry",
                    pid,
                    paths.runtime_socket_path.display()
                )));
            }
        }
        runtime_cleanup_artifacts(&paths);
        ensure_runtime_permissions(&cfg, &paths.runtime_dir, None)?;
        let exe = env::current_exe()?;
        let mut cmd = Command::new(exe);
        cmd.arg("--config").arg(&ctx.config_path);
        cmd.arg("--env-file").arg(&ctx.env_file);
        cmd.arg("--bundle-dir").arg(&ctx.bundle_dir);
        for compose_override in &ctx.compose_file_overrides {
            cmd.arg("--compose-file").arg(compose_override);
        }
        cmd.arg("runtime").arg("serve");
        cmd.env(RUNTIME_BYPASS_ENV, "1");
        cmd.stdin(Stdio::null());
        cmd.stdout(Stdio::null());
        cmd.stderr(Stdio::null());
        let mut child = cmd.spawn().map_err(|err| {
            LuxError::Process(format!("failed to start runtime control plane: {err}"))
        })?;

        let mut started = false;
        for _ in 0..300 {
            thread::sleep(Duration::from_millis(100));
            if runtime_ping(ctx).is_ok() {
                started = true;
                break;
            }
            if let Some(status) = child.try_wait()? {
                return Err(LuxError::Process(format!(
                    "runtime control plane exited before ready (status: {}); try `lux runtime serve` for direct diagnostics",
                    status
                )));
            }
        }
        if !started {
            return Err(LuxError::Process(format!(
                "runtime control plane did not become ready at {}",
                paths.runtime_socket_path.display()
            )));
        }
        if emit_output {
            output(
                ctx,
                json!({
                    "running": true,
                    "already_running": false,
                    "socket_path": paths.runtime_socket_path
                }),
            )?;
        }
        Ok(())
    }
}

fn runtime_down_internal(ctx: &Context) -> Result<(), LuxError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    if runtime_ping(ctx).is_ok() {
        let response = runtime_control_plane_request(
            ctx,
            "POST",
            "/v1/runtime/down",
            &[("Content-Type".to_string(), "application/json".to_string())],
            Some(b"{}"),
        )?;
        if response.status >= 400 {
            return Err(LuxError::Process(format!(
                "runtime down failed with status {}",
                response.status
            )));
        }
        for _ in 0..30 {
            thread::sleep(Duration::from_millis(100));
            if runtime_ping(ctx).is_err() {
                break;
            }
        }
    }
    runtime_cleanup_artifacts(&paths);
    output(
        ctx,
        json!({"running": false, "socket_path": paths.runtime_socket_path}),
    )
}

fn runtime_serve(ctx: &Context) -> Result<(), LuxError> {
    #[cfg(not(unix))]
    {
        let _ = ctx;
        return Err(LuxError::Config(
            "runtime control plane is only supported on unix hosts".to_string(),
        ));
    }
    #[cfg(unix)]
    {
        let cfg = if ctx.config_path.exists() {
            read_config(&ctx.config_path)?
        } else {
            Config::default()
        };
        let (paths, _) = resolve_runtime_paths(ctx)?;
        ensure_runtime_permissions(&cfg, &paths.runtime_dir, None)?;
        let _ = fs::remove_file(&paths.runtime_socket_path);
        let listener = UnixListener::bind(&paths.runtime_socket_path)?;
        listener.set_nonblocking(true)?;
        ensure_runtime_permissions(&cfg, &paths.runtime_dir, Some(&paths.runtime_socket_path))?;
        write_atomic_text_file(
            &paths.runtime_pid_path,
            &format!("{}\n", std::process::id()),
            Some(0o660),
        )?;

        let shared: Arc<(Mutex<RuntimeSharedState>, Condvar)> =
            Arc::new((Mutex::new(RuntimeSharedState::default()), Condvar::new()));
        let _ = runtime_emit_event(
            &shared,
            &paths.runtime_events_path,
            "runtime.started",
            "info",
            json!({"socket_path": paths.runtime_socket_path}),
        );
        let scheduler_shared = Arc::clone(&shared);
        let scheduler_ctx = ctx.clone();
        let scheduler_events = paths.runtime_events_path.clone();
        let scheduler_handle = thread::spawn(move || {
            runtime_scheduler_loop(scheduler_ctx, scheduler_shared, scheduler_events)
        });

        loop {
            {
                let (lock, _) = &*shared;
                let state = lock
                    .lock()
                    .map_err(|_| LuxError::Process("runtime state lock poisoned".to_string()))?;
                if state.shutdown {
                    break;
                }
            }
            match listener.accept() {
                Ok((stream, _addr)) => {
                    let ctx_clone = ctx.clone();
                    let shared_clone = Arc::clone(&shared);
                    let events_clone = paths.runtime_events_path.clone();
                    thread::spawn(move || {
                        let _ = runtime_handle_connection(
                            stream,
                            ctx_clone,
                            shared_clone,
                            events_clone,
                        );
                    });
                }
                Err(err) if err.kind() == io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_millis(100));
                }
                Err(err) => {
                    let _ = runtime_emit_warning(
                        &shared,
                        &paths.runtime_events_path,
                        &format!("runtime listener accept failed: {err}"),
                    );
                    thread::sleep(Duration::from_millis(250));
                }
            }
        }

        {
            let (lock, condvar) = &*shared;
            if let Ok(mut state) = lock.lock() {
                state.shutdown = true;
                condvar.notify_all();
            }
        }
        let _ = scheduler_handle.join();
        runtime_cleanup_artifacts(&paths);
        Ok(())
    }
}

fn handle_runtime(ctx: &Context, command: RuntimeCommand) -> Result<(), LuxError> {
    match command {
        RuntimeCommand::Up => runtime_up_internal(ctx, true),
        RuntimeCommand::Down => runtime_down_internal(ctx),
        RuntimeCommand::Status => output(ctx, runtime_status_payload(ctx)?),
        RuntimeCommand::Serve => runtime_serve(ctx),
    }
}

const SHIM_MARKER: &str = "# lux-shim";
const SHIM_PATH_BEGIN_MARKER: &str = "# >>> lux-shim-path >>>";
const SHIM_PATH_END_MARKER: &str = "# <<< lux-shim-path <<<";

#[derive(Debug, Clone, Copy)]
enum ShimPathAction {
    Enable,
    Disable,
}

impl ShimPathAction {
    fn action_id(self) -> &'static str {
        match self {
            Self::Enable => "shim_enable",
            Self::Disable => "shim_disable",
        }
    }

    fn command_name(self) -> &'static str {
        match self {
            Self::Enable => "lux shim enable",
            Self::Disable => "lux shim disable",
        }
    }
}

#[derive(Debug, Clone)]
struct ShimPathFileStatus {
    path: PathBuf,
    existed: bool,
    managed_block_present: bool,
    changed: bool,
    error: Option<String>,
}

#[derive(Debug, Clone)]
struct ShimPathPhase {
    ok: bool,
    state: String,
    files: Vec<ShimPathFileStatus>,
    rolled_back: Option<bool>,
}

fn resolve_shim_providers(cfg: &Config, providers: Vec<String>) -> Vec<String> {
    if providers.is_empty() {
        return cfg.providers.keys().cloned().collect();
    }
    let mut seen = std::collections::BTreeSet::new();
    let mut ordered = Vec::new();
    for provider in providers {
        if seen.insert(provider.clone()) {
            ordered.push(provider);
        }
    }
    ordered
}

fn resolve_shim_providers_or_error(
    cfg: &Config,
    providers: Vec<String>,
    action: &str,
) -> Result<Vec<String>, LuxError> {
    let resolved = resolve_shim_providers(cfg, providers);
    if resolved.is_empty() {
        return Err(LuxError::Process(format!(
            "no providers configured for shim {action}"
        )));
    }
    Ok(resolved)
}

fn shim_path_for_provider(bin_dir: &Path, provider: &str) -> PathBuf {
    bin_dir.join(provider)
}

fn shim_script(provider: &str) -> String {
    format!(
        "#!/usr/bin/env bash\n{marker}\nset -euo pipefail\nexec lux shim exec {provider} -- \"$@\"\n",
        marker = SHIM_MARKER
    )
}

fn is_lux_managed_shim(path: &Path) -> bool {
    fs::read_to_string(path)
        .map(|body| body.contains(SHIM_MARKER))
        .unwrap_or(false)
}

fn canonical_or_self(path: &Path) -> PathBuf {
    fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf())
}

fn paths_equivalent(left: &Path, right: &Path) -> bool {
    canonical_or_self(left) == canonical_or_self(right)
}

fn resolve_path_candidates(command: &str) -> Vec<PathBuf> {
    let mut rows = Vec::new();
    let mut seen = std::collections::BTreeSet::new();
    let Some(path_env) = env::var_os("PATH") else {
        return rows;
    };
    for dir in env::split_paths(&path_env) {
        let candidate = dir.join(command);
        if !candidate.exists() {
            continue;
        }
        let candidate = canonical_or_self(&candidate);
        let key = candidate.to_string_lossy().to_string();
        if seen.insert(key) {
            rows.push(candidate);
        }
    }
    rows
}

fn shim_path_safe(policy: &PolicyPaths, shim_path: &Path) -> bool {
    path_is_within(shim_path, &policy.trusted_root)
        && !path_is_within(shim_path, &policy.workspace_root)
        && !path_is_within(&policy.workspace_root, shim_path)
}

fn shim_path_precedence_ok(provider: &str, shim_path: &Path) -> (bool, Vec<PathBuf>) {
    let resolved = resolve_path_candidates(provider);
    let first_matches = resolved
        .first()
        .map(|first| paths_equivalent(first, shim_path))
        .unwrap_or(false);
    (first_matches, resolved)
}

fn display_path_with_tilde(path: &Path, home: &Path) -> String {
    if path == home {
        return "~".to_string();
    }
    if let Ok(stripped) = path.strip_prefix(home) {
        if stripped.as_os_str().is_empty() {
            "~".to_string()
        } else {
            format!("~/{}", stripped.display())
        }
    } else {
        path.to_string_lossy().to_string()
    }
}

fn shim_startup_candidate_files(home: &Path) -> Vec<PathBuf> {
    vec![
        home.join(".zprofile"),
        home.join(".zshrc"),
        home.join(".bash_profile"),
        home.join(".bash_login"),
        home.join(".profile"),
        home.join(".bashrc"),
    ]
}

fn existing_shim_startup_files(home: &Path) -> Vec<PathBuf> {
    shim_startup_candidate_files(home)
        .into_iter()
        .filter(|path| path.exists())
        .collect()
}

fn render_shim_path_block(shims_bin_dir: &Path) -> String {
    let shim_dir = shims_bin_dir
        .to_string_lossy()
        .replace('\\', "\\\\")
        .replace('"', "\\\"");
    format!(
        "{begin}\n_lux_shim_dir=\"{shim_dir}\"\n_lux_has_dir=false\nIFS=:\nfor _lux_path_entry in $PATH; do\n  if [ \"$_lux_path_entry\" = \"$_lux_shim_dir\" ]; then\n    _lux_has_dir=true\n    break\n  fi\ndone\nunset IFS\nif [ \"$_lux_has_dir\" != \"true\" ]; then\n  export PATH=\"$_lux_shim_dir:$PATH\"\nfi\nunset _lux_path_entry _lux_has_dir _lux_shim_dir\n{end}\n",
        begin = SHIM_PATH_BEGIN_MARKER,
        end = SHIM_PATH_END_MARKER,
    )
}

fn managed_path_block_present(body: &str) -> bool {
    let Some(begin) = body.find(SHIM_PATH_BEGIN_MARKER) else {
        return false;
    };
    let after_begin = begin + SHIM_PATH_BEGIN_MARKER.len();
    body[after_begin..].contains(SHIM_PATH_END_MARKER)
}

fn strip_managed_path_blocks(body: &str) -> Result<(String, bool), String> {
    let mut remaining = body;
    let mut output = String::with_capacity(body.len());
    let mut removed_any = false;

    loop {
        let Some(begin_idx) = remaining.find(SHIM_PATH_BEGIN_MARKER) else {
            output.push_str(remaining);
            break;
        };
        output.push_str(&remaining[..begin_idx]);
        let after_begin = begin_idx + SHIM_PATH_BEGIN_MARKER.len();
        let Some(end_rel) = remaining[after_begin..].find(SHIM_PATH_END_MARKER) else {
            return Err(
                "found Lux-managed PATH begin marker without matching end marker".to_string(),
            );
        };
        let mut cut_idx = after_begin + end_rel + SHIM_PATH_END_MARKER.len();
        if remaining[cut_idx..].starts_with("\r\n") {
            cut_idx += 2;
        } else if remaining[cut_idx..].starts_with('\n') {
            cut_idx += 1;
        }
        remaining = &remaining[cut_idx..];
        removed_any = true;
    }
    Ok((output, removed_any))
}

fn apply_managed_path_block(body: &str, block: &str) -> Result<(String, bool, bool), String> {
    let (stripped, _) = strip_managed_path_blocks(body)?;
    let mut updated = stripped.trim_end_matches('\n').to_string();
    if !updated.is_empty() {
        updated.push_str("\n\n");
    }
    updated.push_str(block.trim_end_matches('\n'));
    updated.push('\n');
    let changed = updated != body;
    Ok((updated, true, changed))
}

fn remove_managed_path_block(body: &str) -> Result<(String, bool, bool), String> {
    let (updated, _) = strip_managed_path_blocks(body)?;
    let changed = updated != body;
    Ok((updated, false, changed))
}

fn shim_path_persistence_state(rows: &[ShimPathFileStatus]) -> String {
    if rows.is_empty() {
        return "no_startup_files".to_string();
    }
    let present = rows.iter().filter(|row| row.managed_block_present).count();
    if present == 0 {
        "absent".to_string()
    } else if present == rows.len() {
        "configured".to_string()
    } else {
        "partial".to_string()
    }
}

fn rollback_startup_file_mutations(
    changed_paths: &[PathBuf],
    originals: &BTreeMap<PathBuf, String>,
) -> bool {
    let mut rolled_back = true;
    for path in changed_paths.iter().rev() {
        let Some(original) = originals.get(path) else {
            continue;
        };
        if fs::write(path, original.as_bytes()).is_err() {
            rolled_back = false;
        }
    }
    rolled_back
}

fn build_shim_path_failure(
    startup_files: &[PathBuf],
    originals: &BTreeMap<PathBuf, String>,
    failing_path: &Path,
    error_message: String,
    rolled_back: bool,
) -> ShimPathPhase {
    let mut rows = Vec::new();
    for path in startup_files {
        let present = originals
            .get(path)
            .map(|body| managed_path_block_present(body))
            .unwrap_or(false);
        rows.push(ShimPathFileStatus {
            path: path.clone(),
            existed: true,
            managed_block_present: present,
            changed: false,
            error: if path == failing_path {
                Some(error_message.clone())
            } else {
                None
            },
        });
    }
    ShimPathPhase {
        ok: false,
        state: shim_path_persistence_state(&rows),
        files: rows,
        rolled_back: Some(rolled_back),
    }
}

fn mutate_shell_path_persistence(
    policy: &PolicyPaths,
    action: ShimPathAction,
) -> Result<ShimPathPhase, ShimPathPhase> {
    let startup_files = existing_shim_startup_files(&policy.home);
    if startup_files.is_empty() {
        return Ok(ShimPathPhase {
            ok: true,
            state: "no_startup_files".to_string(),
            files: Vec::new(),
            rolled_back: None,
        });
    }

    let mut originals = BTreeMap::new();
    for path in &startup_files {
        let content = match fs::read_to_string(path) {
            Ok(content) => content,
            Err(err) => {
                return Err(build_shim_path_failure(
                    &startup_files,
                    &originals,
                    path,
                    format!("failed to read startup file {}: {}", path.display(), err),
                    true,
                ));
            }
        };
        originals.insert(path.clone(), content);
    }

    let managed_block = render_shim_path_block(&policy.shims_bin_dir);
    let mut changed_paths: Vec<PathBuf> = Vec::new();
    let mut rows: Vec<ShimPathFileStatus> = Vec::new();

    for path in &startup_files {
        let original = originals.get(path).expect("startup file original content");
        let transformed = match action {
            ShimPathAction::Enable => apply_managed_path_block(original, &managed_block),
            ShimPathAction::Disable => remove_managed_path_block(original),
        };
        let (updated, managed_block_present, changed) = match transformed {
            Ok(row) => row,
            Err(err) => {
                let rolled_back = rollback_startup_file_mutations(&changed_paths, &originals);
                return Err(build_shim_path_failure(
                    &startup_files,
                    &originals,
                    path,
                    format!("failed to update startup file {}: {}", path.display(), err),
                    rolled_back,
                ));
            }
        };

        if changed {
            if let Err(err) = fs::write(path, updated.as_bytes()) {
                let rolled_back = rollback_startup_file_mutations(&changed_paths, &originals);
                return Err(build_shim_path_failure(
                    &startup_files,
                    &originals,
                    path,
                    format!("failed to write startup file {}: {}", path.display(), err),
                    rolled_back,
                ));
            }
            changed_paths.push(path.clone());
        }

        rows.push(ShimPathFileStatus {
            path: path.clone(),
            existed: true,
            managed_block_present,
            changed,
            error: None,
        });
    }

    Ok(ShimPathPhase {
        ok: true,
        state: shim_path_persistence_state(&rows),
        files: rows,
        rolled_back: None,
    })
}

fn inspect_shell_path_persistence(policy: &PolicyPaths) -> Result<ShimPathPhase, LuxError> {
    let startup_files = existing_shim_startup_files(&policy.home);
    if startup_files.is_empty() {
        return Ok(ShimPathPhase {
            ok: true,
            state: "no_startup_files".to_string(),
            files: Vec::new(),
            rolled_back: None,
        });
    }
    let mut rows = Vec::new();
    for path in startup_files {
        let content = fs::read_to_string(&path).map_err(|err| {
            LuxError::Process(format!(
                "failed to read startup file {}: {}",
                path.display(),
                err
            ))
        })?;
        rows.push(ShimPathFileStatus {
            path,
            existed: true,
            managed_block_present: managed_path_block_present(&content),
            changed: false,
            error: None,
        });
    }
    Ok(ShimPathPhase {
        ok: true,
        state: shim_path_persistence_state(&rows),
        files: rows,
        rolled_back: None,
    })
}

fn shim_path_files_json(
    rows: &[ShimPathFileStatus],
    home: &Path,
    include_changed: bool,
    include_error: bool,
) -> Vec<serde_json::Value> {
    let mut json_rows = Vec::new();
    for row in rows {
        let mut item = json!({
            "path": display_path_with_tilde(&row.path, home),
            "existed": row.existed,
            "managed_block_present": row.managed_block_present,
        });
        if include_changed {
            item["changed"] = json!(row.changed);
        }
        if include_error {
            if let Some(error) = &row.error {
                item["error"] = json!(error);
            }
        }
        json_rows.push(item);
    }
    json_rows
}

fn shim_status_summary_state(rows: &[serde_json::Value]) -> String {
    let installed_count = rows
        .iter()
        .filter(|row| row["installed"].as_bool().unwrap_or(false))
        .count();
    if installed_count == 0 {
        return "disabled".to_string();
    }
    let all_ready = rows.iter().all(|row| {
        row["installed"].as_bool().unwrap_or(false)
            && row["path_precedence_ok"].as_bool().unwrap_or(false)
    });
    if all_ready {
        "enabled".to_string()
    } else {
        "degraded".to_string()
    }
}

fn emit_shim_current_session_guidance(
    action: ShimPathAction,
    policy: &PolicyPaths,
    no_startup_files: bool,
) {
    let shim_dir = policy.shims_bin_dir.to_string_lossy();
    eprintln!();
    match action {
        ShimPathAction::Enable => {
            eprintln!("Current session PATH update:");
            eprintln!("  export PATH=\"{}:$PATH\"", shim_dir);
            eprintln!("Reload shell startup files (if changed):");
            eprintln!("  source ~/.zprofile  # zsh login shell");
            eprintln!("  source ~/.bashrc    # bash interactive shell");
        }
        ShimPathAction::Disable => {
            let quoted = shell_single_quote(&shim_dir);
            eprintln!("Current session PATH update:");
            eprintln!(
                "  export PATH=\"$(printf '%s' \"$PATH\" | tr ':' '\\n' | grep -Fxv {} | paste -sd ':' -)\"",
                quoted
            );
            eprintln!("Or start a new shell session.");
        }
    }
    if no_startup_files {
        eprintln!("No supported zsh/bash startup files were found; Lux did not create any files.");
    }
}

#[cfg(unix)]
fn write_shim(path: &Path, provider: &str) -> Result<(), LuxError> {
    use std::os::unix::fs::PermissionsExt;
    ensure_parent(path)?;
    let body = shim_script(provider);
    write_atomic_text_file(path, &body, Some(0o755))?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o755))?;
    Ok(())
}

#[cfg(not(unix))]
fn write_shim(_path: &Path, _provider: &str) -> Result<(), LuxError> {
    Err(LuxError::Config(
        "shim enable is only supported on unix hosts".to_string(),
    ))
}

fn ensure_provider_plane_for_shim<R: DockerRunner>(
    ctx: &Context,
    provider: &str,
    runner: &R,
) -> Result<String, LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let state_root = policy.state_root;
    if let Some(active_provider) = load_active_provider_state(&state_root)? {
        if active_provider.provider != provider {
            return Err(provider_mismatch_error(&active_provider.provider, provider));
        }
        let active_workspace = load_active_run_state(&state_root)?
            .filter(|state| state.run_id == active_provider.run_id)
            .map(|state| resolve_active_run_workspace_root(&cfg, &state))
            .transpose()?;
        let run_env =
            compose_env_for_run(Some(&active_provider.run_id), active_workspace.as_deref());
        if provider_plane_is_running(ctx, runner, &cfg, false, &run_env)? {
            return Ok(active_provider.run_id);
        }
    }
    handle_up(
        ctx,
        Some(provider.to_string()),
        false,
        None,
        Some("missing".to_string()),
        true,
        None,
        runner,
    )?;
    let active_provider = load_active_provider_state(&state_root)?.ok_or_else(|| {
        LuxError::Process("provider did not register active state after startup".to_string())
    })?;
    Ok(active_provider.run_id)
}

fn shim_validate_exec_args(args: &[String]) -> Result<(), LuxError> {
    for arg in args {
        if Path::new(arg).is_absolute() {
            return Err(LuxError::Process(format!(
                "absolute host path arguments are unsupported in shim v1: {}",
                arg
            )));
        }
    }
    Ok(())
}

fn handle_shim<R: DockerRunner>(
    ctx: &Context,
    command: ShimCommand,
    runner: &R,
) -> Result<(), LuxError> {
    match command {
        ShimCommand::Enable { providers } => {
            let cfg = read_config(&ctx.config_path)?;
            let policy = resolve_config_policy_paths(&cfg)?;
            let providers = resolve_shim_providers_or_error(&cfg, providers, "enable")?;

            let mut preflight: Vec<(String, PathBuf, bool, bool)> = Vec::new();
            let mut rollback_data: BTreeMap<PathBuf, (bool, Option<String>)> = BTreeMap::new();
            for provider in &providers {
                let _ = provider_from_config(&cfg, &provider)?;
                let shim_path = shim_path_for_provider(&policy.shims_bin_dir, &provider);
                if !shim_path_safe(&policy, &shim_path) {
                    return Err(LuxError::Process(format!(
                        "shim path violates trust policy (provider={}, path={}, workspace_root={}, trusted_root={})",
                        provider,
                        shim_path.display(),
                        policy.workspace_root.display(),
                        policy.trusted_root.display()
                    )));
                }
                let existed_before = shim_path.exists();
                if existed_before {
                    if !is_lux_managed_shim(&shim_path) {
                        return Err(LuxError::Process(format!(
                            "shim enable would overwrite existing non-lux binary: {}",
                            shim_path.display()
                        )));
                    }
                    let existing_body = fs::read_to_string(&shim_path)?;
                    let desired = shim_script(provider);
                    let needs_write = existing_body != desired;
                    rollback_data.insert(shim_path.clone(), (true, Some(existing_body)));
                    preflight.push((provider.clone(), shim_path, true, needs_write));
                } else {
                    rollback_data.insert(shim_path.clone(), (false, None));
                    preflight.push((provider.clone(), shim_path, false, true));
                }
            }

            fs::create_dir_all(&policy.shims_bin_dir).map_err(|err| {
                LuxError::Config(format!(
                    "failed to create shims.bin_dir at {}: {}",
                    policy.shims_bin_dir.display(),
                    err
                ))
            })?;

            let mut changed_paths = Vec::new();
            for (provider, shim_path, _existed_before, needs_write) in &preflight {
                if !needs_write {
                    continue;
                }
                if let Err(err) = write_shim(shim_path, provider) {
                    for rollback_path in changed_paths.iter().rev() {
                        let Some((existed_before, original_content)) =
                            rollback_data.get(rollback_path)
                        else {
                            continue;
                        };
                        if *existed_before {
                            if let Some(original_content) = original_content {
                                let _ = fs::write(rollback_path, original_content.as_bytes());
                            }
                        } else {
                            let _ = fs::remove_file(rollback_path);
                        }
                    }
                    return Err(err);
                }
                changed_paths.push(shim_path.clone());
            }

            let mut shim_rows = Vec::new();
            let mut warnings: Vec<String> = Vec::new();
            for (provider, shim_path, _existed_before, needs_write) in &preflight {
                let (path_precedence_ok, _candidates) =
                    shim_path_precedence_ok(provider, shim_path);
                if !path_precedence_ok {
                    warnings.push(format!(
                        "PATH precedence mismatch for '{}': expected {} to resolve first",
                        provider,
                        shim_path.display()
                    ));
                }
                shim_rows.push(json!({
                    "provider": provider,
                    "path": shim_path,
                    "changed": needs_write,
                }));
            }

            let path_phase = match mutate_shell_path_persistence(&policy, ShimPathAction::Enable) {
                Ok(phase) => phase,
                Err(path_failure) => {
                    let partial_outcome = json!({
                        "action": ShimPathAction::Enable.action_id(),
                        "providers": providers,
                        "shim": {"ok": true, "rows": shim_rows},
                        "path": {
                            "ok": path_failure.ok,
                            "rolled_back": path_failure.rolled_back.unwrap_or(false),
                            "state": path_failure.state,
                            "files": shim_path_files_json(&path_failure.files, &policy.home, true, true),
                        },
                    });
                    return Err(LuxError::ProcessDetailed {
                        message: format!(
                            "shell startup file mutation failed during `{}`",
                            ShimPathAction::Enable.command_name()
                        ),
                        details: ProcessErrorDetails {
                            error_code: "shim_path_mutation_failed".to_string(),
                            hint: Some(
                                "Fix shell startup file permissions and retry `lux shim enable`."
                                    .to_string(),
                            ),
                            command: Some(ShimPathAction::Enable.command_name().to_string()),
                            raw_stderr: None,
                            partial_outcome: Some(partial_outcome),
                        },
                    });
                }
            };

            if !ctx.json {
                for warning in &warnings {
                    eprintln!("warning: {warning}");
                }
                emit_shim_current_session_guidance(
                    ShimPathAction::Enable,
                    &policy,
                    path_phase.state == "no_startup_files",
                );
            }

            output(
                ctx,
                json!({
                    "action": ShimPathAction::Enable.action_id(),
                    "providers": providers,
                    "shim": {"ok": true, "rows": shim_rows},
                    "path": {
                        "ok": path_phase.ok,
                        "state": path_phase.state,
                        "files": shim_path_files_json(&path_phase.files, &policy.home, true, false),
                    },
                    "warnings": warnings,
                    "errors": Vec::<String>::new(),
                }),
            )
        }
        ShimCommand::Disable { providers } => {
            let cfg = read_config(&ctx.config_path)?;
            let policy = resolve_config_policy_paths(&cfg)?;
            let providers = resolve_shim_providers_or_error(&cfg, providers, "disable")?;
            let mut shim_rows = Vec::new();
            for provider in &providers {
                let _ = provider_from_config(&cfg, &provider)?;
                let shim_path = shim_path_for_provider(&policy.shims_bin_dir, &provider);
                let mut changed = false;
                if shim_path.exists() && is_lux_managed_shim(&shim_path) {
                    fs::remove_file(&shim_path)?;
                    changed = true;
                }
                shim_rows.push(json!({
                    "provider": provider,
                    "path": shim_path,
                    "changed": changed,
                }));
            }

            let path_phase = match mutate_shell_path_persistence(&policy, ShimPathAction::Disable) {
                Ok(phase) => phase,
                Err(path_failure) => {
                    let partial_outcome = json!({
                        "action": ShimPathAction::Disable.action_id(),
                        "providers": providers,
                        "shim": {"ok": true, "rows": shim_rows},
                        "path": {
                            "ok": path_failure.ok,
                            "rolled_back": path_failure.rolled_back.unwrap_or(false),
                            "state": path_failure.state,
                            "files": shim_path_files_json(&path_failure.files, &policy.home, true, true),
                        },
                    });
                    return Err(LuxError::ProcessDetailed {
                        message: format!(
                            "shell startup file mutation failed during `{}`",
                            ShimPathAction::Disable.command_name()
                        ),
                        details: ProcessErrorDetails {
                            error_code: "shim_path_mutation_failed".to_string(),
                            hint: Some(
                                "Fix shell startup file permissions and retry `lux shim disable`."
                                    .to_string(),
                            ),
                            command: Some(ShimPathAction::Disable.command_name().to_string()),
                            raw_stderr: None,
                            partial_outcome: Some(partial_outcome),
                        },
                    });
                }
            };

            if !ctx.json {
                emit_shim_current_session_guidance(
                    ShimPathAction::Disable,
                    &policy,
                    path_phase.state == "no_startup_files",
                );
            }

            output(
                ctx,
                json!({
                    "action": ShimPathAction::Disable.action_id(),
                    "providers": providers,
                    "shim": {"ok": true, "rows": shim_rows},
                    "path": {
                        "ok": path_phase.ok,
                        "state": path_phase.state,
                        "files": shim_path_files_json(&path_phase.files, &policy.home, true, false),
                    },
                    "warnings": Vec::<String>::new(),
                    "errors": Vec::<String>::new(),
                }),
            )
        }
        ShimCommand::Status { providers } => {
            let cfg = read_config(&ctx.config_path)?;
            let policy = resolve_config_policy_paths(&cfg)?;
            let providers = resolve_shim_providers_or_error(&cfg, providers, "status")?;

            let mut shim_rows = Vec::new();
            for provider in &providers {
                let _ = provider_from_config(&cfg, provider)?;
                let shim_path = shim_path_for_provider(&policy.shims_bin_dir, provider);
                let (path_precedence_ok, candidates) =
                    shim_path_precedence_ok(provider, &shim_path);
                shim_rows.push(json!({
                    "provider": provider,
                    "path": shim_path,
                    "installed": shim_path.exists() && is_lux_managed_shim(&shim_path),
                    "path_safe": shim_path_safe(&policy, &shim_path),
                    "path_precedence_ok": path_precedence_ok,
                    "resolved_candidates": candidates.into_iter().map(|path| path.to_string_lossy().to_string()).collect::<Vec<String>>(),
                }));
            }
            let path_status = inspect_shell_path_persistence(&policy)?;
            output(
                ctx,
                json!({
                    "action": "shim_status",
                    "providers": providers,
                    "state": shim_status_summary_state(&shim_rows),
                    "shims": shim_rows,
                    "path_persistence": {
                        "state": path_status.state,
                        "files": shim_path_files_json(&path_status.files, &policy.home, false, false),
                    }
                }),
            )
        }
        ShimCommand::Exec { provider, argv } => {
            let mut passthrough = argv;
            if passthrough
                .first()
                .map(|value| value == "--")
                .unwrap_or(false)
            {
                passthrough.remove(0);
            }
            shim_validate_exec_args(&passthrough)?;
            let cfg = read_config(&ctx.config_path)?;
            let provider_cfg = provider_from_config(&cfg, &provider)?;
            let policy = resolve_config_policy_paths(&cfg)?;
            let shim_path = shim_path_for_provider(&policy.shims_bin_dir, &provider);
            if !shim_path_safe(&policy, &shim_path) {
                return Err(LuxError::Process(format!(
                    "shim path violates trust policy (provider={}, path={}, workspace_root={}, trusted_root={})",
                    provider,
                    shim_path.display(),
                    policy.workspace_root.display(),
                    policy.trusted_root.display()
                )));
            }
            let state_root = policy.state_root;
            ensure_runtime_running(ctx)?;
            let run_id = ensure_provider_plane_for_shim(ctx, &provider, runner)?;
            let mut tui_cmd = provider_cfg.commands.tui.clone();
            for arg in &passthrough {
                tui_cmd.push(' ');
                tui_cmd.push_str(&shell_single_quote(arg));
            }
            let runtime =
                generate_provider_runtime_compose(ctx, &provider, provider_cfg, Some(&tui_cmd))?;
            for warning in &runtime.warnings {
                eprintln!("warning: {warning}");
            }
            let mut args = compose_base_args(ctx, &cfg, false, &[runtime.override_file.clone()])?;
            let cwd = env::current_dir()?;
            let active_workspace = load_active_run_state(&state_root)?
                .filter(|state| state.run_id == run_id)
                .map(|state| resolve_active_run_workspace_root(&cfg, &state))
                .transpose()?
                .unwrap_or_else(|| policy.workspace_root.clone());
            let workspace_canon = fs::canonicalize(&active_workspace).unwrap_or(active_workspace);
            let cwd_canon = fs::canonicalize(&cwd).unwrap_or(cwd);
            if !cwd_canon.starts_with(&workspace_canon) {
                return Err(LuxError::Process(format!(
                    "shim execution must run from within workspace root: {}",
                    workspace_canon.display()
                )));
            }
            let container_workdir = map_host_start_dir_to_container(&cwd_canon, &workspace_canon)?;
            append_harness_tui_run_args(&mut args, &container_workdir);
            run_docker_command(
                ctx,
                runner,
                &args,
                &compose_env_for_run(Some(&run_id), Some(&workspace_canon)),
                json!({"action":"shim_exec", "provider": provider, "run_id": run_id}),
                false,
            )
        }
    }
}

fn handle_up<R: DockerRunner>(
    ctx: &Context,
    provider: Option<String>,
    collector_only: bool,
    workspace: Option<String>,
    pull: Option<String>,
    wait: bool,
    timeout_sec: Option<u64>,
    runner: &R,
) -> Result<(), LuxError> {
    if timeout_sec.is_some() && !wait {
        return Err(LuxError::Config(
            "--timeout-sec requires --wait".to_string(),
        ));
    }
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let state_root = policy.state_root;
    let target = resolve_lifecycle_target(provider, collector_only)?;

    match target {
        LifecycleTarget::CollectorOnly => {
            let effective_workspace = resolve_effective_workspace_root(&cfg, workspace.as_deref())?;
            let preflight_env = compose_env_for_run(None, Some(&effective_workspace));
            if provider_plane_is_running(ctx, runner, &cfg, false, &preflight_env)? {
                return Err(LuxError::Process(
                    "provider plane is still running; stop it before starting a new collector run"
                        .to_string(),
                ));
            }
            if collector_is_running(ctx, runner, &cfg, false, &preflight_env)? {
                return Err(LuxError::Process(
                    "collector is already running".to_string(),
                ));
            }
            let run_id = run_id_from_now();
            fs::create_dir_all(run_root(&log_root, &run_id))?;
            write_active_run_state(&state_root, &run_id, &effective_workspace)?;

            let mut args = compose_base_args(ctx, &cfg, false, &[])?;
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
                let _ = clear_active_run_state(&state_root);
            }
            result
        }
        LifecycleTarget::Provider(provider_name) => {
            let provider_cfg = provider_from_config(&cfg, &provider_name)?;
            if cfg.collector.auto_start {
                let collector_running =
                    collector_is_running(ctx, runner, &cfg, false, &BTreeMap::new())?;
                let active_run_valid = load_active_run_state(&state_root)?
                    .map(|state| run_root(&log_root, &state.run_id).exists())
                    .unwrap_or(false);
                if !collector_running || !active_run_valid {
                    handle_up(
                        ctx,
                        None,
                        true,
                        None,
                        Some("missing".to_string()),
                        true,
                        None,
                        runner,
                    )?;
                }
            }
            let active_run = load_active_run_state(&state_root)?.ok_or_else(|| {
                LuxError::Process(
                    "no active run found; start collector first with `lux up --collector-only`"
                        .to_string(),
                )
            })?;
            let active_workspace = resolve_active_run_workspace_root(&cfg, &active_run)?;
            if let Some(raw_workspace) = workspace.as_deref() {
                let requested_workspace =
                    resolve_effective_workspace_root(&cfg, Some(raw_workspace))?;
                if requested_workspace != active_workspace {
                    return Err(LuxError::Config(format!(
                        "--workspace must match active run workspace (active={}, requested={})",
                        active_workspace.display(),
                        requested_workspace.display()
                    )));
                }
            }
            if !run_root(&log_root, &active_run.run_id).exists() {
                clear_active_run_state(&state_root)?;
                return Err(LuxError::Process(
                    "active run metadata points to a missing run directory; restart collector with `lux up --collector-only`"
                        .to_string(),
                ));
            }
            let run_env = compose_env_for_run(Some(&active_run.run_id), Some(&active_workspace));
            if !collector_is_running(ctx, runner, &cfg, false, &run_env)? {
                return Err(LuxError::Process(
                    "collector is not running; start it first with `lux up --collector-only`"
                        .to_string(),
                ));
            }
            if let Some(active_provider) = load_active_provider_state(&state_root)? {
                if active_provider.provider != provider_name {
                    return Err(provider_mismatch_error(
                        &active_provider.provider,
                        &provider_name,
                    ));
                }
            }
            if provider_plane_is_running(ctx, runner, &cfg, false, &run_env)? {
                return Err(LuxError::Process(format!(
                    "provider plane is already running for '{}'",
                    provider_name
                )));
            }

            let runtime =
                generate_provider_runtime_compose(ctx, &provider_name, provider_cfg, None)?;
            for warning in &runtime.warnings {
                eprintln!("warning: {warning}");
            }

            let mut args = compose_base_args(ctx, &cfg, false, &[runtime.override_file.clone()])?;
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
                    &state_root,
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
    runner: &R,
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let state_root = policy.state_root;
    let target = resolve_lifecycle_target(provider, collector_only)?;
    let active_run = load_active_run_state(&state_root)?;
    let run_id = active_run.as_ref().map(|state| state.run_id.clone());
    let workspace_root = active_run
        .as_ref()
        .map(|state| resolve_active_run_workspace_root(&cfg, state))
        .transpose()?;
    let env_overrides = compose_env_for_run(run_id.as_deref(), workspace_root.as_deref());

    match target {
        LifecycleTarget::CollectorOnly => {
            let mut args = compose_base_args(ctx, &cfg, false, &[])?;
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
            if let Some(active_provider) = load_active_provider_state(&state_root)? {
                if active_provider.provider != provider_name {
                    return Err(provider_mismatch_error(
                        &active_provider.provider,
                        &provider_name,
                    ));
                }
            }
            let mut args = compose_base_args(ctx, &cfg, false, &[])?;
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
                clear_active_provider_state(&state_root)?;
            }
            result
        }
    }
}

fn handle_status<R: DockerRunner>(
    ctx: &Context,
    provider: Option<String>,
    collector_only: bool,
    runner: &R,
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let state_root = policy.state_root;
    let active_run = load_active_run_state(&state_root)?;
    let run_id = active_run.as_ref().map(|state| state.run_id.clone());
    let workspace_root = active_run
        .as_ref()
        .map(|state| resolve_active_run_workspace_root(&cfg, state))
        .transpose()?;
    let env_overrides = compose_env_for_run(run_id.as_deref(), workspace_root.as_deref());
    let target = resolve_lifecycle_target(provider, collector_only)?;

    let mut args = compose_base_args(ctx, &cfg, false, &[])?;
    args.push("ps".to_string());
    args.push("--format".to_string());
    args.push("json".to_string());
    match target {
        LifecycleTarget::CollectorOnly => {
            args.push("collector".to_string());
        }
        LifecycleTarget::Provider(provider_name) => {
            let _provider_cfg = provider_from_config(&cfg, &provider_name)?;
            if let Some(active_provider) = load_active_provider_state(&state_root)? {
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
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let _provider_cfg = provider_from_config(&cfg, &provider)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let state_root = policy.state_root;
    let active_provider = load_active_provider_state(&state_root)?.ok_or_else(|| {
        LuxError::Process(
            "no active provider plane found; start one with `lux up --provider <name>`".to_string(),
        )
    })?;
    if active_provider.provider != provider {
        return Err(provider_mismatch_error(
            &active_provider.provider,
            &provider,
        ));
    }
    let active_run = load_active_run_state(&state_root)?.ok_or_else(|| {
        LuxError::Process(
            "no active run metadata found; restart collector with `lux up --collector-only`"
                .to_string(),
        )
    })?;
    if active_run.run_id != active_provider.run_id {
        return Err(LuxError::Process(format!(
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
        return Err(LuxError::Process(format!(
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
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let provider_cfg = provider_from_config(&cfg, &provider)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let state_root = policy.state_root;
    let active_provider = load_active_provider_state(&state_root)?.ok_or_else(|| {
        LuxError::Process(
            "no active provider plane found; start one with `lux up --provider <name>`".to_string(),
        )
    })?;
    if active_provider.provider != provider {
        return Err(provider_mismatch_error(
            &active_provider.provider,
            &provider,
        ));
    }
    let active_run = load_active_run_state(&state_root)?.ok_or_else(|| {
        LuxError::Process(
            "no active run metadata found; restart collector with `lux up --collector-only`"
                .to_string(),
        )
    })?;
    if active_run.run_id != active_provider.run_id {
        return Err(LuxError::Process(format!(
            "active run mismatch (collector run_id={}, provider run_id={}); restart provider plane",
            active_run.run_id, active_provider.run_id
        )));
    }
    let workspace_root = resolve_active_run_workspace_root(&cfg, &active_run)?;
    let host_start_dir = resolve_host_start_dir(&cfg, &workspace_root, start_dir.as_deref())?;
    let container_start_dir = map_host_start_dir_to_container(&host_start_dir, &workspace_root)?;

    let runtime = generate_provider_runtime_compose(ctx, &provider, provider_cfg, None)?;
    for warning in &runtime.warnings {
        eprintln!("warning: {warning}");
    }
    let mut args = compose_base_args(ctx, &cfg, false, &[runtime.override_file.clone()])?;
    append_harness_tui_run_args(&mut args, &container_start_dir);
    let env_overrides = compose_env_for_run(Some(&active_provider.run_id), Some(&workspace_root));
    if !provider_plane_is_running(ctx, runner, &cfg, false, &env_overrides)? {
        return Err(LuxError::Process(format!(
            "provider plane for '{provider}' is not running; start it with `lux up --provider {provider}`"
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

fn handle_jobs(ctx: &Context, command: JobsCommand) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let state_root = policy.state_root;
    match command {
        JobsCommand::List { run_id, latest } => {
            let run_id =
                resolve_run_id_from_selector(&log_root, &state_root, run_id.as_deref(), latest)?;
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
            let run_id =
                resolve_run_id_from_selector(&log_root, &state_root, run_id.as_deref(), latest)?;
            let jobs_dir = run_root(&log_root, &run_id).join("harness").join("jobs");
            let status_path = jobs_dir.join(&id).join("status.json");
            if !status_path.exists() {
                return Err(LuxError::Process(format!("job not found: {id}")));
            }
            let content = fs::read_to_string(status_path)?;
            let data: serde_json::Value =
                serde_json::from_str(&content).unwrap_or(json!({"raw": content}));
            output(ctx, json!({"run_id": run_id, "job": data}))
        }
    }
}

#[derive(Debug, Clone, Serialize)]
struct DoctorCheck {
    id: String,
    ok: bool,
    severity: String,
    strict_fail: bool,
    message: String,
    remediation: String,
    details: serde_json::Value,
}

fn doctor_check(
    id: &str,
    ok: bool,
    severity: &str,
    strict_fail: bool,
    message: impl Into<String>,
    remediation: impl Into<String>,
    details: serde_json::Value,
) -> DoctorCheck {
    DoctorCheck {
        id: id.to_string(),
        ok,
        severity: severity.to_string(),
        strict_fail,
        message: message.into(),
        remediation: remediation.into(),
        details,
    }
}

fn collect_doctor_checks(ctx: &Context, cfg: &Config) -> Result<Vec<DoctorCheck>, LuxError> {
    let mut checks = Vec::new();

    let docker_installed = which::which("docker").is_ok();
    let docker_ok = if docker_installed {
        Command::new("docker")
            .arg("info")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    } else {
        false
    };
    checks.push(doctor_check(
        "docker_runtime",
        docker_ok,
        "error",
        true,
        if docker_ok {
            "docker daemon reachable"
        } else if docker_installed {
            "docker is installed but daemon is unreachable"
        } else {
            "docker is not installed or not in PATH"
        },
        "Install/start Docker Desktop (or compatible Docker runtime) and rerun `lux doctor`.",
        json!({"docker_installed": docker_installed}),
    ));

    let docker_compose_ok = if docker_installed {
        Command::new("docker")
            .arg("compose")
            .arg("version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
    } else {
        false
    };
    checks.push(doctor_check(
        "docker_compose",
        docker_compose_ok,
        "error",
        true,
        if docker_compose_ok {
            "docker compose is available"
        } else {
            "docker compose is not available"
        },
        "Install/enable Docker Compose and rerun `lux doctor`.",
        json!({"docker_installed": docker_installed}),
    ));

    let compose_files = configured_compose_files(ctx, true, &[]);
    let missing_compose: Vec<String> = compose_files
        .iter()
        .filter(|path| !path.exists())
        .map(|path| path.to_string_lossy().to_string())
        .collect();
    checks.push(doctor_check(
        "compose_contract",
        missing_compose.is_empty(),
        "error",
        true,
        if missing_compose.is_empty() {
            "compose/runtime contract files present"
        } else {
            "one or more compose contract files are missing"
        },
        "Reinstall/update the CLI bundle or fix `--bundle-dir/--compose-file` overrides.",
        json!({"missing_files": missing_compose}),
    ));

    let policy = resolve_config_policy_paths(cfg)?;
    let log_root = policy.log_root.clone();
    let workspace_root = policy.workspace_root.clone();
    let trusted_root = policy.trusted_root.clone();
    let shims_bin_dir = policy.shims_bin_dir.clone();
    let log_writable = host_dir_writable(&log_root);
    checks.push(doctor_check(
        "log_sink_permissions",
        log_writable,
        "error",
        true,
        if log_writable {
            "log root is writable"
        } else {
            "log root is not writable"
        },
        format!(
            "Ensure {} exists and is writable by your user.",
            log_root.display()
        ),
        json!({"log_root": log_root.clone()}),
    ));

    let workspace_ok = fs::create_dir_all(&workspace_root).is_ok();
    let path_coherent = workspace_ok
        && !path_is_within(&workspace_root, &log_root)
        && !path_is_within(&log_root, &workspace_root)
        && path_is_within(&log_root, &trusted_root);
    checks.push(doctor_check(
        "path_config_coherence",
        path_coherent,
        "warn",
        true,
        if path_coherent {
            "workspace/log/trusted path config is coherent"
        } else if !workspace_ok {
            "workspace_root is not writable"
        } else if !path_is_within(&log_root, &trusted_root) {
            "log_root must be inside trusted_root"
        } else {
            "workspace/log path relationship is invalid"
        },
        "Set valid writable `paths.workspace_root`, `paths.trusted_root`, and `paths.log_root` values.",
        json!({
            "workspace_root": workspace_root.clone(),
            "trusted_root": trusted_root.clone(),
            "log_root": log_root.clone()
        }),
    ));

    let shim_bin_policy_ok = shim_path_safe(&policy, &shims_bin_dir);
    checks.push(doctor_check(
        "shim_bin_path_policy",
        shim_bin_policy_ok,
        "error",
        true,
        if shim_bin_policy_ok {
            "shims.bin_dir satisfies trust-zone policy"
        } else {
            "shims.bin_dir violates trust-zone policy"
        },
        "Set `shims.bin_dir` inside `paths.trusted_root` and outside `paths.workspace_root`.",
        json!({
            "trusted_root": trusted_root.clone(),
            "workspace_root": workspace_root.clone(),
            "shims_bin_dir": shims_bin_dir.clone(),
        }),
    ));

    let mut shim_rows = Vec::new();
    let mut shim_precedence_ok = true;
    for provider in cfg.providers.keys() {
        let shim_path = shim_path_for_provider(&policy.shims_bin_dir, provider);
        let installed = shim_path.exists() && is_lux_managed_shim(&shim_path);
        let (path_precedence_ok, candidates) = shim_path_precedence_ok(provider, &shim_path);
        let provider_ok = installed && path_precedence_ok;
        if !provider_ok {
            shim_precedence_ok = false;
        }
        shim_rows.push(json!({
            "provider": provider,
            "path": shim_path,
            "installed": installed,
            "path_precedence_ok": path_precedence_ok,
            "resolved_candidates": candidates.into_iter().map(|path| path.to_string_lossy().to_string()).collect::<Vec<String>>(),
        }));
    }
    checks.push(doctor_check(
        "shim_path_precedence",
        shim_precedence_ok,
        "warn",
        true,
        if shim_precedence_ok {
            "configured provider shims resolve first on PATH"
        } else {
            "one or more configured provider shims are not first on PATH"
        },
        "Run `lux shim enable` and ensure `<trusted_root>/bin` is first in PATH for configured providers.",
        json!({"providers": shim_rows}),
    ));

    let trusted_root_permissions = vec![
        ("trusted_root", policy.trusted_root.clone()),
        ("log_root", policy.log_root.clone()),
        ("runtime_root", policy.runtime_root.clone()),
        ("state_root", policy.state_root.clone()),
        ("secrets_root", policy.secrets_root.clone()),
        ("shims_bin_dir", policy.shims_bin_dir.clone()),
    ];
    let trusted_permission_rows: Vec<serde_json::Value> = trusted_root_permissions
        .iter()
        .map(|(name, path)| {
            json!({
                "path_id": name,
                "path": path,
                "writable": host_dir_writable(path),
            })
        })
        .collect();
    let trusted_root_ok = trusted_permission_rows
        .iter()
        .all(|row| row["writable"].as_bool().unwrap_or(false));
    checks.push(doctor_check(
        "trusted_root_permissions",
        trusted_root_ok,
        "error",
        true,
        if trusted_root_ok {
            "trusted root and subdirectories are writable"
        } else {
            "trusted root or required subdirectories are not writable"
        },
        "Ensure trusted root and key subdirectories are writable by the Lux process user.",
        json!({"paths": trusted_permission_rows}),
    ));

    let (paths, _) = resolve_runtime_paths(ctx)?;
    let runtime_dir_ok = fs::create_dir_all(&paths.runtime_dir).is_ok();
    checks.push(doctor_check(
        "runtime_socket_ready",
        runtime_dir_ok,
        "warn",
        false,
        if runtime_dir_ok {
            "runtime socket directory is writable"
        } else {
            "runtime socket directory is not writable"
        },
        format!(
            "Ensure runtime dir {} is writable for runtime daemon startup.",
            paths.runtime_dir.display()
        ),
        json!({"runtime_dir": paths.runtime_dir}),
    ));

    let token_ok =
        !cfg.harness.api_token.trim().is_empty() || env::var("HARNESS_API_TOKEN").is_ok();
    checks.push(doctor_check(
        "harness_token_sanity",
        token_ok,
        "warn",
        false,
        if token_ok {
            "harness token configured"
        } else {
            "harness token is empty"
        },
        "Set `harness.api_token` in config or `HARNESS_API_TOKEN` env before non-interactive `lux run`.",
        json!({}),
    ));

    let attribution_ok = cfg
        .providers
        .values()
        .all(|provider| !provider.ownership.root_comm.is_empty());
    checks.push(doctor_check(
        "attribution_prerequisites",
        attribution_ok,
        "error",
        true,
        if attribution_ok {
            "provider ownership attribution config present"
        } else {
            "one or more providers have empty ownership.root_comm"
        },
        "Ensure each provider has non-empty `ownership.root_comm` entries.",
        json!({}),
    ));

    checks.push(doctor_check(
        "contract_schema_compatibility",
        cfg.version == 2,
        "error",
        true,
        if cfg.version == 2 {
            "config schema version is compatible"
        } else {
            "config schema version is incompatible"
        },
        "Set `version: 2` in config.yaml and migrate provider blocks as needed.",
        json!({"config_version": cfg.version}),
    ));

    Ok(checks)
}

fn handle_doctor(ctx: &Context, strict: bool) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let checks = collect_doctor_checks(ctx, &cfg)?;
    let has_error = checks
        .iter()
        .any(|check| !check.ok && check.severity == "error");
    let has_strict_warning = checks.iter().any(|check| !check.ok && check.strict_fail);
    let ok = !has_error && (!strict || !has_strict_warning);
    let primary_error = checks
        .iter()
        .find(|check| !check.ok && check.severity == "error")
        .or_else(|| {
            checks
                .iter()
                .find(|check| !check.ok && strict && check.strict_fail)
        })
        .or_else(|| checks.iter().find(|check| !check.ok))
        .map(|check| check.message.clone());

    if ctx.json {
        let payload = JsonResult {
            ok,
            result: Some(json!({ "checks": checks, "strict": strict })),
            error: if ok { None } else { primary_error },
            error_details: None,
        };
        print_json(&payload)?;
        return Ok(());
    }

    for check in &checks {
        let state = if check.ok { "ok" } else { "fail" };
        println!(
            "[{}] {} ({}) - {}",
            state, check.id, check.severity, check.message
        );
        if !check.ok {
            println!("  remediation: {}", check.remediation);
        }
    }
    if ok {
        return Ok(());
    }
    if strict && has_strict_warning {
        return Err(LuxError::Process("doctor strict mode failed".to_string()));
    }
    Err(LuxError::Process(
        checks
            .iter()
            .find(|check| !check.ok && check.severity == "error")
            .or_else(|| checks.iter().find(|check| !check.ok))
            .map(|check| check.message.clone())
            .unwrap_or_else(|| "one or more readiness checks failed".to_string()),
    ))
}

fn handle_paths(ctx: &Context) -> Result<(), LuxError> {
    let (paths, config_exists) = resolve_runtime_paths(ctx)?;
    let env_exists = paths.env_file.exists();
    let compose_files: Vec<String> = configured_compose_files(ctx, false, &[])
        .into_iter()
        .map(|p| p.to_string_lossy().to_string())
        .collect();
    let compose_contract_files: Vec<String> = configured_compose_files(ctx, true, &[])
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
            "trusted_root": paths.trusted_root,
            "runtime_dir": paths.runtime_dir,
            "runtime_socket_path": paths.runtime_socket_path,
            "runtime_pid_path": paths.runtime_pid_path,
            "runtime_events_path": paths.runtime_events_path,
            "state_dir": paths.state_dir,
            "state_active_run_path": paths.state_active_run_path,
            "state_active_provider_path": paths.state_active_provider_path,
            "secrets_dir": paths.secrets_dir,
            "shim_bin_dir": paths.shim_bin_dir,
            "compose_files": compose_files,
            "compose_contract_files": compose_contract_files,
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

fn handle_update(ctx: &Context, command: UpdateCommand) -> Result<(), LuxError> {
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

fn update_check(ctx: &Context) -> Result<(), LuxError> {
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
) -> Result<(), LuxError> {
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
        return Err(LuxError::Config(
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

    let update_result = (|| -> Result<(), LuxError> {
        download_file(&plan.bundle_url, &bundle_path)?;
        download_file(&plan.checksum_url, &checksum_path)?;
        verify_bundle_checksum(&bundle_path, &checksum_path)?;
        if plan.target_dir.exists() {
            fs::remove_dir_all(&plan.target_dir)?;
        }
        extract_bundle(&bundle_path, &plan.target_dir)?;
        let lux_binary = plan.target_dir.join("lux");
        if !lux_binary.exists() {
            return Err(LuxError::Process(format!(
                "bundle did not contain expected binary: {}",
                lux_binary.display()
            )));
        }
        fs::create_dir_all(&paths.install_dir)?;
        fs::create_dir_all(&paths.bin_dir)?;
        force_symlink(&plan.target_dir, &paths.current_link)?;
        force_symlink(&paths.current_link.join("lux"), &paths.bin_path)?;
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
) -> Result<(), LuxError> {
    let (paths, _) = resolve_runtime_paths(ctx)?;
    let current_version = read_current_version(&paths);
    let installed_tags = list_installed_version_tags(&paths)?;
    if installed_tags.is_empty() {
        return Err(LuxError::Process(
            "no installed versions found under install directory".to_string(),
        ));
    }
    let target_version = match to {
        Some(value) => normalize_version_tag(&value),
        None => {
            let _ = previous;
            let Some(current) = current_version.as_deref() else {
                return Err(LuxError::Process(
                    "cannot infer rollback target: current version is not set".to_string(),
                ));
            };
            let Some(prev) = select_previous_version(current, &installed_tags) else {
                return Err(LuxError::Process(
                    "no previous installed version available for rollback".to_string(),
                ));
            };
            prev
        }
    };
    let target_tag = target_version.trim_start_matches('v');
    let target_dir = paths.versions_dir.join(target_tag);
    if !target_dir.exists() {
        return Err(LuxError::Process(format!(
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
        return Err(LuxError::Config(
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
    force_symlink(&paths.current_link.join("lux"), &paths.bin_path)?;
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

fn remove_path(path: &Path) -> Result<bool, LuxError> {
    let meta = match fs::symlink_metadata(path) {
        Ok(meta) => meta,
        Err(err) if err.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(err) => return Err(LuxError::Io(err)),
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
) -> Result<(), LuxError> {
    if !dry_run && !yes {
        return Err(LuxError::Config(
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
    let bin_path = bin_dir.join("lux");

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

fn handle_logs(ctx: &Context, command: LogsCommand) -> Result<(), LuxError> {
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

fn logs_stats(ctx: &Context, run_id: Option<String>, latest: bool) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let run_id =
        resolve_run_id_from_selector(&log_root, &policy.state_root, run_id.as_deref(), latest)?;
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
) -> Result<(), LuxError> {
    let cfg = read_config(&ctx.config_path)?;
    let policy = resolve_config_policy_paths(&cfg)?;
    let log_root = policy.log_root;
    let run_id =
        resolve_run_id_from_selector(&log_root, &policy.state_root, run_id.as_deref(), latest)?;
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
        return Err(LuxError::Process(format!(
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

fn dir_size(path: PathBuf) -> Result<u64, LuxError> {
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

fn resolve_token(cfg: &Config) -> Result<String, LuxError> {
    if !cfg.harness.api_token.trim().is_empty() {
        return Ok(cfg.harness.api_token.clone());
    }
    if let Ok(token) = env::var("HARNESS_API_TOKEN") {
        if !token.trim().is_empty() {
            return Ok(token);
        }
    }
    Err(LuxError::Config(
        "HARNESS_API_TOKEN is required for server runs; set it in config.yaml or env".to_string(),
    ))
}

fn extract_process_error_details(err: &LuxError) -> Option<ProcessErrorDetails> {
    match err {
        LuxError::ProcessDetailed { details, .. } => Some(details.clone()),
        _ => None,
    }
}

fn output(ctx: &Context, payload: serde_json::Value) -> Result<(), LuxError> {
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

fn print_json<T: Serialize>(payload: &T) -> Result<(), LuxError> {
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
        let trusted_root = base.join("trusted");
        cfg.paths.trusted_root = trusted_root.to_string_lossy().to_string();
        cfg.paths.log_root = trusted_root.join("logs").to_string_lossy().to_string();
        cfg.shims.bin_dir = trusted_root.join("bin").to_string_lossy().to_string();
        cfg.paths.workspace_root = home
            .join("lux-test-workspace")
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
  log_root: ~/lux-logs
  workspace_root: ~/lux-workspace
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
        assert!(cfg.collector.auto_start);
        assert_eq!(cfg.collector.idle_timeout_min, 10_080);
        assert_eq!(cfg.collector.rotate_every_min, 1_440);
        assert_eq!(cfg.runtime_control_plane.socket_path, "");
    }

    #[cfg(unix)]
    #[test]
    fn runtime_socket_path_falls_back_when_default_is_too_long() {
        let mut cfg: Config = serde_yaml::from_str("version: 2").expect("config");
        let deep_trusted_root = PathBuf::from(format!("/tmp/{}", "a".repeat(180)));
        cfg.paths.trusted_root = deep_trusted_root.to_string_lossy().to_string();
        let preferred = deep_trusted_root.join("runtime").join("control_plane.sock");
        assert!(unix_socket_path_too_long(&preferred));
        let effective = effective_runtime_socket_path(&cfg);
        assert!(!unix_socket_path_too_long(&effective));
        assert_ne!(effective, preferred);
    }

    #[cfg(unix)]
    #[test]
    fn config_validate_rejects_overlong_runtime_socket_path() {
        let mut cfg = Config::default();
        cfg.runtime_control_plane.socket_path = format!("/tmp/{}", "b".repeat(180));
        let yaml = serde_yaml::to_string(&cfg).expect("serialize config");
        let err = read_config_from_str(&yaml).expect_err("long socket path should fail");
        assert!(err
            .to_string()
            .contains("runtime_control_plane.socket_path is too long"));
    }

    #[test]
    fn expand_tilde_works() {
        let expanded = expand_path("~/lux-logs");
        assert!(!expanded.starts_with("~/"));
    }

    #[test]
    fn display_path_with_home_rewrites_home_prefix() {
        let home = PathBuf::from("/tmp/lux-home");
        assert_eq!(display_path_with_home(&home, Some(&home)), "$HOME");
        assert_eq!(
            display_path_with_home(&home.join("workspace"), Some(&home)),
            "$HOME/workspace"
        );
        assert_eq!(
            display_path_with_home(Path::new("/var/lib/lux/logs"), Some(&home)),
            "/var/lib/lux/logs"
        );
        assert_eq!(
            display_path_with_home(&home.join("workspace"), None),
            "/tmp/lux-home/workspace"
        );
    }

    #[test]
    fn env_file_written() {
        let dir = tempdir().unwrap();
        let env_path = dir.path().join("compose.env");
        let cfg: Config = serde_yaml::from_str("version: 2").unwrap();
        let envs = config_to_env(&cfg);
        write_env_file(&env_path, &envs).unwrap();
        let content = fs::read_to_string(&env_path).unwrap();
        assert!(content.contains("LUX_VERSION="));
        assert!(content.contains("LUX_LOG_ROOT="));
        assert!(content.contains("LUX_RUNTIME_DIR="));
        assert!(content.contains("LUX_RUNTIME_GID="));
    }

    #[test]
    fn yaml_patch_preserves_comments_and_spacing() {
        let input = r#"# top comment
version: 2

paths:   # paths comment
  log_root : ~/lux-logs   # inline
  workspace_root: "~/lux-workspace"   # keep quotes

providers:
  codex:
    auth_mode: api_key  # keep
    mount_host_state_in_api_mode: false
    commands:
      tui: "codex"
      run_template: "codex exec {prompt}"
    auth:
      api_key:
        secrets_file: ~/.config/lux/secrets/codex.env
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
        assert!(patched.contains("  workspace_root: \"~/lux-workspace\"   # keep quotes"));

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

        handle_up(&ctx, None, true, None, None, true, Some(45), &runner).unwrap();

        let calls = runner.calls();
        assert_eq!(calls.len(), 3);

        let ps_args = &calls[0].args;
        assert!(ps_args.iter().any(|x| x == "ps"));
        assert!(calls[0].env_overrides.contains_key("LUX_WORKSPACE_ROOT"));
        assert!(!calls[0].env_overrides.contains_key("LUX_RUN_ID"));

        let args = &calls[2].args;
        assert!(calls[2].capture_output);
        assert!(args.iter().any(|x| x == "up"));
        assert!(args.iter().any(|x| x == "--wait"));
        let idx = args.iter().position(|x| x == "--wait-timeout").unwrap();
        assert_eq!(args[idx + 1], "45");
        assert!(calls[2].env_overrides.contains_key("LUX_RUN_ID"));
        assert!(calls[2].env_overrides.contains_key("LUX_WORKSPACE_ROOT"));
    }

    #[test]
    fn up_timeout_requires_wait() {
        let dir = tempdir().unwrap();
        write_minimal_config(&dir.path().join("config.yaml"));
        write_default_compose_files(dir.path());
        let ctx = make_context(dir.path());
        let runner = MockDockerRunner::default();

        let err = handle_up(&ctx, None, true, None, None, false, Some(10), &runner)
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

        let err = handle_up(&ctx, None, true, None, None, false, None, &runner)
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

        handle_down(&ctx, None, true, &runner).unwrap();

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

        handle_status(&ctx, None, true, &runner).unwrap();

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
        let content = format!("{hash}  lux_0.1.0_linux_amd64.tar.gz");
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
    fn append_harness_tui_run_args_places_env_before_service_name() {
        let mut args = Vec::new();
        append_harness_tui_run_args(&mut args, "/work/project");
        assert_eq!(
            args,
            vec![
                "run".to_string(),
                "--rm".to_string(),
                "-e".to_string(),
                "HARNESS_MODE=tui".to_string(),
                "-e".to_string(),
                "HARNESS_AGENT_WORKDIR=/work/project".to_string(),
                "harness".to_string(),
            ]
        );
    }

    #[cfg(unix)]
    #[test]
    fn bundle_dir_from_symlinked_exe_prefers_real_binary_parent() {
        let dir = tempdir().unwrap();
        let bundle_dir = dir.path().join("bundle");
        fs::create_dir_all(&bundle_dir).unwrap();
        fs::write(bundle_dir.join("compose.yml"), "services: {}\n").unwrap();

        let real_exe = bundle_dir.join("lux");
        fs::write(&real_exe, "").unwrap();

        let bin_dir = dir.path().join("bin");
        fs::create_dir_all(&bin_dir).unwrap();
        let symlink_exe = bin_dir.join("lux");
        std::os::unix::fs::symlink(&real_exe, &symlink_exe).unwrap();

        let resolved = bundle_dir_from_exe_path(&symlink_exe).expect("bundle dir should resolve");
        assert_eq!(resolved, bundle_dir);
    }

    #[test]
    fn resolve_effective_workspace_root_enforces_home_policy_for_override() {
        let dir = tempdir().unwrap();
        let home = required_home_dir().unwrap();
        let mut cfg = Config::default();
        let trusted_root = dir.path().join("trusted");
        cfg.paths.trusted_root = trusted_root.to_string_lossy().to_string();
        cfg.paths.log_root = trusted_root.join("logs").to_string_lossy().to_string();
        cfg.shims.bin_dir = trusted_root.join("bin").to_string_lossy().to_string();
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
        let trusted_root = dir.path().join("trusted");
        cfg.paths.trusted_root = trusted_root.to_string_lossy().to_string();
        cfg.paths.log_root = trusted_root.join("logs").to_string_lossy().to_string();
        cfg.shims.bin_dir = trusted_root.join("bin").to_string_lossy().to_string();
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
            LuxError::ProcessDetailed { message, details } => {
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
            LuxError::ProcessDetailed { message, details } => {
                assert!(message.contains("failed to run command `docker compose ps`"));
                assert_eq!(details.error_code, "docker_not_found");
                assert!(details.hint.unwrap_or_default().contains("Install Docker"));
                assert_eq!(details.command.unwrap_or_default(), "docker compose ps");
            }
            other => panic!("unexpected error variant: {other:?}"),
        }
    }

    #[test]
    fn shim_path_block_insert_replace_remove_is_idempotent() {
        let initial = "# shell profile\n";
        let block = render_shim_path_block(Path::new("/tmp/lux/bin"));

        let (enabled, enabled_present, enabled_changed) =
            apply_managed_path_block(initial, &block).expect("enable should work");
        assert!(enabled_present);
        assert!(enabled_changed);
        assert_eq!(enabled.matches(SHIM_PATH_BEGIN_MARKER).count(), 1);

        let (enabled_again, enabled_again_present, enabled_again_changed) =
            apply_managed_path_block(&enabled, &block).expect("enable re-run should work");
        assert!(enabled_again_present);
        assert!(!enabled_again_changed);
        assert_eq!(enabled_again.matches(SHIM_PATH_BEGIN_MARKER).count(), 1);

        let (disabled, disabled_present, disabled_changed) =
            remove_managed_path_block(&enabled_again).expect("disable should work");
        assert!(!disabled_present);
        assert!(disabled_changed);
        assert!(!disabled.contains(SHIM_PATH_BEGIN_MARKER));

        let (disabled_again, disabled_again_present, disabled_again_changed) =
            remove_managed_path_block(&disabled).expect("disable re-run should work");
        assert!(!disabled_again_present);
        assert!(!disabled_again_changed);
        assert_eq!(disabled, disabled_again);
    }

    #[test]
    fn shim_path_persistence_state_computation() {
        assert_eq!(shim_path_persistence_state(&[]), "no_startup_files");

        let absent = vec![
            ShimPathFileStatus {
                path: PathBuf::from("/tmp/.zprofile"),
                existed: true,
                managed_block_present: false,
                changed: false,
                error: None,
            },
            ShimPathFileStatus {
                path: PathBuf::from("/tmp/.bashrc"),
                existed: true,
                managed_block_present: false,
                changed: false,
                error: None,
            },
        ];
        assert_eq!(shim_path_persistence_state(&absent), "absent");

        let partial = vec![
            ShimPathFileStatus {
                path: PathBuf::from("/tmp/.zprofile"),
                existed: true,
                managed_block_present: true,
                changed: false,
                error: None,
            },
            ShimPathFileStatus {
                path: PathBuf::from("/tmp/.bashrc"),
                existed: true,
                managed_block_present: false,
                changed: false,
                error: None,
            },
        ];
        assert_eq!(shim_path_persistence_state(&partial), "partial");

        let configured = vec![
            ShimPathFileStatus {
                path: PathBuf::from("/tmp/.zprofile"),
                existed: true,
                managed_block_present: true,
                changed: false,
                error: None,
            },
            ShimPathFileStatus {
                path: PathBuf::from("/tmp/.bashrc"),
                existed: true,
                managed_block_present: true,
                changed: false,
                error: None,
            },
        ];
        assert_eq!(shim_path_persistence_state(&configured), "configured");
    }

    #[test]
    fn shim_status_summary_state_computation() {
        let disabled_rows = vec![
            json!({"provider":"codex","installed":false,"path_precedence_ok":false}),
            json!({"provider":"claude","installed":false,"path_precedence_ok":false}),
        ];
        assert_eq!(shim_status_summary_state(&disabled_rows), "disabled");

        let enabled_rows = vec![
            json!({"provider":"codex","installed":true,"path_precedence_ok":true}),
            json!({"provider":"claude","installed":true,"path_precedence_ok":true}),
        ];
        assert_eq!(shim_status_summary_state(&enabled_rows), "enabled");

        let degraded_rows = vec![
            json!({"provider":"codex","installed":true,"path_precedence_ok":false}),
            json!({"provider":"claude","installed":true,"path_precedence_ok":true}),
        ];
        assert_eq!(shim_status_summary_state(&degraded_rows), "degraded");
    }
}
