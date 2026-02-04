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
│  ├─ TESTING.md — filter test cases and expected outcomes
│  └─ EXAMPLE_FLOW.md — end-to-end example walkthroughs
├─ history/
│  ├─ HISTORY.md — narrative history and decisions
│  └─ dev_log.md — implementation log
├─ scratch/
│  └─ scratch_notes.md — working notes
└─ Components (in repo root)
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
```
