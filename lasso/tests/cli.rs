use assert_cmd::Command;
use serde_json::Value;
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::symlink;
use tempfile::tempdir;

fn bin() -> Command {
    let path = assert_cmd::cargo::cargo_bin!("lasso");
    Command::new(path)
}

fn parse_json(bytes: &[u8]) -> Value {
    serde_json::from_slice(bytes).expect("json output")
}

#[test]
fn config_init_creates_and_preserves_existing() {
    let dir = tempdir().unwrap();
    let config_dir = dir.path().join("config");

    let output = bin()
        .env("LASSO_CONFIG_DIR", &config_dir)
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
        .env("LASSO_CONFIG_DIR", &config_dir)
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
        "version: 1\nunknown_field: true\npaths:\n  log_root: /tmp/logs\n  workspace_root: /tmp/work\n",
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
fn config_apply_writes_env_and_dirs() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let env_file = dir.path().join("compose.env");

    let yaml = format!(
        "version: 1\npaths:\n  log_root: {}\n  workspace_root: {}\n",
        log_root.display(),
        work_root.display()
    );
    fs::write(&config_path, yaml).unwrap();

    bin()
        .arg("--config")
        .arg(&config_path)
        .env("LASSO_ENV_FILE", &env_file)
        .arg("config")
        .arg("apply")
        .assert()
        .success();

    let env_content = fs::read_to_string(&env_file).unwrap();
    assert!(env_content.contains("LASSO_VERSION="));
    assert!(env_content.contains("LASSO_LOG_ROOT="));
    assert!(env_content.contains("LASSO_WORKSPACE_ROOT="));

    assert!(log_root.exists());
    assert!(work_root.exists());
}

#[test]
fn config_apply_invalid_config_is_actionable() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 1\nunknown: true\n").unwrap();

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
    let config_path = dir.path().join("config.yaml");
    let log_root = dir.path().join("logs");

    let yaml = format!(
        "version: 1\npaths:\n  log_root: {}\n  workspace_root: {}\n",
        log_root.display(),
        log_root.display()
    );
    fs::write(&config_path, yaml).unwrap();

    let output = bin()
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
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("docker"));
}

#[test]
fn status_fails_when_docker_missing() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 1\n").unwrap();

    bin()
        .env("PATH", "")
        .arg("--config")
        .arg(&config_path)
        .arg("status")
        .assert()
        .failure();
}

#[test]
fn run_requires_token() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 1\n").unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .arg("run")
        .arg("hello")
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();

    let value = parse_json(&output);
    let error = value["error"].as_str().unwrap_or_default();
    assert!(error.contains("HARNESS_API_TOKEN"));
}

#[test]
fn paths_reports_resolved_values() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let install_dir = dir.path().join("install");
    let bin_dir = dir.path().join("bin");
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(&env_file, "LASSO_VERSION=v0.1.0\n").unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 1\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("LASSO_ENV_FILE", &env_file)
        .env("LASSO_INSTALL_DIR", &install_dir)
        .env("LASSO_BIN_DIR", &bin_dir)
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
        log_root.to_string_lossy()
    );
    assert_eq!(
        value["result"]["workspace_root"].as_str().unwrap(),
        work_root.to_string_lossy()
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
fn uninstall_requires_yes_without_dry_run() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 1\n").unwrap();

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
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let install_dir = dir.path().join("install");
    let versions_dir = install_dir.join("versions").join("0.1.0");
    let current_link = install_dir.join("current");
    let bin_dir = dir.path().join("bin");
    let bin_link = bin_dir.join("lasso");
    fs::create_dir_all(&versions_dir).unwrap();
    fs::create_dir_all(&bin_dir).unwrap();
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(versions_dir.join("lasso"), "binary").unwrap();
    symlink(&versions_dir, &current_link).unwrap();
    symlink(current_link.join("lasso"), &bin_link).unwrap();
    fs::write(&env_file, "LASSO_VERSION=v0.1.0\n").unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 1\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("LASSO_ENV_FILE", &env_file)
        .env("LASSO_INSTALL_DIR", &install_dir)
        .env("LASSO_BIN_DIR", &bin_dir)
        .arg("uninstall")
        .arg("--dry-run")
        .arg("--remove-config")
        .arg("--remove-data")
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
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let install_dir = dir.path().join("install");
    let versions_dir = install_dir.join("versions").join("0.1.0");
    let current_link = install_dir.join("current");
    let bin_dir = dir.path().join("bin");
    let bin_link = bin_dir.join("lasso");
    fs::create_dir_all(&versions_dir).unwrap();
    fs::create_dir_all(&bin_dir).unwrap();
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(versions_dir.join("lasso"), "binary").unwrap();
    symlink(&versions_dir, &current_link).unwrap();
    symlink(current_link.join("lasso"), &bin_link).unwrap();
    fs::write(&env_file, "LASSO_VERSION=v0.1.0\n").unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 1\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("LASSO_ENV_FILE", &env_file)
        .env("LASSO_INSTALL_DIR", &install_dir)
        .env("LASSO_BIN_DIR", &bin_dir)
        .arg("uninstall")
        .arg("--yes")
        .arg("--remove-config")
        .arg("--remove-data")
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
    assert!(!log_root.exists());
    assert!(!work_root.exists());
}
