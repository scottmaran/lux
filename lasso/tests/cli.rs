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
        "version: 2\nunknown_field: true\npaths:\n  log_root: /tmp/logs\n  workspace_root: /tmp/work\n",
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
        "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
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
    let config_path = dir.path().join("config.yaml");
    let log_root = dir.path().join("logs");

    let yaml = format!(
        "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
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
    fs::write(&config_path, "version: 2\n").unwrap();

    bin()
        .env("PATH", "")
        .arg("--config")
        .arg(&config_path)
        .arg("status")
        .arg("--collector-only")
        .assert()
        .failure();
}

#[test]
fn run_requires_active_provider_plane() {
    let dir = tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 2\n").unwrap();

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
    let config_path = dir.path().join("config.yaml");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
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
    let config_path = dir.path().join("config.yaml");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let run_1 = "lasso__2026_02_11_12_00_00";
    let run_2 = "lasso__2026_02_12_12_00_00";
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
    let config_path = dir.path().join("config.yaml");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let run_id = "lasso__2026_02_12_12_00_00";
    let jobs_dir = log_root.join(run_id).join("harness").join("jobs");
    fs::create_dir_all(jobs_dir.join("job_1")).unwrap();
    fs::create_dir_all(jobs_dir.join("job_2")).unwrap();

    let output = bin()
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
    let home = dir.path();
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let install_dir = home.join(".lasso");
    let bin_dir = home.join(".local").join("bin");
    fs::create_dir_all(&log_root).unwrap();
    fs::create_dir_all(&work_root).unwrap();
    fs::write(&env_file, "LASSO_VERSION=v0.1.0\n").unwrap();
    fs::write(
        &config_path,
        format!(
            "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", home)
        .env("LASSO_ENV_FILE", &env_file)
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
    fs::write(&config_path, "version: 2\n").unwrap();

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
    let home = dir.path();
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let install_dir = home.join(".lasso");
    let versions_dir = install_dir.join("versions").join("0.1.0");
    let current_link = install_dir.join("current");
    let bin_dir = home.join(".local").join("bin");
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
            "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", home)
        .env("LASSO_ENV_FILE", &env_file)
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
    let home = dir.path();
    let config_path = dir.path().join("config.yaml");
    let env_file = dir.path().join("compose.env");
    let log_root = dir.path().join("logs");
    let work_root = dir.path().join("work");
    let install_dir = home.join(".lasso");
    let versions_dir = install_dir.join("versions").join("0.1.0");
    let current_link = install_dir.join("current");
    let bin_dir = home.join(".local").join("bin");
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
            "version: 2\npaths:\n  log_root: {}\n  workspace_root: {}\n",
            log_root.display(),
            work_root.display()
        ),
    )
    .unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", home)
        .env("LASSO_ENV_FILE", &env_file)
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
    fs::write(&config_path, "version: 2\n").unwrap();

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
    let home = dir.path();
    let config_path = dir.path().join("config.yaml");
    fs::write(&config_path, "version: 2\n").unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", home)
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
    let home = dir.path();
    let config_path = dir.path().join("config.yaml");
    let install_dir = home.join(".lasso");
    let versions_dir = install_dir.join("versions");
    let v1 = versions_dir.join("0.1.0");
    let v2 = versions_dir.join("0.2.0");
    fs::create_dir_all(&v1).unwrap();
    fs::create_dir_all(&v2).unwrap();
    fs::write(v1.join("lasso"), "v1").unwrap();
    fs::write(v2.join("lasso"), "v2").unwrap();
    symlink(&v2, install_dir.join("current")).unwrap();
    fs::write(&config_path, "version: 2\n").unwrap();

    let output = bin()
        .arg("--json")
        .arg("--config")
        .arg(&config_path)
        .env("HOME", home)
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
