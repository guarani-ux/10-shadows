# CAPABILITY GROUND TRUTH

This ledger separates present-tense repository capability from architectural intent.

Audit baseline: `master` commit `34fc01643d21d392d1ddb5fbbfc85ebecd0dfb94`, GitHub Actions run #37.

## Status definitions

- **VERIFIED**: current relevant verification evidence passes.
- **IMPLEMENTED**: executable implementation exists; broader claim is not currently proven.
- **EXPERIMENTAL**: executable implementation exists but integration/reliability/scope remains under validation.
- **SCAFFOLDED**: interface or structural implementation exists without a complete demonstrated path.
- **PLANNED**: milestone/specification target, not a completed capability.
- **BLOCKED**: an otherwise implemented path is prevented from completing by a known current failure.

## Current capability ledger

| Capability | Status | Ground truth |
|---|---|---|
| Canonical `ts_run.py` CLI | IMPLEMENTED | `run`, `verify`, and `capabilities list` commands exist and route into current implementation. |
| Governed objective establishment | IMPLEMENTED | Orchestrator establishes kernel run before builder invocation. |
| Bounded attempt loop | IMPLEMENTED | Canonical orchestrator bounds attempts with `max_attempts`. |
| Worker authorization token verification | IMPLEMENTED | Provider paths reject invalid authorization tokens. |
| Filesystem before/after observation | IMPLEMENTED | Orchestrator hashes workspace files and records created/modified/deleted effects. |
| Candidate capability registration | IMPLEMENTED | Candidate capabilities are registered as unqualified before verification. |
| Capability qualification after verification | IMPLEMENTED | Qualification path is invoked only after independent verification passes. |
| Persistent capability lookup/reuse mechanism | IMPLEMENTED / EXPERIMENTAL | Registry lookup is wired into canonical orchestrator; broad usefulness across arbitrary domains is not established. |
| Independent receipt verification command | IMPLEMENTED | `ts_run.py verify` calls receipt verification and fails closed on invalid evidence. |
| Rust trusted-kernel build | VERIFIED in CI #37 | `cargo build --workspace --all-targets` passes. |
| Rust adversarial authority suite | BLOCKED / PARTIAL | 22/25 pass in CI #37; 3 dispatcher tests fail because Python `pydantic` is unavailable in the Rust test job. |
| Full Python ecosystem qualification | NOT CURRENTLY VERIFIED | CI #37 skips this job after the Ruff quality-gate failure. |
| Deterministic general-purpose builder | NOT IMPLEMENTED | Current deterministic provider supports a small explicit set of objective patterns and fails closed otherwise. |
| Deterministic temperature conversion synthesis | IMPLEMENTED | Explicit code/test synthesis path exists. |
| Deterministic hydraulic transient synthesis | IMPLEMENTED | Explicit code/test synthesis path exists. |
| Gemini live builder through canonical provider | SCAFFOLDED | Adapter exists but intentionally returns provider unavailable; live network generation is not enabled in this path. |
| Antigravity worker bridge | EXPERIMENTAL / ENVIRONMENT-DEPENDENT | Adapter requires `ANTIGRAVITY_CLI`; current success path reports completion but does not by itself establish broad task execution. |
| Fully integrated Scribe -> Herald -> Slicer shared-kernel route | PLANNED / IN PROGRESS | Explicitly identified as Milestone A in `CURRENT_OBJECTIVE.md`. |
| General autonomous capability acquisition | NOT VERIFIED | Registry/candidate/qualification mechanisms exist, but arbitrary-domain discovery, synthesis, validation, and reuse are not demonstrated as a general closed loop. |
| Universal autonomous cognitive operating system | NOT VERIFIED | Architectural aspiration exceeds current demonstrated scope. |
| Production readiness | NOT VERIFIED | Current `master` CI is red. |

## Current CI evidence

GitHub Actions run #37 on the audit baseline reports:

- `Code Style & Quality Gates`: failed at Ruff;
- `Rust Trusted Kernel Tests`: build passed, tests failed;
- Rust adversarial suite: 25 collected, 22 passed, 3 failed;
- failing Rust tests: `test_14_worker_dispatch_through_python_dispatcher`, `test_15_repair_loop_multi_attempt_retention`, `test_16_shadow_domain_forge_dispatch`;
- common observed cause for those three failures: Python dispatcher import fails with `ModuleNotFoundError: No module named 'pydantic'`;
- `Python Ecosystem & Epistemic Tests`: skipped because it depends on the failed quality-gate job.

This means failures in run #37 should not automatically be interpreted as proof that the underlying Rust authority semantics are incorrect; three observed failures are currently CI environment/dependency integration failures. They still count as failures until repaired and rerun.

## Known description drift found by this audit

1. The old README called Ten Shadows a `zero-trust autonomous cognitive compiler and execution operating system` without distinguishing aspiration from demonstrated scope.
2. The old README stated that CI enforces a `Full 500+ unit, integration, and property test battery` while the current CI run does not reach the full Python ecosystem suite. The exact current total was therefore not treated as a verified present-tense claim.
3. The old README described Gemini and Antigravity alongside executable system components without making their current canonical-provider limitations clear.
4. `CURRENT_GOAL.md` still described an older Herald-specific AV-script mission while `CURRENT_OBJECTIVE.md` identifies Shared Kernel Closure / Milestone A as the active repository mission.
5. `FAILURE_LEDGER.md` reports zero active receipt failures, while repository CI is red. That file is an automated Game Master projection with a narrower evidence scope and must not be interpreted as repository-wide health status.

## Claim policy

When documentation and implementation disagree, implementation wins.

When implementation and current verification disagree, the claim must stop at **IMPLEMENTED** or **EXPERIMENTAL** rather than **VERIFIED**.

When CI is red, repository-wide descriptions must not imply a fully qualified state.

When a capability is a milestone target, describe it as planned/in progress until its stated gates pass.

This ledger should be updated whenever a change materially alters capability status.
