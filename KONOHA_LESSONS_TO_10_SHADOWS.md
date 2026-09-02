# The Konoha Legacy Extraction & The 10 SHADOWS Greenfield Blueprint

> **Historical design document:** this file records architectural ideas, intended invariants, and target directions extracted from Konoha. It is not a present-tense capability statement for Ten Shadows. Terms such as “autonomous cognitive OS,” “Merkle event DAG,” “multi-agent swarm,” or other target architecture below must not be interpreted as implemented or verified unless `CAPABILITY_GROUND_TRUTH.md` and current executable evidence independently support them.

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

These are design requirements, not automatic proof that the current implementation satisfies them.

1. **Content-Addressed Immutability**:
   - Never store arbitrary unverified state. All input documents and payloads should be hashed via SHA-256 upon entry where the governing route requires immutable provenance.
2. **First-Class Unknowns**:
   - Unknowns are not zeroes, nulls, or default fallbacks. If critical data is missing, the system should halt/circuit-break (`clarify`) rather than silently hallucinate or assume.
3. **Causal Optimistic Concurrency**:
   - Where revision-governed state is used, mutation should require an explicit revision match (`WHERE case_id = ? AND revision = expected_revision`). Causal collisions should fail loudly.
4. **Separation of Policy and Authority**:
   - The policy engine suggests; an authorized entity or mechanically privileged governor commits.
5. **Linear Event Verification**:
   - Where an event ledger is authoritative, replayability should reproduce the same final state digest.

---

## 4. Architectural Deficits in Konoha (What 10 SHADOWS Was Intended to Evolve)

| Dimension | Konoha 0.1.0 (Legacy) | 10 SHADOWS (Historical Target Direction) |
| :--- | :--- | :--- |
| **Agent Topology** | Single human-in-the-loop CLI operator. No agent swarm abstraction. | Multi-agent workers operating within governed boundaries. |
| **State Machine** | Single-hop transition: `DECIDED (rev 0)` → `CLOSED (rev 1)`. | Multi-stage governed execution and verification lifecycle. |
| **Policy Engine** | Static Python hardcoded rules (`policy.py`). | More composable machine-checkable invariants. |
| **Ledger Architecture** | Global SQLite linear chain. | More scalable/tamper-evident event structures were contemplated. |
| **Input Processing** | Manual text file reading (`source.txt`). | Automated ingestion with explicit epistemic classification was contemplated. |

---

## 5. Historical Greenfield 10 SHADOWS Concept

The original blueprint imagined scaling Konoha's epistemic ideas into a broader autonomous cognitive operating environment:

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

This diagram is retained as design provenance only. The reconciled repository must use narrower present-tense language wherever these elements are not actually implemented and verified.
