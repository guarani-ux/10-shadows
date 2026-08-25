# The Konoha Legacy Extraction & The 10 SHADOWS Greenfield Blueprint

## 1. Executive Forensic Synthesis

Konoha was built as a minimalist, deterministic verification engine designed to address the **Epistemic Drift & Agency Problem** under uncertainty. It enforces strict separation between:
1. **Raw Ground Truth** (immutable content-addressed bytes)
2. **Subjective Assertions** (categorized by epistemic confidence)
3. **Policy Recommendation** (pure deterministic logic)
4. **Authorized Decisions** (human/agent decision gates)
5. **Durable Outcomes** (optimistically locked economic/state events)
6. **Integrity Ledger** (tamper-evident SHA-256 hash chaining)

---

## 2. Core Architectural Mechanics of Konoha

```
[Raw Source Bytes] ──► SHA-256 Content-Addressed Blob Storage
                              │
                              ▼
                      [Observation Layer]
                (VERIFIED / INFERRED / UNKNOWN)
                              │
                              ▼
                  [Deterministic Policy Gate]
                   ├── Risk Marker Hard Reject
                   ├── Operator Availability Gate
                   ├── Required vs Available Capabilities
                   └── Unknowns Short-Circuit (Forces 'clarify')
                              │
                              ▼
                     [Decision Execution]
                              │
                              ▼
                     [SQLite WAL Ledger]
          (Hash-Chained Journal + Revision CAS Concurrency)
```

---

## 3. High-Truth Invariants (What 10 SHADOWS Must Retain)

1. **Content-Addressed Immutability**:
   - Never store arbitrary unverified state. All input documents and payloads must be hashed via SHA-256 upon entry.
2. **First-Class Unknowns**:
   - Unknowns are not zeroes, nulls, or default fallbacks. If critical data is missing, the system must immediately halt/circuit-break (`clarify`) rather than hallucinate or assume.
3. **Causal Optimistic Concurrency**:
   - State cannot mutate without an explicit revision match (`WHERE case_id = ? AND revision = expected_revision`). Causal collisions must fail immediately and loudly.
4. **Separation of Policy and Authority**:
   - The policy engine suggests; an authorized entity (operator/governor agent) commits.
5. **Linear Event Verification**:
   - Replayability is proof. State is valid if and only if the event sequence hashes reproduce the identical final state digest.

---

## 4. Architectural Deficits in Konoha (What 10 SHADOWS Must Evolve)

| Dimension | Konoha 0.1.0 (Legacy) | 10 SHADOWS (Target Architecture) |
| :--- | :--- | :--- |
| **Agent Topology** | Single human-in-the-loop CLI operator. No agent swarm abstraction. | Multi-agent autonomous swarm (Scavenger, Compiler, Sentry, Arbiter) operating within ring-fenced boundaries. |
| **State Machine** | Single-hop transition: `DECIDED (rev 0)` $\rightarrow$ `CLOSED (rev 1)`. | Multi-stage dynamic state machine (Staging $\rightarrow$ Fuzzing $\rightarrow$ AST Verification $\rightarrow$ Ledger Commit $\rightarrow$ Settlement). |
| **Policy Engine** | Static Python hardcoded rules (`policy.py`). | Dynamic, composable rule DSL compiled to AST invariants. |
| **Ledger Architecture** | Global SQLite linear chain (single point of contention). | Merkle-tree event DAG with partitionable agent shards and independent case trees. |
| **Input Processing** | Manual text file reading (`source.txt`). | Automated multi-modal ingestion pipelines with automated epistemic classification. |

---

## 5. Greenfield 10 SHADOWS System Architecture

10 SHADOWS takes the epistemic physics of Konoha and scales them into an autonomous cognitive OS:

```
                          ┌──────────────────────────┐
                          │    10 SHADOWS RUNTIME    │
                          └────────────┬─────────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 ▼                     ▼                     ▼
        ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
        │ SCAVENGER AGENT │   │ COMPILER AGENT  │   │  SENTRY AGENT   │
        │ (Ingestion &    │   │ (AST & Policy   │   │ (Ledger Physics │
        │ Epistemology)   │   │ Synthesis)      │   │ & Verification) │
        └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
                 │                     │                     │
                 └─────────────────────┼─────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │      STATE MACHINE KERNEL     │
                       │   - Write-Ahead Log (WAL)     │
                       │   - Merkle Event DAG          │
                       │   - 3-Strike Abort Governor   │
                       └───────────────────────────────┘
```
