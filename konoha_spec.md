# Reverse-Engineering Architectural Decomposition: Konohagakure (Konoha 0.1.0)

## 1. Formal State Machine & Invariants

### 1.1 State Taxonomy
* **`CaseStatus` Lifecycle**:
  ```text
  [INITIAL INPUT] ──analyze──► [DECIDED (rev 0)] ──outcome──► [CLOSED (rev 1)]
  ```
  - `OPEN`: Defined in enum, reserved for unassessed staging.
  - `DECIDED`: Initialized state upon creation via `analyze`. Revision is fixed at `0`.
  - `CLOSED`: Terminal state upon recording a verified `Outcome`. Revision increments monotonically to `1`.

* **`EvidenceStatus`**:
  - `VERIFIED`: Directly grounded in retained source bytes.
  - `INFERRED`: Derived logically from verified evidence.
  - `HYPOTHESIS`: Unverified proposition.
  - `UNKNOWN`: Missing decision-critical data.
  - `CONTRADICTED`: In conflict with verified ground truth.

* **`AssessmentDecision`**:
  - `pursue`: All gates cleared.
  - `decline`: Hard rejection triggered.
  - `clarify`: Information gap or missing capability detected.
  - `defer`: Explicit non-action state.

* **`OutcomeStatus`**:
  - `not_yet_due`, `collected`, `invoiced`, `lost`, `declined`, `no_response`, `completed`, `harmed`, `unknown`.

### 1.2 Invariants & Rejection Rules
* **Optimistic Concurrency & Revision Monotonicity**:
  - Revisions start strictly at `0`.
  - Outcome writes enforce single-writer concurrency using conditional atomic CAS:
    $$\Delta = \text{UPDATE } \text{decision\_cases} \text{ SET status} = 'closed', \text{revision} = \text{revision} + 1 \text{ WHERE case\_id} = ? \text{ AND revision} = \text{expected\_revision}$$
  - If affected rows $\neq 1$, transaction emits immediate `ROLLBACK` and raises `IntegrityError("causal collision or absent case; outcome was not recorded")`.
* **Value Invariants**:
  - All monetary values (`minimum_value`, `expected_value`, `invoiced_value`, `collected_value`, `direct_cost`) are represented as arbitrary-precision `Decimal` objects.
  - Negative values trigger `DomainError("{label} must not be negative")`.
  - Malformed non-numeric strings trigger `DomainError("{label} must be a decimal string")`.

---

## 2. Schemas & Data Specifications

### 2.1 Database DDL (SQLite)
```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS source_documents (
    source_sha256 TEXT PRIMARY KEY,
    content BLOB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    source_sha256 TEXT NOT NULL REFERENCES source_documents(source_sha256),
    unaided_decision TEXT NOT NULL,
    assessment_decision TEXT NOT NULL,
    assessment_reasons_json TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    final_decision TEXT NOT NULL,
    observations_json TEXT NOT NULL,
    unknowns_json TEXT NOT NULL,
    required_capabilities_json TEXT NOT NULL,
    expected_value TEXT,
    risk_markers_json TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    case_id TEXT NOT NULL REFERENCES decision_cases(case_id),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS journal_events_case_id ON journal_events(case_id);
```

### 2.2 Domain Models & Serialization Contracts
All models are frozen slotted dataclasses (`@dataclass(frozen=True, slots=True)`):

1. **`Observation`**:
   - `text: str` (non-blank after strip)
   - `evidence_status: EvidenceStatus`
   - `source_reference: str` (non-blank after strip)
2. **`Policy`**:
   - `version: str` (non-blank)
   - `minimum_value: Optional[Decimal]`
   - `available: bool`
   - `required_capabilities: frozenset[str]` (normalized to lowercase, stripped)
   - `available_capabilities: frozenset[str]` (normalized to lowercase, stripped)
   - `excluded_risk_markers: frozenset[str]` (normalized to lowercase, stripped)
3. **`CaseInput`**:
   - `title: str`
   - `source_reference: str`
   - `source_content: bytes` (non-empty)
   - `unaided_decision: AssessmentDecision`
   - `observations: Tuple[Observation, ...]`
   - `unknowns: Tuple[str, ...]` (stripped)
   - `required_capabilities: Tuple[str, ...]` (lowercase, stripped)
   - `expected_value: Optional[Decimal]`
   - `risk_markers: Tuple[str, ...]` (lowercase, stripped)
4. **`Canonical JSON Serialization`**:
   - Delimiters: Separators strictly `(',', ':')` with `sort_keys=True` and `ensure_ascii=False`.

---

## 3. Cryptographic Physics & Ledger Integrity

### 3.1 Hashing Specifications
* **Digest Function**: Standard SHA-256 returning 64-character lowercase hexadecimal string.
* **Source Hashing**:
  $$\text{source\_sha256} = \text{SHA256}(\text{source\_content})$$
* **Genesis Hash State**:
  $$\text{previous\_hash}_0 = \text{"0"}^{64} \quad (64 \text{ zeros})$$
* **Event Digest Formula**:
  $$\text{material} = \text{previous\_hash} \parallel "|" \parallel \text{sequence} \parallel "|" \parallel \text{event\_type} \parallel "|" \parallel \text{payload\_json} \parallel "|" \parallel \text{occurred\_at}$$
  $$\text{event\_hash} = \text{SHA256}(\text{material}.\text{encode}("utf\text{-}8"))$$
* **Event ID Formula**:
  $$\text{event\_id} = \text{SHA256}((\text{case\_id} \parallel "|" \parallel \text{sequence} \parallel "|" \parallel \text{event\_hash}).\text{encode}("utf\text{-}8"))$$

### 3.2 Audit & Replay Verification Algorithm
1. Query `journal_events` ordered by `sequence ASC`.
2. Initialize `expected_previous = "0" * 64`, `expected_sequence = 1`.
3. For each event row:
   - Verify `row.sequence == expected_sequence`. If mismatch $\rightarrow$ Fail: `"sequence gap at event {sequence}"`.
   - Calculate `recalculated_hash = event_digest(expected_previous, expected_sequence, row.event_type, row.payload_json, row.occurred_at)`.
   - Verify `row.previous_hash == expected_previous` AND `row.event_hash == recalculated_hash`. If mismatch $\rightarrow$ Fail: `"hash mismatch at event {sequence}"`.
   - Mutate `expected_previous = recalculated_hash`, `expected_sequence += 1`.
4. Query `source_documents`:
   - For each source row, verify `SHA256(row.content) == row.source_sha256`. If mismatch $\rightarrow$ Fail: `"source hash mismatch: {source_sha256}"`.
5. Return Success: `"verified {N} events and {M} sources"`.

---

## 4. Transaction Boundaries & Concurrency

| Operation | Isolation / Lock | Atomicity Scope | Rollback Condition |
| :--- | :--- | :--- | :--- |
| `store_source` | `BEGIN IMMEDIATE` | `source_documents` INSERT | SQLite lock contention or I/O failure |
| `create_case` | `BEGIN IMMEDIATE` | `decision_cases` INSERT + `journal_events` (case_created) | Any constraint failure aborts whole creation |
| `record_outcome`| `BEGIN IMMEDIATE` | `decision_cases` UPDATE + `journal_events` (outcome_recorded) | Stale revision ($rowcount \neq 1$) triggers ROLLBACK |
| `verify_journal`| Read snapshot | Full journal scan | None (read-only) |

---

## 5. Pure Logic & Deterministic Decision Tree

Function: `evaluate(case_input: CaseInput, policy: Policy) -> Assessment`

Order of evaluation (strictly top-to-bottom, first match wins):

```text
1. Prohibited Risk Markers:
   blocked = set(case_input.risk_markers) ∩ policy.excluded_risk_markers
   IF blocked is not empty:
     -> DECLINE ["decline: prohibited risk markers: " + sorted(blocked).join(", ")]

2. Operator Availability:
   IF policy.available == False:
     -> DECLINE ["decline: operator availability is false"]

3. Missing Capabilities:
   missing = set(case_input.required_capabilities) - policy.available_capabilities
   IF missing is not empty:
     -> CLARIFY ["clarify: unavailable required capabilities: " + sorted(missing).join(", ")]

4. Decision-Relevant Unknowns:
   IF len(case_input.unknowns) > 0:
     -> CLARIFY ["clarify: decision-relevant unknowns: " + case_input.unknowns.join(", ")]

5. Value Thresholds:
   IF policy.minimum_value is not None:
     IF case_input.expected_value is None:
       -> CLARIFY ["clarify: expected value is unknown"]
     IF case_input.expected_value < policy.minimum_value:
       -> DECLINE ["decline: expected value {expected} is below minimum {min}"]

6. Default:
   -> PURSUE ["pursue: no hard exclusion or clarification condition was triggered"]
```

---

## 6. CLI & I/O Protocol Specification

* **Binary Name**: `konoha` (or `python -m konoha.cli`)
* **Global Options**: `--database <path>` (defaults to `konoha.db`)

### Subcommands:
1. **`analyze --input <json_file>`**
   - Stdin/File: JSON object containing `"case"` and `"policy"` keys.
   - Stdout: JSON payload:
     ```json
     {
       "case_id": "<UUID>",
       "assessment": "<pursue|decline|clarify|defer>",
       "reasons": ["<reason_string>"],
       "final_decision": "<pursue|decline|clarify|defer>",
       "revision": 0
     }
     ```
   - Exit Code: `0` on success, `2` on error.

2. **`outcome <case_id> --revision <int> --status <status> [--invoiced-value <val>] [--collected-value <val>] [--direct-cost <val>] [--notes <text>]`**
   - Stdout: JSON payload:
     ```json
     {
       "case_id": "<UUID>",
       "revision": 1,
       "status": "<status>"
     }
     ```
   - Exit Code: `0` on success, `2` on error.

3. **`show <case_id>`**
   - Stdout: Formatted JSON representation of SQLite `decision_cases` row.
   - Exit Code: `0` on success, `2` on error.

4. **`list`**
   - Stdout: JSON array of all decision cases ordered by `created_at DESC`.
   - Exit Code: `0` on success, `2` on error.

5. **`ledger-verify`**
   - Stdout: `verified {N} events and {M} sources`
   - Exit Code: `0` if verification passes, `2` on integrity failure.

### Standard Error Handling
All domain, integrity, and argument errors print to `sys.stderr` formatted as:
`error: <message>` with Exit Code `2`.
