use clap::{Parser, Subcommand};
use chrono::{DateTime, Utc};
use dirs::home_dir;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use thiserror::Error;

const DEFAULT_CONFIG_YAML: &str = include_str!("../config/default.yaml");

#[derive(Parser, Debug)]
#[command(name = "lasso", version, about = "Lasso CLI")]
struct Cli {
    #[arg(long, global = true)]
    config: Option<PathBuf>,
    #[arg(long, global = true)]
    json: bool,
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
    Up {
        #[arg(long)]
        codex: bool,
        #[arg(long)]
        ui: bool,
        #[arg(long, value_parser = ["always", "never", "missing"]) ]
        pull: Option<String>,
    },
    Down {
        #[arg(long)]
        codex: bool,
        #[arg(long)]
        ui: bool,
    },
    Status {
        #[arg(long)]
        codex: bool,
        #[arg(long)]
        ui: bool,
    },
    Run {
        prompt: String,
        #[arg(long)]
        capture_input: Option<bool>,
        #[arg(long)]
        cwd: Option<String>,
        #[arg(long)]
        timeout_sec: Option<u64>,
        #[arg(long)]
        env: Vec<String>,
    },
    Tui {
        #[arg(long)]
        codex: bool,
    },
    Jobs {
        #[command(subcommand)]
        command: JobsCommand,
    },
    Doctor,
    Logs {
        #[command(subcommand)]
        command: LogsCommand,
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
    List,
    Get { id: String },
}

#[derive(Subcommand, Debug)]
enum LogsCommand {
    Stats,
    Tail {
        #[arg(long, default_value_t = 50)]
        lines: usize,
        #[arg(long)]
        file: Option<String>,
    },
}

#[derive(Debug, Error)]
enum LassoError {
    #[error("config error: {0}")]
    Config(String),
    #[error("io error: {0}")]
    Io(#[from] io::Error),
    #[error("yaml error: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("process error: {0}")]
    Process(String),
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

impl Default for Config {
    fn default() -> Self {
        Self {
            version: 1,
            paths: Paths::default(),
            release: Release::default(),
            docker: Docker::default(),
            harness: Harness::default(),
        }
    }
}

impl Default for Paths {
    fn default() -> Self {
        Self {
            log_root: "~/lasso-logs".to_string(),
            workspace_root: "~/lasso-workspace".to_string(),
        }
    }
}

impl Default for Release {
    fn default() -> Self {
        Self { tag: "".to_string() }
    }
}

impl Default for Docker {
    fn default() -> Self {
        Self { project_name: "lasso".to_string() }
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

#[derive(Debug, Serialize)]
struct JsonResult<T: Serialize> {
    ok: bool,
    result: Option<T>,
    error: Option<String>,
}

#[derive(Debug)]
struct Context {
    config_path: PathBuf,
    env_file: PathBuf,
    bundle_dir: PathBuf,
    json: bool,
}

fn main() -> Result<(), LassoError> {
    let cli = Cli::parse();
    let ctx = build_context(&cli)?;

    let result = match cli.command {
        Commands::Config { command } => handle_config(&ctx, command),
        Commands::Up { codex, ui, pull } => handle_up(&ctx, codex, ui, pull),
        Commands::Down { codex, ui } => handle_down(&ctx, codex, ui),
        Commands::Status { codex, ui } => handle_status(&ctx, codex, ui),
        Commands::Run { prompt, capture_input, cwd, timeout_sec, env } => {
            handle_run(&ctx, prompt, capture_input, cwd, timeout_sec, env)
        }
        Commands::Tui { codex } => handle_tui(&ctx, codex),
        Commands::Jobs { command } => handle_jobs(&ctx, command),
        Commands::Doctor => handle_doctor(&ctx),
        Commands::Logs { command } => handle_logs(&ctx, command),
    };

    if let Err(err) = result {
        if ctx.json {
            let payload = JsonResult::<serde_json::Value> {
                ok: false,
                result: None,
                error: Some(err.to_string()),
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
    Ok(Context {
        config_path,
        env_file,
        bundle_dir,
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

fn read_config(path: &Path) -> Result<Config, LassoError> {
    let content = fs::read_to_string(path)?;
    let cfg: Config = serde_yaml::from_str(&content)?;
    if cfg.version != 1 {
        return Err(LassoError::Config(format!(
            "unsupported config version {}",
            cfg.version
        )));
    }
    Ok(cfg)
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
    envs.insert("LASSO_LOG_ROOT".to_string(), expand_path(&cfg.paths.log_root));
    envs.insert(
        "LASSO_WORKSPACE_ROOT".to_string(),
        expand_path(&cfg.paths.workspace_root),
    );
    if !cfg.harness.api_token.trim().is_empty() {
        envs.insert("HARNESS_API_TOKEN".to_string(), cfg.harness.api_token.clone());
    }
    envs.insert(
        "HARNESS_HTTP_PORT".to_string(),
        cfg.harness.api_port.to_string(),
    );
    envs
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

fn handle_config(ctx: &Context, command: ConfigCommand) -> Result<(), LassoError> {
    match command {
        ConfigCommand::Init => {
            if ctx.config_path.exists() {
                return output(ctx, json!({"path": ctx.config_path, "created": false}));
            }
            ensure_parent(&ctx.config_path)?;
            fs::write(&ctx.config_path, DEFAULT_CONFIG_YAML)?;
            output(ctx, json!({"path": ctx.config_path, "created": true}))
        }
        ConfigCommand::Edit => {
            if !ctx.config_path.exists() {
                ensure_parent(&ctx.config_path)?;
                fs::write(&ctx.config_path, DEFAULT_CONFIG_YAML)?;
            }
            let editor = env::var("VISUAL").ok().or_else(|| env::var("EDITOR").ok());
            if let Some(editor) = editor {
                let status = Command::new(editor)
                    .arg(&ctx.config_path)
                    .status()
                    .map_err(|err| LassoError::Process(format!("failed to launch editor: {err}")))?;
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
            let envs = config_to_env(&cfg);
            write_env_file(&ctx.env_file, &envs)?;
            let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
            fs::create_dir_all(&log_root)?;
            let workspace_root = PathBuf::from(expand_path(&cfg.paths.workspace_root));
            fs::create_dir_all(&workspace_root)?;
            output(
                ctx,
                json!({"env_file": ctx.env_file, "log_root": log_root, "workspace_root": workspace_root}),
            )
        }
    }
}

fn compose_files(ctx: &Context, codex: bool, ui: bool) -> Result<Vec<PathBuf>, LassoError> {
    let mut files = vec![ctx.bundle_dir.join("compose.yml")];
    if codex {
        files.push(ctx.bundle_dir.join("compose.codex.yml"));
    }
    if ui {
        files.push(ctx.bundle_dir.join("compose.ui.yml"));
    }
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

fn compose_base_command(ctx: &Context, codex: bool, ui: bool) -> Result<Command, LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let files = compose_files(ctx, codex, ui)?;
    if !ctx.env_file.exists() {
        let envs = config_to_env(&cfg);
        write_env_file(&ctx.env_file, &envs)?;
    }
    let mut cmd = Command::new("docker");
    cmd.arg("compose");
    cmd.arg("--env-file").arg(&ctx.env_file);
    if !cfg.docker.project_name.trim().is_empty() {
        cmd.arg("-p").arg(&cfg.docker.project_name);
    }
    for file in files {
        cmd.arg("-f").arg(file);
    }
    cmd.current_dir(&ctx.bundle_dir);
    Ok(cmd)
}

fn handle_up(ctx: &Context, codex: bool, ui: bool, pull: Option<String>) -> Result<(), LassoError> {
    let mut cmd = compose_base_command(ctx, codex, ui)?;
    cmd.arg("up").arg("-d");
    if let Some(pull) = pull {
        cmd.arg("--pull").arg(pull);
    }
    run_command(ctx, cmd, json!({"action": "up"}), true)
}

fn handle_down(ctx: &Context, codex: bool, ui: bool) -> Result<(), LassoError> {
    let mut cmd = compose_base_command(ctx, codex, ui)?;
    cmd.arg("down");
    run_command(ctx, cmd, json!({"action": "down"}), true)
}

fn handle_status(ctx: &Context, codex: bool, ui: bool) -> Result<(), LassoError> {
    let mut cmd = compose_base_command(ctx, codex, ui)?;
    cmd.arg("ps").arg("--format").arg("json");
    let output = cmd.output().map_err(|err| {
        LassoError::Process(format!("failed to run docker compose: {err}"))
    })?;
    if !output.status.success() {
        return Err(LassoError::Process(String::from_utf8_lossy(&output.stderr).to_string()));
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let rows: serde_json::Value = match serde_json::from_str(&text) {
        Ok(value) => value,
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
    };
    if ctx.json {
        let payload = JsonResult {
            ok: true,
            result: Some(rows),
            error: None,
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
    prompt: String,
    capture_input: Option<bool>,
    cwd: Option<String>,
    timeout_sec: Option<u64>,
    env_list: Vec<String>,
) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
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
        "cwd": cwd,
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
        let payload: serde_json::Value = serde_json::from_str(&body).unwrap_or(json!({"raw": body}));
        let wrapper = JsonResult {
            ok: true,
            result: Some(payload),
            error: None,
        };
        print_json(&wrapper)?;
    } else {
        println!("{}", body.trim());
    }
    Ok(())
}

fn handle_tui(ctx: &Context, codex: bool) -> Result<(), LassoError> {
    let mut cmd = compose_base_command(ctx, codex, false)?;
    cmd.arg("run")
        .arg("--rm")
        .arg("-e")
        .arg("HARNESS_MODE=tui")
        .arg("harness");
    run_command(ctx, cmd, json!({"action": "tui"}), false)
}

fn handle_jobs(ctx: &Context, command: JobsCommand) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let jobs_dir = log_root.join("jobs");
    match command {
        JobsCommand::List => {
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
            output(ctx, json!({"jobs": jobs}))
        }
        JobsCommand::Get { id } => {
            let status_path = jobs_dir.join(&id).join("status.json");
            if !status_path.exists() {
                return Err(LassoError::Process(format!("job not found: {id}")));
            }
            let content = fs::read_to_string(status_path)?;
            let data: serde_json::Value = serde_json::from_str(&content).unwrap_or(json!({"raw": content}));
            output(ctx, data)
        }
    }
}

fn handle_doctor(ctx: &Context) -> Result<(), LassoError> {
    let mut checks = BTreeMap::new();
    let docker_ok = match which::which("docker") {
        Ok(_) => {
            let output = Command::new("docker")
                .arg("info")
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            output.map(|s| s.success()).unwrap_or(false)
        }
        Err(_) => false,
    };
    checks.insert("docker".to_string(), docker_ok);

    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let log_ok = fs::create_dir_all(&log_root)
        .and_then(|_| {
            let test_path = log_root.join(".lasso_write_test");
            fs::write(&test_path, b"ok")?;
            fs::remove_file(&test_path)?;
            Ok(())
        })
        .is_ok();
    checks.insert("log_root_writable".to_string(), log_ok);

    let ok = docker_ok && log_ok;
    let error = if ok {
        None
    } else if !docker_ok {
        Some("docker is not available".to_string())
    } else {
        Some("log root is not writable".to_string())
    };

    if ctx.json {
        let payload = JsonResult {
            ok,
            result: Some(json!({ "checks": checks })),
            error,
        };
        print_json(&payload)?;
        return Ok(());
    }

    println!("Docker: {}", if docker_ok { "ok" } else { "missing or not running" });
    println!("Log root: {}", if log_ok { "writable" } else { "not writable" });
    if !docker_ok {
        return Err(LassoError::Process("docker is not available".to_string()));
    }
    if !log_ok {
        return Err(LassoError::Process("log root is not writable".to_string()));
    }
    Ok(())
}

fn handle_logs(ctx: &Context, command: LogsCommand) -> Result<(), LassoError> {
    match command {
        LogsCommand::Stats => logs_stats(ctx),
        LogsCommand::Tail { lines, file } => logs_tail(ctx, lines, file),
    }
}

fn logs_stats(ctx: &Context) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let sessions_dir = log_root.join("sessions");
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
            let (Some(started), Some(ended)) = (started, ended) else { continue; };
            let start_dt = DateTime::parse_from_rfc3339(started).ok();
            let end_dt = DateTime::parse_from_rfc3339(ended).ok();
            let (Some(start_dt), Some(end_dt)) = (start_dt, end_dt) else { continue; };
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
        "sessions": session_count,
        "total_bytes": total_bytes,
        "avg_mb_per_hour": avg_mb_per_hour,
    });
    output(ctx, payload)
}

fn logs_tail(ctx: &Context, lines: usize, file: Option<String>) -> Result<(), LassoError> {
    let cfg = read_config(&ctx.config_path)?;
    let log_root = PathBuf::from(expand_path(&cfg.paths.log_root));
    let target = match file.as_deref() {
        Some("audit") => log_root.join("audit.log"),
        Some("ebpf") => log_root.join("ebpf.jsonl"),
        Some("timeline") | None => log_root.join("filtered_timeline.jsonl"),
        Some(name) => log_root.join(name),
    };
    if !target.exists() {
        return Err(LassoError::Process(format!("log not found: {}", target.display())));
    }
    if ctx.json {
        let payload = JsonResult {
            ok: true,
            result: Some(json!({"path": target})),
            error: None,
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

fn run_command(
    ctx: &Context,
    mut cmd: Command,
    json_payload: serde_json::Value,
    capture_output: bool,
) -> Result<(), LassoError> {
    if capture_output {
        let cmd_output = cmd.output().map_err(|err| {
            LassoError::Process(format!("failed to run command: {err}"))
        })?;
        if !cmd_output.status.success() {
            let stderr = String::from_utf8_lossy(&cmd_output.stderr).trim().to_string();
            let mut message = format!("command failed with status {}", cmd_output.status);
            if !stderr.is_empty() {
                message = format!("{message}: {stderr}");
                let lower = stderr.to_lowercase();
                if lower.contains("denied")
                    || lower.contains("unauthorized")
                    || lower.contains("authentication")
                {
                    message = format!(
                        "{message}\nHint: authenticate with `docker login ghcr.io` for private images."
                    );
                }
            }
            return Err(LassoError::Process(message));
        }
        if !cmd_output.stdout.is_empty() && !ctx.json {
            let stdout = String::from_utf8_lossy(&cmd_output.stdout);
            print!("{stdout}");
        }
        return output(ctx, json_payload);
    }

    let status = cmd.status().map_err(|err| {
        LassoError::Process(format!("failed to run command: {err}"))
    })?;
    if !status.success() {
        return Err(LassoError::Process(format!("command failed with status {status}")));
    }
    output(ctx, json_payload)
}

fn output(ctx: &Context, payload: serde_json::Value) -> Result<(), LassoError> {
    if ctx.json {
        let wrapper = JsonResult {
            ok: true,
            result: Some(payload),
            error: None,
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
    use tempfile::tempdir;

    #[test]
    fn config_unknown_field_errors() {
        let yaml = r#"
version: 1
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
        let yaml = r#"version: 1"#;
        let cfg: Config = serde_yaml::from_str(yaml).expect("config");
        assert_eq!(cfg.version, 1);
        assert_eq!(cfg.paths.log_root, "~/lasso-logs");
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
        let cfg: Config = serde_yaml::from_str("version: 1").unwrap();
        let envs = config_to_env(&cfg);
        write_env_file(&env_path, &envs).unwrap();
        let content = fs::read_to_string(&env_path).unwrap();
        assert!(content.contains("LASSO_VERSION="));
        assert!(content.contains("LASSO_LOG_ROOT="));
    }
}
