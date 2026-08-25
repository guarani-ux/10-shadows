# 10 SHADOWS: Master Architecture & Loop Engine Implementation Plan

## 1. Executive Context & System Purpose

`10 SHADOWS` is a **Zero-Trust Autonomous Execution Runtime** built on deterministic verification physics. It extracts the proven mechanisms from past projects (`Dominion`, `Espada`, `Mugen`, `Konoha`) and consolidates them into a unified, crash-safe engine that turns high-level intent into verified reality without trusting raw model claims.

### Core System Principles:
1. **The Human Apex:** The Architect designs constraints, physics, and intent; the system handles execution, testing, and verification.
2. **Deterministic Physics over Soft Prompts:** Hard AST gates, process timeouts, and compiler tests replace "please be accurate" prompting.
3. **No Direct Production Writes:** All mutations occur in ephemeral, ring-fenced staging directories and commit atomically (`os.replace`) only upon passing all verification gates.
4. **Irreducible 3-Strike Boundary:** Failed runs retry with cumulative negative constraint memory; three consecutive failures trigger a hard abort and emit a forensic audit receipt.

---

## 2. The 10 Domain Shadows (Target Architecture)

The system organizes its capabilities into 10 specialized domain runners powered by the common loop runtime:

| Shadow Name | Functional Descriptor | Primary Responsibility |
| :--- | :--- | :--- |
| **1. The Forge** | Software & Tool Builder | Generates, modifies, and tests Python tools in isolated staging buffers. |
| **2. svris** | Verification & Receipts | Evaluates AST syntax, import safety, quote spans, and emits machine-signed receipts. |
| **3. The Herald** | Document & Media Engine | Generates DDL-compliant Call Sheets, CPL templates, and client-facing docx deliverables. |
| **4. The Scout** | Recon & Deep Research | Ingests web/file data and extracts grounded facts with provenance verification. |
| **5. The Inquisitor** | Adversarial Tribunal | Spawns opposed Red/Blue subagents to stress-test designs and plans before coding. |
| **6. The Scribe** | Knowledge Graph & Memory | Compiles documents, notes, and schemas into queryable graph relationships. |
| **7. The Slicer** | Task & DAG Decomposer | Breaks large goals into minimal, 5–15 minute irreducible vertical slices. |
| **8. The Warden** | Security & Vault Isolation | Enforces `env={}` subprocess scrubbing, path jail boundaries, and file locks. |
| **9. The Alchemist** | Self-Healing & System Repair | Diagnoses broken plugin hooks, repairs syntax errors, and maintains runtime health. |
| **10. The Game Master** | Sovereign State Projection | Projects system health, task queues, and execution metrics into a gamified HUD. |

---

## 3. The 10-Dimension Adversarial Audit Standard

All plans and vertical slices are audited against the 10 failure dimensions defined in [`adversarial-plan-auditor`](file:///c:/10%20SHADOWS/.agents/skills/adversarial-plan-auditor/SKILL.md):

1. **OS & Filesystem:** Windows `WinError 32` handle closures, absolute `PROJECT_ROOT` path anchoring, `.as_posix()` escaping, read-only cleanup.
2. **Subprocess & Environment:** `sys.executable` binding, `PYTHONPATH` injection, `stdin=subprocess.DEVNULL`, hard 5s process timeouts.
3. **State Integrity:** Canonical SHA-256 `spec_hash`, unique run namespaces, atomic 2PC file swaps.
4. **Anti-Oscillation & Context:** Cumulative negative constraint ledgers, 500-token error trace compaction.
5. **Network & API Resilience:** Exponential backoff for 429/5xx errors, network failure strike immunity.
6. **Parsing & AST Security:** Deterministic markdown fence stripping, AST dynamic call bans (`eval`/`exec`).
7. **Test Oracle Integrity:** Non-vacuous assertion validation, deterministic seed isolation.
8. **Signal Handling:** Clean `SIGINT` / `Ctrl+C` subprocess tree termination.
9. **Quotas & Retention:** TTL pruning for old staging runs and forensic logs.
10. **Economic Governance:** Irreducible 3-strike ceiling, hard financial spend caps.

---

## 4. Vertical Slice Implementation Roadmap (`loop_engine/`)

```
c:\10 SHADOWS\loop_engine\
├── __init__.py                               # Package exports
├── base.py                                   # BaseLoop abstract runtime
├── extractor.py                              # Markdown fence stripper & path jail
├── preflight.py                              # Phase 0 pre-flight admission probes
├── governor.py                               # 3-Strike retry & negative constraint memory
├── receipts.py                               # SQLite WAL receipt & event logger
├── verifiers/
│   ├── ast_gate.py                           # AST static security & syntax parser
│   └── test_gate.py                          # Subprocess pytest runner with timeouts
└── tests/
    ├── test_slice_1_hollow_pipe.py           # [COMPLETE]
    ├── test_slice_2_preflight_and_tamper.py  # [NEXT]
    ├── test_slice_3_retry_and_abort.py       # [PLANNED]
    ├── test_slice_4_ast_security.py          # [PLANNED]
    ├── test_slice_5_isolated_execution.py    # [PLANNED]
    └── test_slice_6_atomic_commit.py         # [PLANNED]
```

---

### Slice Status & Detailed Roadmap

#### ✅ Slice 1: The Hollow Pipe & Markdown Extractor (Status: BUILT)
* **Components:** [`loop_engine/base.py`](file:///c:/10%20SHADOWS/loop_engine/base.py), [`loop_engine/extractor.py`](file:///c:/10%20SHADOWS/loop_engine/extractor.py)
* **Capabilities:**
  * Base abstract class with explicit `PROJECT_ROOT` anchoring and `STAGING_ROOT` isolation.
  * Windows `force_remove_readonly` cleanup handler.
  * Deterministic markdown fence stripper with directory traversal security.
* **Test File:** [`loop_engine/tests/test_slice_1_hollow_pipe.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_1_hollow_pipe.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_1_hollow_pipe.py -v
  ```

---

#### ✅ Slice 2: Pre-Flight Admission & Canonical Spec Sealing (Status: BUILT)
* **Components:** [`loop_engine/preflight.py`](file:///c:/10%20SHADOWS/loop_engine/preflight.py)
* **Capabilities:**
  * `run_pre_flight()`: Validates required Python modules via `importlib.util.find_spec` and verifies disk write permissions before allocation.
  * Canonical SHA-256 `spec_hash`: Sorts all dictionary keys and acceptance criteria to seal task definitions deterministically.
  * `SpecTamperError`: Rejects retry attempts if the worker mutates objectives or constraints mid-loop.
* **Test File:** [`loop_engine/tests/test_slice_2_preflight_and_tamper.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_2_preflight_and_tamper.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_2_preflight_and_tamper.py -v
  ```

---

#### ✅ Slice 3: The 3-Strike Governor & Anti-Oscillation Memory (Status: BUILT)
* **Components:** [`loop_engine/governor.py`](file:///c:/10%20SHADOWS/loop_engine/governor.py)
* **Capabilities:**
  * While loop bounded by `max_strikes = 3`.
  * Cumulative `negative_constraints_ledger` tracking root-cause error signatures across attempts.
  * Context compaction: Error feedback capped at 25 lines to prevent token explosion.
  * Hard abort with forensic error trace if Strike 3 fails.
* **Test File:** [`loop_engine/tests/test_slice_3_retry_and_abort.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_3_retry_and_abort.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_3_retry_and_abort.py -v
  ```

---

#### ✅ Slice 4: AST Static Security & Syntax Gate (Status: BUILT)
* **Components:** [`loop_engine/verifiers/ast_gate.py`](file:///c:/10%20SHADOWS/loop_engine/verifiers/ast_gate.py)
* **Capabilities:**
  * `ASTSecurityVisitor`: Enforces static bans on `eval()`, `exec()`, `__import__()`, `os.system()`, dynamic module imports, and network modules.
  * Structured syntax parsing and diagnostic violation extraction.
  * Physical file validation via `inspect_file_ast()`.
* **Test File:** [`loop_engine/tests/test_slice_4_ast_security.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_4_ast_security.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_4_ast_security.py -v
  ```

---

#### ✅ Slice 5: Subprocess Isolation Harness (Status: BUILT)
* **Components:** [`loop_engine/verifiers/test_gate.py`](file:///c:/10%20SHADOWS/loop_engine/verifiers/test_gate.py)
* **Capabilities:**
  * `run_isolated_pytest()`: Pytest execution bound strictly to `sys.executable`.
  * `PYTHONPATH` workspace root injection and `stdin=subprocess.DEVNULL` deadlock prevention.
  * Hard execution timeout enforcement with structured failure receipts.
* **Test File:** [`loop_engine/tests/test_slice_5_isolated_execution.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_5_isolated_execution.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_5_isolated_execution.py -v
  ```

---

#### ✅ Slice 6: Atomic Two-Phase Commit & WAL Receipts (Status: BUILT)
* **Components:** [`loop_engine/receipts.py`](file:///c:/10%20SHADOWS/loop_engine/receipts.py)
* **Capabilities:**
  * `atomic_two_phase_commit()`: Two-phase atomic swap with `.bak` preparation and rollback.
  * `ReceiptStore`: SQLite WAL mode receipt logging with execution timestamps and SHA-256 digests.
  * `compute_file_sha256()`: Deterministic artifact integrity validation.
* **Test File:** [`loop_engine/tests/test_slice_6_atomic_commit.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_6_atomic_commit.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_6_atomic_commit.py -v
  ```

---

#### ✅ Slice 7: Real Domain Runner Integration (Status: BUILT)
* **Components:** [`loop_engine/runners/code_runner.py`](file:///c:/10%20SHADOWS/loop_engine/runners/code_runner.py)
* **Capabilities:**
  * Concrete `CodeRunnerLoop` embedding AST static security gate and subprocess pytest gate.
  * Integration with 3-Strike `Governor` and SQLite WAL `ReceiptStore`.
  * Physical verification of AST bans and isolated test suites.
* **Test File:** [`loop_engine/tests/test_slice_7_domain_runners.py`](file:///c:/10%20SHADOWS/loop_engine/tests/test_slice_7_domain_runners.py)
* **Verification Command:**
  ```powershell
  python -m pytest loop_engine/tests/test_slice_7_domain_runners.py -v
  ```

---

## 5. Verification & Testing Playbook

```powershell
# Run full loop_engine test suite (36 tests)
python -m pytest loop_engine/tests/ -v
```


