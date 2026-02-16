# Collector Config (Canonical Docs Live In docs/contracts/)

The shipped collector config files live in this directory:
- `collector/config/*.yaml`
- `collector/config/*.conf`
- `collector/config/rules.d/*`

The canonical documentation for the *semantics* of these configs lives under:
- `docs/contracts/collector_config/README.md`

If you change a shipped config file, update the corresponding contract doc and
tests so the behavior remains explicit and enforced.
