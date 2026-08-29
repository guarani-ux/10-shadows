# 10 SHADOWS

> **Deterministic Relational Architecture, Sovereign Trusted Kernel, and Epistemic Operating System.**

---

## 1. System Overview

**10 SHADOWS** is a zero-trust autonomous cognitive compiler and execution operating system designed to prevent model-driven epistemic drift, semantic laundering, ungrounded self-certification, and accidental destructive mutation.

The system is split into two non-overlapping authorities:

1. **The Sovereign Rust Trusted Kernel (`crates/ten_shadows_kernel`)**:
   A mathematically strict, typestate-enforced execution and custody arbiter. It owns run creation, baseline capture, ephemeral Git worktree isolation, cryptographically bound worker dispatch, independent verification receipts, and atomic promotion to authoritative branches.
2. **The Epistemic Relational Substrate (`loop_engine`, `Forge`, `svris`, `zero_trust_engine`)**:
   The domain and cognitive execution layer responsible for goal decomposition, relational graph planning, bounded domain routing (Forge, Scribe, Herald, Scout, Inquisitor, Slicer, Warden, Alchemist, Game Master), and just-in-time truth maintenance (JTMS).

---

## 2. Governing Substrate Invariants

| Law | Principle | Physical Mechanism |
| :--- | :--- | :--- |
| **Law 1** | **Sandbox & Ring-Fenced Boundary** | Subprocess execution runs exclusively inside ephemeral Git worktrees with sterile environment variables (`env={...}`). |
| **Law 2** | **Human Authorization Gate** | Material destructive actions require an explicit unbypassable confirmation token. |
| **Law 3** | **Independence of Verification** | Proposers and builders cannot self-certify (`builder_id != verifier_id`). Verification is conducted by independent verifiers against physical AST and execution gates. |
| **Law 4** | **Epistemic Monotonicity** | Typed metadata is not authoritative semantic evidence. Synthetic outputs cannot upgrade epistemic status without empirical or structural verification. |
| **Law 5** | **Three-Strike Governor** | Any loop exceeding 3 failed attempts forcefully halts, rolls back the ephemeral worktree, and triggers Root Cause Architecture Assessment. |
| **Law 6** | **Contract-Driven Sufficiency** | Objectives require versioned contracts, ground truth obligations, tested effects, and monotonic truth maintenance (JTMS) before claiming accomplishment. |

---

## 3. Directory & State Topology

```
10 SHADOWS/
├── Cargo.toml                     # Root Rust workspace definition
├── pyproject.toml                 # Canonical Python package manifest, pytest & ruff configs
├── requirements.txt               # Base runtime dependencies
├── requirements-dev.txt           # Development and verification toolchain
├── pytest.ini                     # Pytest runner configuration
│
├── crates/                        # Sovereign Rust Kernel
│   └── ten_shadows_kernel/        # Typestate state machine, SQLite WAL journal, and CLI (ts)
│
├── loop_engine/                   # Epistemic Operating System & Runtime Engine
│   ├── config.py                  # Centralized path, limit, and configuration management
│   ├── errors.py                  # Typed error and failure classification taxonomy
│   ├── observability.py           # Structured JSON event logging and telemetry
│   ├── constitution/              # Objective contracts, evidence entailment, JTMS sufficiency
│   ├── dispatcher/                # Language-neutral worker dispatch protocol
│   ├── relational/                # Knowledge graph, dependency scheduler, and gap planner
│   └── harness/                   # Ephemeral Git worktree sandbox management
│
├── Forge/                         # Shadow 1: Autonomous Code Synthesis Engine
├── svris/                         # Shadow 2: Verification, Extraction, & State Normalization
├── zero_trust_engine/             # Shadow 8/Warden: Adversarial Plan Auditing Gate
│
├── scripts/                       # Standardized Quality & Verification Scripts
│   ├── preflight.py               # Deterministic environment & health preflight check
│   ├── check_fast.py              # Fast-tier linter, clippy, and unit test runner
│   ├── check_full.py              # Full qualification pipeline runner
│   ├── check-fast.sh / .ps1       # Platform shell wrappers
│   └── check-full.sh / .ps1       # Platform shell wrappers
│
├── tests/                         # Integrated & Adversarial Test Suites
│   ├── test_architectural_fitness.py # Structural fitness and boundary invariant checks
│   ├── test_constitutional_foundation.py # Law 6 epistemic sufficiency tests
│   └── fixtures/                  # Authoritative static test receipts and specs
│
├── scratch/                       # Untracked ephemeral runtime data (WAL databases, staging)
└── .receipts/                     # Untracked physical cryptographic run receipts
```

---

---

## 4. Mandatory Sovereign Execution Entrypoint (`ts run`)

> [!IMPORTANT]
> **Canonical Invariant: NO VALID KERNEL-ISSUED EXECUTION RECEIPT = TEN SHADOWS DID NOT EXECUTE.**
>
> The builder/model is never responsible for deciding whether Ten Shadows is used.
> For governed objectives, the ONLY supported sovereign entrypoint is:
>
> ```bash
> python ts_run.py run "<objective>" [options]
> # Or binary alias:
> ts run "<objective>" [options]
> ```
>
> Direct invocation of `Forge`, `Gemini`, `Antigravity`, raw worker scripts, or verifier scripts does **NOT** constitute Ten Shadows execution. Claims of success, qualification, or capability acquisition are authoritative **only** when sealed and verified by the sovereign kernel receipt.

### CLI Usage & Options

```bash
# Execute an objective through the Ten Shadows Kernel
python ts_run.py run "Create a Python function that converts Celsius to Fahrenheit and verify it against independently specified examples."

# Execute an objective from a file
python ts_run.py run --file objective.md --target ./my_project

# Verify cryptographic authenticity of an execution receipt
python ts_run.py verify .receipts/run_task_20260829_065413_6453956_receipt.json

# Query persistent capability registry
python ts_run.py capabilities list --status QUALIFIED
```

---

## 5. Quickstart & Developer Toolchain

### Prerequisites
* **Python**: `3.10` or higher (`3.13` recommended)
* **Rust**: `stable` (with `cargo`, `rustfmt`, and `clippy`)
* **Git**: `2.30` or higher

### Environment Preflight Check
Run the deterministic preflight check to verify that all compilers, runtimes, and storage paths are operational:

```bash
python scripts/preflight.py
```

### Fast Check (Iterative Development)
Runs Python linting (Ruff), formatting checks, Rust formatting (`rustfmt`), Rust clippy, Rust unit/adversarial tests, and core epistemic tests:

```bash
python scripts/check_fast.py
# Or via shell wrapper:
./scripts/check-fast.sh       # Linux / macOS
.\scripts\check-fast.ps1      # Windows PowerShell
```

### Full Qualification (Pre-Commit / Pre-Promotion)
Runs the complete battery including preflight checks, full clippy with warnings denied, the entire Rust kernel test suite (25 adversarial tests), the complete Python pytest suite, and git working directory cleanliness validation:

```bash
python scripts/check_full.py
# Or via shell wrapper:
./scripts/check-full.sh       # Linux / macOS
.\scripts\check-full.ps1      # Windows PowerShell
```

---

## 5. Continuous Integration (CI)

GitHub Actions runs the unified CI workflow on every push and pull request (`.github/workflows/ci.yml`), enforcing:
* Code style & linting gates (`ruff`, `rustfmt`, `clippy -D warnings`)
* Sovereign kernel build & adversarial authority tests
* Deterministic preflight execution
* Full 500+ unit, integration, and property test battery
* Post-test working directory cleanliness (zero leaked untracked artifacts)

---

## 6. License & Custody

Strict internal custody under the **10 SHADOWS** sovereign protocol.
