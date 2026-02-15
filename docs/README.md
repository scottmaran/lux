# Documentation Map

```
docs/README.md (you are here)
├─ guide/
│  ├─ install.md — installer + manual install steps
│  ├─ cli.md — CLI commands and behavior
│  ├─ config.md — config.yaml reference and defaults
│  └─ log_layout.md — run-scoped log directory structure
├─ agent_classes/
│  ├─ brainstorm.md — brainstorm options + recommendation
│  ├─ create_spec.md — write an implementable spec
│  ├─ implement_spec.md — implement an existing spec with tests
│  ├─ audit.md — review/audit the codebase (read-only)
│  ├─ explain.md — explain current behavior accurately
│  └─ one_off.md — small, bounded fixes/changes
├─ specs/
│  ├─ README.md — how to write specs
│  └─ TEMPLATE.md — spec template
├─ audits/
│  ├─ README.md — how to write audits
│  └─ TEMPLATE.md — audit template
├─ orientation/
│  ├─ overview.md — system summary and goals
│  ├─ platform.md — platform assumptions and constraints
│  └─ kernel_auditing_info.md — kernel audit/eBPF notes
├─ vm/
│  ├─ docker_desktop_vm.md — Docker Desktop VM behavior
│  └─ lasso_vm_layout.md — VM/container layout
├─ ui/
│  ├─ UI_DESIGN.md — UI behavior and layout
│  └─ UI_API.md — UI API contract
├─ dev/
│  ├─ DEVELOPING.md — manual compose + component runs (advanced)
│  └─ EXAMPLE_FLOW.md — illustrative end-to-end walkthrough (non-normative)
├─ history/
│  ├─ HISTORY.md — narrative history and decisions
│  └─ dev_log.md — implementation log
├─ Components (in repo root)
   ├─ agent/README.md — agent container setup
   │  └─ agent/provider_auth.md — provider auth bootstrap details
   ├─ harness/README.md — harness behavior and config
   │  ├─ harness/api.md — harness server-mode API contract
   │  └─ harness/artifacts.md — harness session/job artifacts contract
   ├─ collector/README.md — collector setup and pipeline
   │  ├─ collector/auditd_raw_data.md — raw audit.log format
   │  ├─ collector/auditd_filtered_data.md — filtered audit JSONL schema
   │  ├─ collector/ebpf_raw_data.md — raw eBPF JSONL schema
   │  ├─ collector/ebpf_filtered_data.md — filtered eBPF JSONL schema
   │  ├─ collector/ebpf_summary_data.md — eBPF summary JSONL schema
   │  ├─ collector/timeline_filtered_data.md — merged timeline JSONL schema
   │  ├─ collector/ownership_and_attribution.md — attribution semantics
   │  └─ collector/config/README.md — collector config map
   ├─ ui/README.md — UI build/run notes
   ├─ ui/src/Attributions.md — asset attributions
   └─ lasso/ — Rust CLI source (release bundles ship the binary only)
└─ Testing Docs (in `tests/`)
   ├─ tests/README.md — canonical testing contract and runnable commands
   ├─ tests/test_principles.md — concise test invariants
   ├─ tests/SYNTHETIC_LOGS.md — synthetic-data fidelity guidance
   └─ tests/testing_prompt.md — implementation contract for test-suite subagents
```
