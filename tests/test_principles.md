# Lasso Test Suite

## Philosophy

The test suite is the specification. If a behavior is not tested, it is not
guaranteed. If a test exists, its name and structure describe exactly what is
promised.

**Guiding principles:**

1. **Interpretability.** Any developer or agent can read the test directory
   tree and understand what Lasso guarantees. Test names are precise
   descriptions of behavior, not implementation details.

2. **Determinism.** Every aspect of the test suite is rigorously defined and
   validated. Test inputs follow defined schemas. Test outputs are compared
   against exact expected values. Fixture case directories have a required
   structure enforced by validation. There is no ambiguity about what a test
   expects, what files a fixture case must contain, or what format they must
   follow. If a convention exists, it is enforced by code

---

## Isolation

Every test is isolated. This is enforced structurally.

- **Unit:** in-memory only, no shared state between functions.
- **Fixture:** each case runs in an independent temp directory.
- **Integration:** fresh temp log dir + unique compose project per test.
- **Stress:** independent resources per trial.
- Teardown is unconditional (runs even on failure).
