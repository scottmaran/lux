#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect forbidden actions based on policy rules.")
    parser.add_argument(
        "--config",
        default=os.getenv("COLLECTOR_FORBIDDEN_CONFIG", "/etc/collector/forbidden_detection.yaml"),
        help="Path to forbidden_detection.yaml",
    )
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if yaml:
        return yaml.safe_load(content) or {}
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise SystemExit("collector-forbidden: missing PyYAML and config is not valid JSON") from exc


def load_policy(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if yaml:
        return yaml.safe_load(content) or {}
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise SystemExit("collector-forbidden: policy is not valid JSON and PyYAML is missing") from exc


def parse_ts(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    value = ts.rstrip("Z")
    if "." in value:
        base, frac = value.split(".", 1)
        frac = (frac + "000000")[:6]
        value = base + "." + frac
    try:
        return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_match_spec(value) -> list:
    if isinstance(value, dict):
        return as_list(value.get("any"))
    return as_list(value)


def event_get(event: dict, key: str):
    if key in event:
        return event.get(key)
    details = event.get("details")
    if isinstance(details, dict) and key in details:
        return details.get(key)
    return None


def compile_regex_list(values: list, rule_id: str, field: str) -> list:
    patterns = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        try:
            patterns.append(re.compile(raw))
        except re.error:
            print(
                f"collector-forbidden: invalid regex in rule '{rule_id}' for field '{field}': {raw}",
                file=sys.stderr,
            )
    return patterns


def normalize_rules(policy: dict) -> tuple[dict, list[dict]]:
    policy_block = policy.get("policy", {}) if isinstance(policy, dict) else {}
    defaults = policy_block.get("defaults", {}) if isinstance(policy_block, dict) else {}
    rules_raw = policy_block.get("rules", []) if isinstance(policy_block, dict) else []
    rules = []
    for raw in rules_raw:
        if not isinstance(raw, dict):
            continue
        rule_id = raw.get("id")
        if not rule_id:
            continue
        rule = dict(raw)
        rule["_enabled"] = raw.get("enabled", defaults.get("enabled", True))
        rule["_severity"] = raw.get("severity", defaults.get("severity", "medium"))
        rule["_action"] = raw.get("action", defaults.get("action", "alert"))
        event_type_any = normalize_match_spec(raw.get("event_type_any"))
        if not event_type_any and raw.get("event_type"):
            event_type_any = [raw.get("event_type")]
        rule["_event_type_any"] = [str(item) for item in event_type_any if item]
        source_any = normalize_match_spec(raw.get("source_any"))
        if not source_any and raw.get("source"):
            source_any = [raw.get("source")]
        rule["_source_any"] = [str(item) for item in source_any if item]

        match = raw.get("match") if isinstance(raw.get("match"), dict) else {}
        compiled = {}
        comm_any = normalize_match_spec(match.get("comm"))
        if comm_any:
            compiled["comm_any"] = [str(item) for item in comm_any if isinstance(item, (str, int))]
        exe_any = normalize_match_spec(match.get("exe"))
        if exe_any:
            compiled["exe_any"] = [str(item) for item in exe_any if isinstance(item, (str, int))]
        cmd_contains = normalize_match_spec(match.get("cmd_contains"))
        if cmd_contains:
            compiled["cmd_contains"] = [str(item) for item in cmd_contains if isinstance(item, (str, int))]
        cmd_regex = normalize_match_spec(match.get("cmd_regex"))
        if cmd_regex:
            compiled["cmd_regex"] = compile_regex_list(cmd_regex, rule_id, "cmd_regex")
        path_prefix = normalize_match_spec(match.get("path_prefix"))
        if path_prefix:
            compiled["path_prefix"] = [str(item) for item in path_prefix if isinstance(item, (str, int))]
        path_regex = normalize_match_spec(match.get("path_regex"))
        if path_regex:
            compiled["path_regex"] = compile_regex_list(path_regex, rule_id, "path_regex")
        dst_port = normalize_match_spec(match.get("dst_port"))
        if dst_port:
            ports = []
            for item in dst_port:
                try:
                    ports.append(int(item))
                except (TypeError, ValueError):
                    continue
            if ports:
                compiled["dst_port"] = ports
        protocol_any = normalize_match_spec(match.get("protocol"))
        if protocol_any:
            compiled["protocol_any"] = [str(item) for item in protocol_any if isinstance(item, (str, int))]
        dns_suffix = normalize_match_spec(match.get("dns_suffix"))
        if dns_suffix:
            compiled["dns_suffix"] = [str(item).lower() for item in dns_suffix if isinstance(item, (str, int))]
        dns_regex = normalize_match_spec(match.get("dns_regex"))
        if dns_regex:
            compiled["dns_regex"] = compile_regex_list(dns_regex, rule_id, "dns_regex")
        dst_ip = normalize_match_spec(match.get("dst_ip"))
        if dst_ip:
            compiled["dst_ip_any"] = [str(item) for item in dst_ip if isinstance(item, (str, int))]
        rule["_match"] = compiled
        rules.append(rule)

    return policy_block, rules


def match_any(value, options) -> tuple[bool, str | None]:
    if value is None:
        return False, None
    for opt in options:
        if value == opt:
            return True, opt
    return False, None


def match_contains(value, options) -> tuple[bool, str | None]:
    if not isinstance(value, str):
        return False, None
    for opt in options:
        opt_str = str(opt)
        if opt_str and opt_str in value:
            return True, opt_str
    return False, None


def match_regex(value, patterns: list[re.Pattern]) -> tuple[bool, str | None]:
    if not isinstance(value, str):
        return False, None
    for pattern in patterns:
        if pattern.search(value):
            return True, pattern.pattern
    return False, None


def match_prefix(value, prefixes) -> tuple[bool, str | None]:
    if not isinstance(value, str):
        return False, None
    for prefix in prefixes:
        prefix_str = str(prefix)
        if prefix_str and value.startswith(prefix_str):
            return True, prefix_str
    return False, None


def match_dns_suffix(dns_names, suffixes) -> tuple[bool, tuple[str, str] | None]:
    if not dns_names:
        return False, None
    names = dns_names if isinstance(dns_names, list) else [dns_names]
    for name in names:
        if not isinstance(name, str):
            continue
        name_l = name.lower()
        for suffix in suffixes:
            suffix_l = str(suffix).lower()
            if name_l.endswith(suffix_l):
                return True, (name, suffix)
    return False, None


def match_rule(rule: dict, event: dict) -> tuple[bool, list[dict]]:
    if not rule.get("_enabled", True):
        return False, []

    event_type = event.get("event_type")
    if rule.get("_event_type_any") and event_type not in rule.get("_event_type_any"):
        return False, []

    source = event.get("source")
    if rule.get("_source_any") and source not in rule.get("_source_any"):
        return False, []

    matched_fields: list[dict] = []
    match_spec = rule.get("_match", {})

    if "comm_any" in match_spec:
        value = event_get(event, "comm")
        ok, matched = match_any(value, match_spec["comm_any"])
        if not ok:
            return False, []
        matched_fields.append({"field": "comm", "value": value, "pattern": matched})

    if "exe_any" in match_spec:
        value = event_get(event, "exe")
        ok, matched = match_any(value, match_spec["exe_any"])
        if not ok:
            return False, []
        matched_fields.append({"field": "exe", "value": value, "pattern": matched})

    if "cmd_contains" in match_spec:
        value = event_get(event, "cmd")
        ok, matched = match_contains(value, match_spec["cmd_contains"])
        if not ok:
            return False, []
        matched_fields.append({"field": "cmd", "value": value, "pattern": matched})

    if "cmd_regex" in match_spec:
        value = event_get(event, "cmd")
        ok, matched = match_regex(value, match_spec["cmd_regex"])
        if not ok:
            return False, []
        matched_fields.append({"field": "cmd", "value": value, "pattern": matched})

    if "path_prefix" in match_spec:
        value = event_get(event, "path")
        ok, matched = match_prefix(value, match_spec["path_prefix"])
        if not ok:
            return False, []
        matched_fields.append({"field": "path", "value": value, "pattern": matched})

    if "path_regex" in match_spec:
        value = event_get(event, "path")
        ok, matched = match_regex(value, match_spec["path_regex"])
        if not ok:
            return False, []
        matched_fields.append({"field": "path", "value": value, "pattern": matched})

    if "dst_port" in match_spec:
        value = event_get(event, "dst_port")
        try:
            port = int(value)
        except (TypeError, ValueError):
            return False, []
        ok, matched = match_any(port, match_spec["dst_port"])
        if not ok:
            return False, []
        matched_fields.append({"field": "dst_port", "value": port, "pattern": matched})

    if "protocol_any" in match_spec:
        value = event_get(event, "protocol")
        ok, matched = match_any(value, match_spec["protocol_any"])
        if not ok:
            return False, []
        matched_fields.append({"field": "protocol", "value": value, "pattern": matched})

    if "dns_suffix" in match_spec:
        dns_names = event_get(event, "dns_names")
        ok, match_info = match_dns_suffix(dns_names, match_spec["dns_suffix"])
        if not ok:
            return False, []
        name, suffix = match_info
        matched_fields.append({"field": "dns_names", "value": name, "pattern": suffix})

    if "dns_regex" in match_spec:
        dns_names = event_get(event, "dns_names")
        names = dns_names if isinstance(dns_names, list) else [dns_names]
        matched = None
        for name in names:
            ok, pattern = match_regex(name, match_spec["dns_regex"])
            if ok:
                matched = (name, pattern)
                break
        if not matched:
            return False, []
        matched_fields.append({"field": "dns_names", "value": matched[0], "pattern": matched[1]})

    if "dst_ip_any" in match_spec:
        value = event_get(event, "dst_ip")
        ok, matched = match_any(value, match_spec["dst_ip_any"])
        if not ok:
            return False, []
        matched_fields.append({"field": "dst_ip", "value": value, "pattern": matched})

    return True, matched_fields


def build_subject(event: dict) -> str:
    event_type = event.get("event_type") or ""
    if event_type == "exec":
        return (
            event_get(event, "cmd")
            or event_get(event, "exec_attempted_path")
            or event_get(event, "exe")
            or event_get(event, "comm")
            or "exec"
        )
    if event_type.startswith("fs_"):
        return (
            event_get(event, "path")
            or event_get(event, "cmd")
            or event_get(event, "exe")
            or "filesystem"
        )
    if event_type == "net_summary":
        dns_names = event_get(event, "dns_names")
        if isinstance(dns_names, list) and dns_names:
            return ", ".join([str(name) for name in dns_names])
        if isinstance(dns_names, str) and dns_names:
            return dns_names
        dst_ip = event_get(event, "dst_ip")
        dst_port = event_get(event, "dst_port")
        if dst_ip and dst_port:
            return f"{dst_ip}:{dst_port}"
        if dst_ip:
            return str(dst_ip)
        return "network"
    return event_type or "event"


def build_alert(event: dict, rule: dict, matched_fields: list[dict], policy_name: str | None) -> dict:
    alert = {
        "schema_version": "forbidden.alert.v1",
        "session_id": event.get("session_id", "unknown"),
        "ts": event.get("ts"),
        "source": "policy",
        "event_type": "alert",
        "rule_id": rule.get("id"),
        "rule_description": rule.get("description"),
        "severity": rule.get("_severity"),
        "action": rule.get("_action"),
        "trigger_source": event.get("source"),
        "trigger_event_type": event.get("event_type"),
        "trigger_subject": build_subject(event),
        "matched": matched_fields,
    }
    if policy_name:
        alert["policy_name"] = policy_name
    for key in ("job_id", "pid", "ppid", "uid", "gid", "comm", "exe"):
        if key in event:
            alert[key] = event.get(key)
    return alert


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    policy_path = cfg.get("policy") or cfg.get("policy_path")
    if not policy_path:
        print("collector-forbidden: missing policy path", file=sys.stderr)
        return 2
    policy = load_policy(policy_path)
    policy_meta, rules = normalize_rules(policy)
    policy_name = policy_meta.get("name") if isinstance(policy_meta, dict) else None

    inputs = cfg.get("inputs", [])
    output_path = cfg.get("output", {}).get("jsonl", "/logs/filtered_alerts.jsonl")
    sort_strategy = cfg.get("sorting", {}).get("strategy", "ts_rule_pid")

    alerts: list[dict] = []

    for entry in inputs:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not path or not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if not event.get("ts"):
                    continue
                for rule in rules:
                    ok, matched_fields = match_rule(rule, event)
                    if not ok:
                        continue
                    alert = build_alert(event, rule, matched_fields, policy_name)
                    alerts.append(alert)

    if sort_strategy == "ts_rule_pid":
        alerts.sort(
            key=lambda item: (
                parse_ts(item.get("ts")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
                item.get("rule_id") or "",
                item.get("pid") or 0,
            )
        )
    else:
        alerts.sort(key=lambda item: parse_ts(item.get("ts")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as writer:
        for alert in alerts:
            writer.write(json.dumps(alert, separators=(",", ":")) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
