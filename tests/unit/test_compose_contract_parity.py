from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


pytestmark = pytest.mark.unit


ROOT_DIR = Path(__file__).resolve().parents[2]
COMPOSE_BASE = ROOT_DIR / "compose.yml"
COMPOSE_TEST_OVERRIDE = ROOT_DIR / "tests" / "integration" / "compose.test.override.yml"
AGENT_DOCKERFILE = ROOT_DIR / "agent" / "Dockerfile"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"compose file is not a mapping: {path}")
    return payload


def _service(payload: dict[str, Any], name: str) -> dict[str, Any]:
    services = payload.get("services")
    if not isinstance(services, dict):
        raise AssertionError("compose file missing services mapping")
    service = services.get(name)
    if not isinstance(service, dict):
        raise AssertionError(f"compose file missing service={name}")
    return service


def _env_keys(service: dict[str, Any]) -> set[str]:
    raw = service.get("environment")
    if raw is None:
        return set()
    if isinstance(raw, dict):
        return {str(key) for key in raw}
    if isinstance(raw, list):
        keys: set[str] = set()
        for value in raw:
            if not isinstance(value, str):
                continue
            key = value.split("=", 1)[0].strip()
            if key:
                keys.add(key)
        return keys
    return set()


def _volume_modes(service: dict[str, Any]) -> dict[str, str]:
    raw = service.get("volumes")
    if not isinstance(raw, list):
        return {}

    modes: dict[str, str] = {}
    for entry in raw:
        if isinstance(entry, str):
            parts = entry.rsplit(":", 2)
            if len(parts) == 3:
                _, target, mode = parts
            elif len(parts) == 2:
                _, target = parts
                mode = "rw"
            else:
                continue
            modes[target] = mode
            continue

        if isinstance(entry, dict):
            target = entry.get("target")
            if not isinstance(target, str):
                continue
            read_only = bool(entry.get("read_only", False))
            modes[target] = "ro" if read_only else "rw"

    return modes


def test_compose_base_runtime_contract() -> None:
    payload = _load_yaml(COMPOSE_BASE)
    for service_name in ("collector", "agent", "harness"):
        _service(payload, service_name)

    collector = _service(payload, "collector")
    assert collector.get("privileged") is True
    assert collector.get("pid") == "host"

    harness = _service(payload, "harness")
    ports = harness.get("ports")
    assert isinstance(ports, list) and ports, "harness must expose an API host port"
    assert any(
        isinstance(value, str) and "${HARNESS_HOST_PORT:-8081}:8081" in value
        for value in ports
    ), "harness host port must be parameterized for isolated tests"

    collector_volumes = _volume_modes(collector)
    assert collector_volumes.get("/logs") == "rw"
    assert collector_volumes.get("/work") == "ro"

    agent_volumes = _volume_modes(_service(payload, "agent"))
    assert agent_volumes.get("/logs") == "ro"
    assert agent_volumes.get("/work") == "rw"
    assert agent_volumes.get("/config") == "ro"
    agent = _service(payload, "agent")
    cap_drop = agent.get("cap_drop")
    assert isinstance(cap_drop, list), "agent cap_drop must be configured"
    assert "SYS_ADMIN" in cap_drop
    security_opt = agent.get("security_opt")
    assert isinstance(security_opt, list), "agent security_opt must be configured"
    assert "no-new-privileges:true" in security_opt

    harness_volumes = _volume_modes(harness)
    assert harness_volumes.get("/logs") == "rw"
    assert harness_volumes.get("/work") == "rw"
    assert harness_volumes.get("/harness/keys") == "rw"

    assert {
        "LASSO_RUN_ID",
        "COLLECTOR_AUDIT_LOG",
        "COLLECTOR_EBPF_OUTPUT",
        "COLLECTOR_FILTER_OUTPUT",
        "COLLECTOR_EBPF_FILTER_OUTPUT",
        "COLLECTOR_EBPF_SUMMARY_OUTPUT",
        "COLLECTOR_MERGE_FILTER_OUTPUT",
        "COLLECTOR_SESSIONS_DIR",
        "COLLECTOR_JOBS_DIR",
        "COLLECTOR_ROOT_COMM",
    }.issubset(
        _env_keys(collector)
    )
    assert {
        "LASSO_RUN_ID",
        "HARNESS_AGENT_HOST",
        "HARNESS_AGENT_PORT",
        "HARNESS_AGENT_USER",
        "HARNESS_HTTP_BIND",
        "HARNESS_HTTP_PORT",
        "HARNESS_API_TOKEN",
        "HARNESS_AGENT_WORKDIR",
        "HARNESS_LOG_DIR",
        "HARNESS_TIMELINE_PATH",
        "HARNESS_TUI_CMD",
        "HARNESS_RUN_CMD_TEMPLATE",
    }.issubset(_env_keys(harness))


def test_test_override_is_minimal_and_allowlisted() -> None:
    payload = _load_yaml(COMPOSE_TEST_OVERRIDE)
    services = payload.get("services")
    assert isinstance(services, dict), "test override must define services mapping"
    assert set(services) == {"collector", "agent", "harness"}

    collector = _service(payload, "collector")
    assert set(collector) <= {"build", "image", "volumes", "environment"}
    assert "privileged" not in collector
    assert "pid" not in collector

    collector_volumes = _volume_modes(collector)
    assert collector_volumes.get("/test-config") == "ro"
    assert "/logs" not in collector_volumes
    assert "/work" not in collector_volumes

    assert _env_keys(collector) == {
        "COLLECTOR_FILTER_CONFIG",
        "COLLECTOR_EBPF_FILTER_CONFIG",
    }

    assert set(_service(payload, "agent")) <= {"build", "image"}
    assert set(_service(payload, "harness")) <= {"build", "image"}


def test_agent_dockerfile_config_dir_owned_by_harness_uid_for_shared_keys_volume() -> None:
    content = AGENT_DOCKERFILE.read_text(encoding="utf-8")
    assert "chown 1002:1002 /config" in content
    assert "chmod 700 /config" in content
