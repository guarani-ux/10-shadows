---
name: adversarial-plan-auditor
description: "Adversarially stress-tests implementation plans across 10 critical systems engineering failure dimensions (OS/filesystem, process isolation, state integrity, anti-oscillation, network resilience, AST security, test oracle quality, signal handling, disk quota, and resource governance) before writing code. Invoked to audit plans or ensure zero unmitigated vulnerabilities."
---

# Adversarial Plan Auditor

This skill enforces a rigorous, 10-dimension pre-build audit on any proposed implementation plan or architecture specification before code generation begins.

## When to Run This Skill

- When the user asks to review, audit, stress-test, or check an implementation plan for hidden failure modes.
- Before executing any complex multi-step build or refactor.

---

## The 10 Failure Dimensions Checklist

When reviewing any plan, evaluate the target code and architecture strictly against these 10 dimensions:

### 1. OS & Filesystem Hazards
- **Windows File Locking (`WinError 32`):** Are file descriptors and database connections wrapped in explicit context managers (`with open(...)`) and closed prior to atomic replacements (`os.replace`)?
- **Path Anchoring:** Are all paths anchored to an explicit, absolute project root rather than relying on current working directory (`cwd`)?
- **Path Escapes:** Are path representations normalized to POSIX format (`.as_posix()`) to prevent backslash escape crashes in JSON or code templates?
- **Read-Only Cleanup:** Does directory removal use an `onerror` handler to clear read-only file bits on Windows?

### 2. Subprocess & Environment Hazards
- **Interpreter Binding:** Are Python and pytest invocations bound to `sys.executable` rather than bare CLI commands?
- **Environment Isolation:** Is `PYTHONPATH` explicitly set to the project root, and are sensitive API keys scrubbed from subprocess environments (`env={}`)?
- **Deadlock & Stdin Protection:** Is `stdin=subprocess.DEVNULL` explicitly set to prevent indefinite hangs on interactive input calls?
- **Hard Process Timeouts:** Is every external execution bounded by a hard OS process group timeout (e.g., 5–30 seconds)?

### 3. State Integrity & Anti-Drift
- **Spec Sealing:** Is the initial task specification canonically hashed via SHA-256 (`spec_hash`) upon entry?
- **Anti-Drift Verification:** Does the verifier evaluate against the immutable `spec_hash` to prevent goalpost-moving during retries?
- **Namespace Isolation:** Does each execution run in a cryptographically unique directory (`run_<task_id>_<uuid>`)?
- **Atomic Two-Phase Commit:** Are state mutations staged in temporary scratchpads and committed via atomic file swaps with rollback backups?

### 4. Anti-Oscillation & Context Compaction
- **Cumulative Negative Constraint Ledger:** Does the retry prompt carry forward all previous failure signatures rather than just the latest error?
- **Context Compaction:** Are error feedback traces strictly capped (e.g., max 20 lines / 500 tokens) to prevent context window overflow?

### 5. Network & API Resilience
- **Transient Failure Separation:** Are HTTP 429 rate limits, 5xx server errors, and network timeouts handled with jittered exponential backoff?
- **Strike Immunity:** Network and infrastructure errors must NOT consume task execution strikes.

### 6. Parsing & Security Guards
- **Markdown Fence Stripping:** Does the ingestion layer deterministically strip markdown fences (```` ```python ````) before passing code to AST parsers or filesystems?
- **AST Security Screening:** Does a static AST visitor inspect candidate code to block forbidden dynamic execution (`eval`, `exec`, `os.system`, raw socket connections)?

### 7. Test Oracle Integrity
- **Non-Vacuous Assertions:** Does the verification gate inspect test files to verify they contain non-trivial `assert` statements?
- **Flakiness Isolation:** Are tests deterministic, independent of system wall-clock timing, and executed with fixed seeds?

### 8. Signal Handling & Interruption
- **Clean Teardown:** Are `SIGINT` (`Ctrl+C`) and `SIGTERM` signals trapped to terminate child process trees and remove temporary locks cleanly?

### 9. Resource Quotas & Garbage Collection
- **TTL / Retention Policy:** Is there an automatic cleanup policy to prune old staging directories and crash logs to prevent disk saturation?

### 10. Economic Governors
- **Irreducible Iteration Cap:** Hard ceiling of maximum 3 strikes before mandatory abort.
- **Financial Spend Cap:** Hard dollar / token budget ceiling per execution loop.

---

## Output Protocol

For every identified defect, format findings strictly as:

```text
[DEFECT NAME]
- Failure Scenario: <Exact condition or line where failure occurs>
- Symptom: <Exact error message or system failure behavior>
- Mandatory Code Fix: <Concrete implementation change required to close the defect>
```

If all 10 dimensions are mathematically and structurally verified in the plan, output:
`PLAN VERIFIED: ZERO UNMITIGATED VULNERABILITIES DETECTED.`
