# Reverse-Engineering Architectural Decomposition: Outer Sanctum

## 1. System Topology Overview
**Outer Sanctum** is a dual-subsystem cognitive manufacturing environment:
1. **`Komorebi` (Adversarial OS & Harness Kernel)**: A gate-enforced, untrusted-model execution harness driven by AST-level red-team/blue-team verification, fuzz corpus logging, and machine-signed mission receipts.
2. **`Sovereign_Media_Engine` (Deterministic Media Factory)**: A DAMA-DMBOK compliant schema-as-truth content production pipeline with cryptographic provenance, strict compatibility matrices, and ffmpeg execution bridges.

```
                           ┌────────────────────────────┐
                           │    OUTER SANCTUM SYSTEM    │
                           └─────────────┬──────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     ┌───────────────────────┐                       ┌───────────────────────┐
     │       KOMOREBI        │                       │ SOVEREIGN MEDIA ENG.  │
     │ (Adversarial Harness) │                       │ (Production Engine)   │
     └───────────┬───────────┘                       └───────────┬───────────┘
                 │                                               │
     ├── harness_coordinator.py (Red/Blue Loop)       ├── definitive_schema.sql (DAMA Truth)
     ├── staging_buffer.py (Proposals)                ├── populate_full_ledger.py (ETL)
     ├── claim_gate.py (Machine Receipts)             ├── compile_video.py (Render Bridge)
     └── fuzz_corpus.db (Crash Payloads)              └── cpl_sovereign_ledger.db (WAL)
```

---

## 2. Formal State Machine & Invariants (Komorebi Harness)

### 2.1 The Red-Team / Blue-Team Adversarial Cycle
```
[HUMAN INTENT] ──► harness_coordinator.py start "<intent>"
                         │
                         ▼
        ┌──────────────────────────────────┐
        │       RED-TEAM DISPATCH          │
        │ Generates adversarial tests.py   │
        └────────────────┬─────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │       BLUE-TEAM DISPATCH         │
        │ Proposes logic into staging_     │
        │ buffer.py / candidate.py         │
        └────────────────┬─────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │        COLOSSEUM ADJUDICATION    │
        │ - AST Anti-Cheat Gate (aci.py)   │
        │ - Subprocess in Isolated Sandbox │
        │ - Max 3-Strike Loop              │
        └────────────────┬─────────────────┘
                         │
           [PASS?] ──────┴──────► [FAIL (>=3 Strikes)]
              │                          │
              ▼                          ▼
   [claim_gate.py Emit Receipt]   [ABORT SWARM / PURGE]
```

### 2.2 Invariant Physics:
1. **Receipt Doctrine**: A claim is `NOT ENFORCED YET` unless backed by:
   $$\text{Truth} = \text{Path} \land \text{Command} \land \text{Pass Output} \land \text{Fail Output}$$
2. **AST Hard Bans (`aci.py`)**:
   - Immediate rejection on `eval()`, `exec()`, `shell=True`, bare `except: pass`, string-built SQL, `# noqa`, `# type: ignore`, `ORDER BY RANDOM()`.
3. **Atomic Staging (`staging_buffer.py`)**:
   - Model outputs never touch production directly. Proposals are compiled into isolated staging buffers and executed against unit tests in `env={}` ring-fenced subprocesses.

---

## 3. Schemas & Data Specifications (Sovereign Media Engine)

### 3.1 DDL Integrity & Provenance (`definitive_schema.sql`)
```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- DDL Version Guard
CREATE TABLE schema_meta (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Dimension Tables with Strict GLOB Validations
CREATE TABLE video_types (
    id TEXT PRIMARY KEY CHECK (id GLOB 'VT[0-9][0-9]'),
    name TEXT NOT NULL UNIQUE,
    tier INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 5),
    schema_version TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

-- Normalized Compatibility Junction (Zero Orphan FKs)
CREATE TABLE compatibility_matrix (
    vt_id TEXT NOT NULL REFERENCES video_types(id),
    dimension TEXT NOT NULL CHECK (dimension IN ('format','duration','hook','arc','message')),
    value_id TEXT NOT NULL,
    PRIMARY KEY (vt_id, dimension, value_id)
);

-- Ingestion Audit Lineage
CREATE TABLE ingestion_runs (
    run_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    source_hashes_json TEXT NOT NULL,
    total_records INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMMITTED', 'ROLLED_BACK')),
    executed_at TEXT NOT NULL
);
```

---

## 4. Cryptographic & Verification Physics

1. **Source Block Anti-Drift**:
   - Markdown documents contain structured YAML `SOURCE_BLOCK` markers.
   - `test_ledger.py` runs a `doc_sync` test asserting that prose documentation $\equiv$ `SOURCE_BLOCK` via set equality.
2. **Golden Round-Trip Verification**:
   - Re-serializes the SQLite relational matrix back into canonical format and asserts set-equality against raw source bytes.
3. **Crash Corpus Accumulation (`fuzz_corpus.db`)**:
   - Every OS/test failure payload is stored permanently in SQLite, ensuring regression immunity across future model generations.
