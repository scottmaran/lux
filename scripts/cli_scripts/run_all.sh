#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

"$SCRIPT_DIR/00_config_init.sh"
"$SCRIPT_DIR/01_config_validate_unknown.sh"
"$SCRIPT_DIR/02_config_apply.sh"
"$SCRIPT_DIR/03_config_apply_invalid.sh"
"$SCRIPT_DIR/04_doctor_no_docker.sh"
"$SCRIPT_DIR/05_doctor_log_root_unwritable.sh"
"$SCRIPT_DIR/06_status_no_docker.sh"
"$SCRIPT_DIR/11_upgrade_env.sh"
"$SCRIPT_DIR/12_missing_ghcr_auth.sh"
"$SCRIPT_DIR/13_up_wait_timeout.sh"
"$SCRIPT_DIR/14_down_cleanup_flags.sh"
"$SCRIPT_DIR/15_paths_json.sh"
"$SCRIPT_DIR/16_uninstall_dry_run.sh"
"$SCRIPT_DIR/17_uninstall_exec.sh"
"$SCRIPT_DIR/10_stack_smoke.sh"

echo "All CLI integration scripts completed."
