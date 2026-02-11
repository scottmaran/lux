# Documentation Map

```
docs/README.md (you are here)
├─ guide/
│  ├─ install.md — installer + manual install steps
│  ├─ cli.md — CLI commands and behavior
│  └─ config.md — config.yaml reference and defaults
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
│  ├─ DEVELOPING.md — manual compose + component runs (legacy/advanced)
│  ├─ TESTING.md — testing quickstart and links to canonical test docs
│  └─ EXAMPLE_FLOW.md — illustrative end-to-end walkthrough (non-normative)
├─ history/
│  ├─ HISTORY.md — narrative history and decisions
│  └─ dev_log.md — implementation log
├─ scratch/
│  └─ scratch_notes.md — working notes
├─ Components (in repo root)
   ├─ agent/README.md — agent container setup
   ├─ harness/README.md — harness behavior and config
   ├─ collector/README.md — collector setup and pipeline
   │  ├─ collector/auditd_data.md — audit log schema
   │  ├─ collector/eBPF_data.md — eBPF log schema
   │  ├─ collector/timeline_data.md — merged timeline schema
   │  └─ collector/config/filtering_rules.md — filtering rules
   ├─ ui/README.md — UI build/run notes
   ├─ ui/src/Attributions.md — asset attributions
   └─ lasso/ — Rust CLI source (release bundles ship the binary only)
└─ Testing Docs (in `tests/`)
   ├─ tests/README.md — canonical testing contract and runnable commands
   ├─ tests/test_principles.md — concise test invariants
   ├─ tests/SYNTHETIC_LOGS.md — synthetic-data fidelity guidance
   └─ tests/testing_prompt.md — implementation contract for test-suite subagents
```
