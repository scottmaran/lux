use assert_cmd::Command;
use predicates::str::contains;
use serde_json::Value;
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};
use tempfile::tempdir;

fn bin() -> Command {
    let path = assert_cmd::cargo::cargo_bin!("lux");
    Command::new(path)
}

fn parse_json(bytes: &[u8]) -> Value {
    serde_json::from_slice(bytes).expect("json output")
}

fn make_policy_paths(root: &Path) -> (PathBuf, PathBuf, PathBuf, PathBuf) {
    let home = root.join("home");
    let trusted_root = root.join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(&trusted_root).unwrap();
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&workspace_root).unwrap();
    (home, trusted_root, log_root, workspace_root)
}

fn write_config_with_paths(
    config_path: &Path,
    trusted_root: &Path,
    log_root: &Path,
    workspace_root: &Path,
) {
    let shims_bin_dir = trusted_root.join("bin");
    fs::create_dir_all(&shims_bin_dir).unwrap();
    fs::write(
        config_path,
        format!(
            "version: 2\npaths:\n  trusted_root: {}\n  log_root: {}\n  workspace_root: {}\nshims:\n  bin_dir: {}\n",
            trusted_root.display(),
            log_root.display(),
            workspace_root.display(),
            shims_bin_dir.display()
        ),
    )
    .unwrap();
}

fn write_valid_config(config_path: &Path) {
    let parent = config_path.parent().unwrap_or_else(|| Path::new("."));
    let trusted_root = parent.join("trusted");
    let log_root = trusted_root.join("logs");
    let home = PathBuf::from(std::env::var("HOME").expect("HOME"));
    let workspace_root = home.join("workspace");
    write_config_with_paths(config_path, &trusted_root, &log_root, &workspace_root);
}

fn write_default_template_config(config_dir: &Path, trusted_root: &Path) -> PathBuf {
    let template =
        fs::read_to_string("config/default.yaml").expect("read config/default.yaml template");
    let trusted_root_text = trusted_root.to_string_lossy().to_string();
    let config = template.replace("/var/lib/lux", &trusted_root_text);
    let config_path = config_dir.join("config.yaml");
    fs::write(&config_path, config).unwrap();
    config_path
}

#[test]
fn config_init_creates_and_preserves_existing() {
    let dir = tempdir().unwrap();
    let config_dir = dir.path().join("config");

    let output = bin()
        .env("LUX_CONFIG_DIR", &config_dir)
        .arg("--json")
        .arg("config")
        .arg("init")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert!(value["result"]["created"].as_bool().unwrap());

    let config_path = config_dir.join("config.yaml");
    assert!(config_path.exists());

    fs::write(&config_path, "sentinel: true\n").unwrap();

    let output = bin()
        .env("LUX_CONFIG_DIR", &config_dir)
        .arg("--json")
        .arg("config")
        .arg("init")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert!(!value["result"]["created"].as_bool().unwrap());

    let content = fs::read_to_string(&config_path).unwrap();
    assert_eq!(content, "sentinel: true\n");
}

#[test]
fn config_validate_rejects_unknown_fields() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(
        &config_path,
        "version: 2\nunknown_field: true\npaths:\n  trusted_root: /var/lib/lux\n  log_root: /var/lib/lux/logs\n  workspace_root: /tmp/work\n",
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("config")
        .arg("validate")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(!value["ok"].as_bool().unwrap());
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("unknown_field") || error.contains("unknown field"));
}

#[test]
fn config_validate_rejects_workspace_outside_home() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = dir.path().join("workspace-outside-home");
    let shims_bin_dir = trusted_root.join("bin");
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  trusted_root: {}\n  log_root: {}\n  workspace_root: {}\nshims:\n  bin_dir: {}\n",
            trusted_root.display(),
            log_root.display(),
            workspace_root.display(),
            shims_bin_dir.display()
        ),
    )
    .unwrap();

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("config")
        .arg("validate")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("paths.workspace_root must be under $HOME"));
}

#[test]
fn config_validate_rejects_log_root_inside_home() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = home.join("logs-inside-home");
    let workspace_root = home.join("workspace");
    let shims_bin_dir = trusted_root.join("bin");
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  trusted_root: {}\n  log_root: {}\n  workspace_root: {}\nshims:\n  bin_dir: {}\n",
            trusted_root.display(),
            log_root.display(),
            workspace_root.display(),
            shims_bin_dir.display()
        ),
    )
    .unwrap();

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("config")
        .arg("validate")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("paths.log_root must be inside paths.trusted_root"));
}

#[test]
fn run_rejects_removed_cwd_flag() {
    let output = bin()
        .arg("run")
        .arg("--provider")
        .arg("codex")
        .arg("--cwd")
        .arg("/work")
        .arg("hello")
        .assert()
        .failure()
        .get_output()
        .stderr
        .clone();
    let stderr = String::from_utf8_lossy(&output);
    assert!(stderr.contains("--cwd"));
}

#[test]
fn config_apply_writes_env_and_dirs() {
    let dir = tempdir().unwrap();
    let (home, trusted_root, log_root, work_root) = make_policy_paths(dir.path());
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    bin()
        .arg("--config")
        .arg(&config_path)
        .env("HOME", &home)
        .env("LUX_ENV_FILE", &env_file)
        .arg("config")
        .arg("apply")
        .assert()
        .success();

    let env_content = fs::read_to_string(&env_file).unwrap();
    assert!(env_content.contains("LUX_VERSION="));
    assert!(env_content.contains("LUX_LOG_ROOT="));
    assert!(env_content.contains("LUX_WORKSPACE_ROOT="));

    assert!(log_root.exists());
    assert!(work_root.exists());
}

#[test]
fn config_apply_invalid_config_is_actionable() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 2\nunknown: true\n").unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("config")
        .arg("apply")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("config is invalid"));
    assert!(error.contains("Please edit"));
}

#[test]
fn doctor_reports_missing_docker_in_json() {
    let dir = tempdir().unwrap();
    let (home, trusted_root, log_root, work_root) = make_policy_paths(dir.path());
    let config_path = dir.path().join("config.yaml");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let output = bin()
        .env("HOME", &home)
        .env("PATH", "")
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("doctor")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(!value["ok"].as_bool().unwrap());
    let checks = value["result"]["checks"].as_array().expect("checks");
    let docker = checks
        .iter()
        .find(|row| row["id"] == "docker_runtime")
        .expect("docker_runtime check");
    assert_eq!(docker["ok"], false);
    let docker_compose = checks
        .iter()
        .find(|row| row["id"] == "docker_compose")
        .expect("docker_compose check");
    assert_eq!(docker_compose["ok"], false);
}

#[test]
fn doctor_strict_fails_when_checks_fail() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    bin()
        .env("PATH", "")
        .arg("--config")
        .arg(&config_path)
        .arg("doctor")
        .arg("--strict")
        .assert()
        .failure();
}

#[test]
fn status_fails_when_docker_missing() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    bin()
        .env("PATH", "")
        .arg("--config")
        .arg(&config_path)
        .arg("--compose-file")
        .arg("../compose.yml")
        .arg("--compose-file")
        .arg("../tests/integration/compose.test.override.yml")
        .arg("status")
        .arg("--collector-only")
        .assert()
        .failure();
}

#[test]
fn status_json_includes_structured_docker_error_details() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    let output = bin()
        .env("PATH", "")
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("--compose-file")
        .arg("../compose.yml")
        .arg("--compose-file")
        .arg("../tests/integration/compose.test.override.yml")
        .arg("status")
        .arg("--collector-only")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(!value["ok"].as_bool().unwrap());
    assert_eq!(value["error_details"]["error_code"], "docker_not_found");
    let command = value["error_details"]["command"]
        .as_str()
        .unwrap_or_default();
    assert!(command.contains("docker compose"));
    let hint = value["error_details"]["hint"].as_str().unwrap_or_default();
    assert!(hint.contains("Install Docker"));
}

#[test]
fn run_requires_active_provider_plane() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("run")
        .arg("--provider")
        .arg("codex")
        .arg("hello")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("active provider plane"));
}

#[test]
fn logs_tail_without_active_run_fails_with_actionable_error() {
    let dir = tempdir().unwrap();
    let (home, trusted_root, log_root, work_root) = make_policy_paths(dir.path());
    let config_path = dir.path().join("config.yaml");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("logs")
        .arg("tail")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("no active run found"));
}

#[test]
fn logs_tail_latest_resolves_most_recent_run_directory() {
    let dir = tempdir().unwrap();
    let (home, trusted_root, log_root, work_root) = make_policy_paths(dir.path());
    let config_path = dir.path().join("config.yaml");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let run_1 = "lux__2026_02_11_12_00_00";
    let run_2 = "lux__2026_02_12_12_00_00";
    let t1 = log_root
        .join(run_1)
        .join("collector")
        .join("filtered")
        .join("filtered_timeline.jsonl");
    let t2 = log_root
        .join(run_2)
        .join("collector")
        .join("filtered")
        .join("filtered_timeline.jsonl");
    fs::create_dir_all(t1.parent().unwrap()).unwrap();
    fs::create_dir_all(t2.parent().unwrap()).unwrap();
    fs::write(&t1, "{\"ts\":\"2026-02-11T12:00:00Z\"}\n").unwrap();
    fs::write(&t2, "{\"ts\":\"2026-02-12T12:00:00Z\"}\n").unwrap();

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("logs")
        .arg("tail")
        .arg("--latest")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    assert_eq!(value["result"]["run_id"], run_2);
    let path = value["result"]["path"].as_str().unwrap_or_default();
    assert!(path.contains(run_2));
}

#[test]
fn jobs_list_with_run_id_uses_run_scoped_jobs_directory() {
    let dir = tempdir().unwrap();
    let (home, trusted_root, log_root, work_root) = make_policy_paths(dir.path());
    let config_path = dir.path().join("config.yaml");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let run_id = "lux__2026_02_12_12_00_00";
    let jobs_dir = log_root.join(run_id).join("harness").join("jobs");
    fs::create_dir_all(jobs_dir.join("job_1")).unwrap();
    fs::create_dir_all(jobs_dir.join("job_2")).unwrap();

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("jobs")
        .arg("list")
        .arg("--run-id")
        .arg(run_id)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    assert_eq!(value["result"]["run_id"], run_id);
    let jobs = value["result"]["jobs"].as_array().expect("jobs array");
    let rendered: Vec<String> = jobs
        .iter()
        .filter_map(|v| v.as_str().map(ToString::to_string))
        .collect();
    assert!(rendered.contains(&"job_1".to_string()));
    assert!(rendered.contains(&"job_2".to_string()));
}

#[test]
fn paths_reports_resolved_values() {
    let dir = tempdir().unwrap();
    let (home, trusted_root, log_root, work_root) = make_policy_paths(dir.path());
    let canonical_log_root = fs::canonicalize(&log_root).unwrap();
    let canonical_work_root = fs::canonicalize(&work_root).unwrap();
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let install_dir = home.join(".lux");
    let bin_dir = home.join(".local").join("bin");
    fs::write(&env_file, "LUX_VERSION=v0.1.0\n").unwrap();
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", home)
        .env("LUX_ENV_FILE", &env_file)
        .arg("paths")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert_eq!(
        value["result"]["log_root"].as_str().unwrap(),
        canonical_log_root.to_string_lossy()
    );
    assert_eq!(
        value["result"]["workspace_root"].as_str().unwrap(),
        canonical_work_root.to_string_lossy()
    );
    assert_eq!(
        value["result"]["install_dir"].as_str().unwrap(),
        install_dir.to_string_lossy()
    );
    assert_eq!(
        value["result"]["bin_dir"].as_str().unwrap(),
        bin_dir.to_string_lossy()
    );
}

#[test]
fn setup_defaults_creates_secrets_from_env_when_missing() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let config_dir = dir.path().join("config");
    let trusted_root = dir.path().join("trusted");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(&config_dir).unwrap();
    let _config_path = write_default_template_config(&config_dir, &trusted_root);

    let secrets_path = trusted_root.join("secrets").join("codex.env");
    assert!(!secrets_path.exists());

    let output = bin()
        .env("HOME", &home)
        .env("LUX_CONFIG_DIR", &config_dir)
        .env("OPENAI_API_KEY", "test-key-123")
        .arg("--json")
        .arg("setup")
        .arg("--defaults")
        .arg("--yes")
        .arg("--no-apply")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert!(secrets_path.exists());

    let content = fs::read_to_string(&secrets_path).unwrap();
    assert!(content.contains("OPENAI_API_KEY="));
    assert!(content.contains("test-key-123"));

    let config_path = config_dir.join("config.yaml");
    assert!(config_path.exists());

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = fs::metadata(&secrets_path).unwrap().permissions().mode() & 0o777;
        assert_eq!(mode, 0o600);
    }
}

#[test]
fn setup_defaults_errors_when_api_key_missing_and_env_missing() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let config_dir = dir.path().join("config");
    let trusted_root = dir.path().join("trusted");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(&config_dir).unwrap();
    let _config_path = write_default_template_config(&config_dir, &trusted_root);

    let output = bin()
        .env("HOME", &home)
        .env("LUX_CONFIG_DIR", &config_dir)
        .arg("--json")
        .arg("setup")
        .arg("--defaults")
        .arg("--no-apply")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(!value["ok"].as_bool().unwrap());
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("OPENAI_API_KEY"));
    assert!(error.contains("secrets"));
}

#[test]
fn setup_dry_run_writes_nothing() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let config_dir = dir.path().join("config");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(&config_dir).unwrap();

    let config_path = config_dir.join("config.yaml");
    let secrets_path = home
        .join(".config")
        .join("lux")
        .join("secrets")
        .join("codex.env");

    let output = bin()
        .env("HOME", &home)
        .env("LUX_CONFIG_DIR", &config_dir)
        .env("OPENAI_API_KEY", "dry-run-key")
        .arg("--json")
        .arg("setup")
        .arg("--defaults")
        .arg("--dry-run")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert!(value["result"]["dry_run"].as_bool().unwrap());

    assert!(!config_path.exists());
    assert!(!secrets_path.exists());
}

#[test]
fn uninstall_requires_yes_without_dry_run() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("uninstall")
        .arg("--force")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("--yes"));
}

#[cfg(unix)]
#[test]
fn uninstall_dry_run_preserves_files() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let work_root = home.join("work");
    let install_dir = home.join(".lux");
    let versions_dir = install_dir.join("versions").join("0.1.0");
    let current_link = install_dir.join("current");
    let bin_dir = home.join(".local").join("bin");
    let bin_link = bin_dir.join("lux");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(&versions_dir).unwrap();
    fs::create_dir_all(&bin_dir).unwrap();
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(versions_dir.join("lux"), "binary").unwrap();
    symlink(&versions_dir, &current_link).unwrap();
    symlink(current_link.join("lux"), &bin_link).unwrap();
    fs::write(&env_file, "LUX_VERSION=v0.1.0\n").unwrap();
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", &home)
        .env("LUX_ENV_FILE", &env_file)
        .arg("uninstall")
        .arg("--dry-run")
        .arg("--remove-config")
        .arg("--all-versions")
        .arg("--force")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["result"]["dry_run"].as_bool().unwrap());
    assert!(bin_link.exists());
    assert!(current_link.exists());
    assert!(install_dir.join("versions").exists());
    assert!(config_path.exists());
    assert!(env_file.exists());
    assert!(log_root.exists());
    assert!(work_root.exists());
}

#[cfg(unix)]
#[test]
fn uninstall_exec_removes_requested_targets() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let work_root = home.join("work");
    let install_dir = home.join(".lux");
    let versions_dir = install_dir.join("versions").join("0.1.0");
    let current_link = install_dir.join("current");
    let bin_dir = home.join(".local").join("bin");
    let bin_link = bin_dir.join("lux");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(&versions_dir).unwrap();
    fs::create_dir_all(&bin_dir).unwrap();
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(versions_dir.join("lux"), "binary").unwrap();
    symlink(&versions_dir, &current_link).unwrap();
    symlink(current_link.join("lux"), &bin_link).unwrap();
    fs::write(&env_file, "LUX_VERSION=v0.1.0\n").unwrap();
    write_config_with_paths(&config_path, &trusted_root, &log_root, &work_root);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", &home)
        .env("LUX_ENV_FILE", &env_file)
        .arg("uninstall")
        .arg("--yes")
        .arg("--remove-config")
        .arg("--all-versions")
        .arg("--force")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(!value["result"]["dry_run"].as_bool().unwrap());
    assert!(!bin_link.exists());
    assert!(!current_link.exists());
    assert!(!install_dir.join("versions").exists());
    assert!(!config_path.exists());
    assert!(!env_file.exists());
    assert!(log_root.exists());
    assert!(work_root.exists());
}

#[test]
fn update_apply_requires_yes_without_dry_run() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("update")
        .arg("apply")
        .arg("--to")
        .arg("v0.1.0")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("requires --yes"));
}

#[test]
fn update_apply_dry_run_reports_target() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &workspace_root);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", &home)
        .arg("update")
        .arg("apply")
        .arg("--to")
        .arg("0.9.9")
        .arg("--dry-run")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert_eq!(value["result"]["target_version"], "v0.9.9");
    assert_eq!(value["result"]["dry_run"], true);
}

#[cfg(unix)]
#[test]
fn update_rollback_dry_run_previous_selects_prior_version() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    let install_dir = home.join(".lux");
    let versions_dir = install_dir.join("versions");
    let v1 = versions_dir.join("0.1.0");
    let v2 = versions_dir.join("0.2.0");
    fs::create_dir_all(&v1).unwrap();
    fs::create_dir_all(&v2).unwrap();
    fs::write(v1.join("lux"), "v1").unwrap();
    fs::write(v2.join("lux"), "v2").unwrap();
    symlink(&v2, install_dir.join("current")).unwrap();
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &workspace_root);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", &home)
        .arg("update")
        .arg("rollback")
        .arg("--dry-run")
        .arg("--previous")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    assert!(value["ok"].as_bool().unwrap());
    assert_eq!(value["result"]["target_version"], "v0.1.0");
}

#[test]
fn ui_url_returns_default_local_url() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("ui")
        .arg("url")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    assert_eq!(value["result"]["url"], "http://127.0.0.1:8090");
}

#[test]
fn up_rejects_removed_ui_flag() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    bin()
        .arg("--config")
        .arg(&config_path)
        .arg("up")
        .arg("--collector-only")
        .arg("--ui")
        .assert()
        .failure()
        .stderr(contains("unexpected argument '--ui'"));
}

#[cfg(unix)]
#[test]
fn runtime_up_status_down_cycle() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    write_valid_config(&config_path);

    let up = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("runtime")
        .arg("up")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let up_value = parse_json(&up);
    assert!(up_value["result"]["running"].as_bool().unwrap_or(false));

    let status = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("runtime")
        .arg("status")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let status_value = parse_json(&status);
    assert!(status_value["result"]["running"].as_bool().unwrap_or(false));

    let down = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("runtime")
        .arg("down")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let down_value = parse_json(&down);
    assert!(!down_value["result"]["running"].as_bool().unwrap_or(true));
}

#[cfg(unix)]
#[test]
fn shim_enable_status_disable_roundtrip() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    fs::write(home.join(".zprofile"), "# existing zprofile\n").unwrap();
    fs::write(home.join(".bashrc"), "# existing bashrc\n").unwrap();
    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &workspace_root);

    let shims_bin = trusted_root.join("bin");
    let path_env = format!(
        "{}:{}",
        shims_bin.display(),
        std::env::var("PATH").unwrap_or_default()
    );

    let enable = bin()
        .env("PATH", &path_env)
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("enable")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let enable_value = parse_json(&enable);
    assert_eq!(enable_value["result"]["action"], "shim_enable");
    assert_eq!(enable_value["result"]["path"]["state"], "configured");
    let path_rows = enable_value["result"]["path"]["files"].as_array().unwrap();
    assert_eq!(path_rows.len(), 2);
    assert!(path_rows
        .iter()
        .all(|row| row["managed_block_present"].as_bool().unwrap_or(false)));

    let shim_path = trusted_root.join("bin").join("codex");
    let claude_shim_path = trusted_root.join("bin").join("claude");
    assert!(shim_path.exists());
    assert!(claude_shim_path.exists());

    let zprofile = fs::read_to_string(home.join(".zprofile")).unwrap();
    assert!(zprofile.contains("# >>> lux-shim-path >>>"));
    assert!(zprofile.contains("# <<< lux-shim-path <<<"));

    let status = bin()
        .env("PATH", &path_env)
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("status")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let status_value = parse_json(&status);
    assert_eq!(status_value["result"]["action"], "shim_status");
    assert_eq!(status_value["result"]["state"], "enabled");
    assert_eq!(
        status_value["result"]["path_persistence"]["state"],
        "configured"
    );
    let shims = status_value["result"]["shims"].as_array().unwrap();
    let codex = shims
        .iter()
        .find(|row| row["provider"] == "codex")
        .expect("codex shim row");
    assert_eq!(codex["installed"], true);
    let claude = shims
        .iter()
        .find(|row| row["provider"] == "claude")
        .expect("claude shim row");
    assert_eq!(claude["installed"], true);

    let disable = bin()
        .env("PATH", &path_env)
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("disable")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let disable_value = parse_json(&disable);
    assert_eq!(disable_value["result"]["action"], "shim_disable");
    assert_eq!(disable_value["result"]["path"]["state"], "absent");
    let disable_rows = disable_value["result"]["path"]["files"].as_array().unwrap();
    assert_eq!(disable_rows.len(), 2);
    assert!(disable_rows
        .iter()
        .all(|row| !row["managed_block_present"].as_bool().unwrap_or(true)));

    let zprofile_after = fs::read_to_string(home.join(".zprofile")).unwrap();
    assert!(!zprofile_after.contains("# >>> lux-shim-path >>>"));

    let final_status = bin()
        .env("PATH", &path_env)
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("status")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let final_status_value = parse_json(&final_status);
    assert_eq!(final_status_value["result"]["state"], "disabled");
    assert_eq!(
        final_status_value["result"]["path_persistence"]["state"],
        "absent"
    );

    assert!(!shim_path.exists());
    assert!(!claude_shim_path.exists());
}

#[cfg(unix)]
#[test]
fn shim_enable_no_startup_files_returns_no_startup_files_state() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &workspace_root);

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("enable")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    assert_eq!(value["result"]["path"]["state"], "no_startup_files");
    let files = value["result"]["path"]["files"].as_array().unwrap();
    assert!(files.is_empty());

    let status = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("status")
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let status_value = parse_json(&status);
    assert_eq!(
        status_value["result"]["path_persistence"]["state"],
        "no_startup_files"
    );

    assert!(!home.join(".zprofile").exists());
    assert!(!home.join(".zshrc").exists());
    assert!(!home.join(".bash_profile").exists());
    assert!(!home.join(".bash_login").exists());
    assert!(!home.join(".profile").exists());
    assert!(!home.join(".bashrc").exists());
}

#[cfg(unix)]
#[test]
fn shim_enable_path_failure_returns_json_partial_outcome() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    fs::create_dir_all(home.join(".zprofile")).unwrap();
    fs::write(home.join(".bashrc"), "# bashrc\n").unwrap();

    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    write_config_with_paths(&config_path, &trusted_root, &log_root, &workspace_root);

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("enable")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    assert_eq!(value["ok"], false);
    assert_eq!(value["result"], Value::Null);
    assert_eq!(
        value["error_details"]["error_code"],
        "shim_path_mutation_failed"
    );
    assert_eq!(
        value["error_details"]["partial_outcome"]["action"],
        "shim_enable"
    );
    assert_eq!(
        value["error_details"]["partial_outcome"]["shim"]["ok"],
        true
    );
    assert_eq!(
        value["error_details"]["partial_outcome"]["path"]["ok"],
        false
    );
    assert_eq!(
        value["error_details"]["partial_outcome"]["path"]["rolled_back"],
        true
    );
    let files = value["error_details"]["partial_outcome"]["path"]["files"]
        .as_array()
        .unwrap();
    let zprofile_row = files
        .iter()
        .find(|row| row["path"] == "~/.zprofile")
        .expect("zprofile error row");
    assert!(zprofile_row["error"]
        .as_str()
        .unwrap_or_default()
        .contains("failed to read"));
}

#[test]
fn shim_old_subcommands_are_rejected() {
    for legacy in ["install", "uninstall", "list"] {
        let output = bin()
            .arg("shim")
            .arg(legacy)
            .assert()
            .failure()
            .get_output()
            .stderr
            .clone();
        let stderr = String::from_utf8_lossy(&output);
        assert!(stderr.contains("unrecognized subcommand"));
    }
}

#[test]
fn shim_enable_fails_when_no_providers_configured() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    let trusted_root = dir.path().join("trusted");
    let log_root = trusted_root.join("logs");
    let workspace_root = home.join("workspace");
    fs::create_dir_all(&trusted_root).unwrap();
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&workspace_root).unwrap();
    let shims_bin_dir = trusted_root.join("bin");
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  trusted_root: {}\n  log_root: {}\n  workspace_root: {}\nshims:\n  bin_dir: {}\nproviders: {{}}\n",
            trusted_root.display(),
            log_root.display(),
            workspace_root.display(),
            shims_bin_dir.display()
        ),
    )
    .unwrap();

    let output = bin()
        .env("HOME", &home)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("enable")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("config.providers must contain at least one provider"));
}

#[test]
fn shim_exec_rejects_absolute_paths() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let workspace = home.join("workspace");
    let trusted_root = dir.path().join("trusted");
    let logs = trusted_root.join("logs");
    fs::create_dir_all(&workspace).unwrap();
    fs::create_dir_all(&logs).unwrap();
    fs::create_dir_all(&home).unwrap();
    let config_path = dir.path().join("config.yaml");
    write_config_with_paths(&config_path, &trusted_root, &logs, &workspace);

    let output = bin()
        .env("HOME", &home)
        .current_dir(&workspace)
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("shim")
        .arg("exec")
        .arg("codex")
        .arg("--")
        .arg("/tmp/host-path")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("absolute host path"));
}
