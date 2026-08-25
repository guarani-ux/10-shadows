# Synthesis Plan: Konohagakure (Konoha 0.1.0)

## System Overview
**Konohagakure (`konoha`)** is a local, deterministic, evidence-preserving decision and outcome journal designed to evaluate proposals/work under uncertainty.

## Architectural Breakdown

### 1. Data Pipeline & Domain Boundaries (`konoha/models.py`)
* **Strict Evidence Classification**: `EvidenceStatus` Enum (`VERIFIED`, `INFERRED`, `HYPOTHESIS`, `UNKNOWN`, `CONTRADICTED`).
* **Decision States**: `AssessmentDecision` (`pursue`, `decline`, `clarify`, `defer`).
* **Outcome Tracking**: `OutcomeStatus` (`not_yet_due`, `collected`, `invoiced`, `lost`, `declined`, `no_response`, `completed`, `harmed`, `unknown`).
* **Immutability & Safety**: Frozen slotted dataclasses (`Observation`, `Policy`, `CaseInput`, `Assessment`, `DecisionCase`, `Outcome`), non-negative `Decimal` parsing for monetary attributes.

### 2. Pure Deterministic Policy (`konoha/policy.py`)
* Pure evaluation function: `evaluate(case_input: CaseInput, policy: Policy) -> Assessment`.
* Non-probabilistic gate chain:
  1. Risk Marker Exclusion (e.g. `unpaid`).
  2. Operator Availability gate.
  3. Capability requirements vs available capabilities.
  4. Decision-relevant unknowns check (triggers `clarify`).
  5. Minimum value threshold check.

### 3. Ledger & Cryptographic Verification (`konoha/storage.py`)
* **SQLite WAL Engine**: `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 5000`, `PRAGMA journal_mode = WAL`.
* **Content Addressing**: Retains raw source blobs in `source_documents` keyed by SHA-256 digest.
* **Hash Chaining**: `journal_events` table enforces an append-only linear hash chain linking each event to the `previous_hash`, sequence number, and canonical JSON payload digest.
* **Optimistic Concurrency Control**: Revisions incremented on outcome updates (`revision = revision + 1 WHERE case_id = ? AND revision = ?`), aborting causal collisions.
* **Audit & Replay**: `verify_journal()` recalculates source blob digests and linear event hash integrity.

### 4. Application Boundary & CLI (`konoha/service.py`, `konoha/cli.py`)
* **Service Coordinator**: `DecisionService` orchestrates raw source storage, policy evaluation, and event append operations within ACID transactions.
* **CLI Interface**: Subcommands for `analyze`, `outcome`, `show`, `list`, and `ledger-verify`.

### 5. Verification Harness (`tests/test_konoha.py`)
* Full standard-library integration test suite covering end-to-end analysis, outcome logging, stale revision conflict rejection, and source tampering detection.

---

## State Assessment & Invariant Health
* **Strengths**: Zero external runtime dependencies (Python standard library only), explicit transactional boundaries, deterministic policy evaluation, robust hash verification.
* **Opportunities / Next Vectors**:
  - Integration with automated ingestion channels.
  - Multi-policy comparative analysis.
  - Exporting cryptographic proof receipts or audit logs.
