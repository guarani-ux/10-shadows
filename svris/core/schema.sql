PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Topics (Controlled Taxonomy)
CREATE TABLE IF NOT EXISTS topics (
    topic_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_topic_id TEXT REFERENCES topics(topic_id),
    description TEXT
);

-- 2. Source Origin
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    url TEXT,
    title TEXT NOT NULL,
    publisher TEXT,
    author TEXT,
    publication_date TEXT,
    retrieval_date TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('ACADEMIC', 'JOURNALISM', 'PRIMARY_DOC', 'INDUSTRY_REPORT', 'INTERVIEW', 'WEB', 'OTHER')),
    trust_tier TEXT NOT NULL CHECK (trust_tier IN ('UNTRUSTED_RETRIEVAL', 'VERIFIED_PRIMARY', 'AUTHORITATIVE_SECONDARY')),
    raw_content_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 3. Source Snapshots (Physical Content Custody)
CREATE TABLE IF NOT EXISTS source_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    retrieved_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    media_type TEXT NOT NULL DEFAULT 'text/plain',
    canonical_url TEXT,
    created_at TEXT NOT NULL
);

-- 4. Source Chunks (Granular Content Spans)
CREATE TABLE IF NOT EXISTS source_chunks (
    chunk_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    start_char INTEGER NOT NULL CHECK (start_char >= 0),
    end_char INTEGER NOT NULL CHECK (end_char > start_char),
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    UNIQUE(snapshot_id, ordinal)
);

-- 5. Research Runs & Ingestion Batches
CREATE TABLE IF NOT EXISTS research_runs (
    run_id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topics(topic_id),
    objective TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    plan_json TEXT NOT NULL,
    summary_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS research_run_sources (
    run_id TEXT NOT NULL REFERENCES research_runs(run_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id),
    discovered_at TEXT NOT NULL,
    PRIMARY KEY (run_id, source_id)
);

-- 6. Atomic Factual Claims (with CAS revision lock)
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    claim_text TEXT NOT NULL,
    topic_id TEXT NOT NULL REFERENCES topics(topic_id),
    verification_state TEXT NOT NULL CHECK (verification_state IN ('VERIFIED', 'UNVERIFIED', 'CONTRADICTED', 'STALE', 'SUPERSEDED')),
    valid_from TEXT,
    valid_until TEXT,
    review_after TEXT,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 7. Explicit Evidence Junction with Exact Quote Span Proof
CREATE TABLE IF NOT EXISTS evidence_relationships (
    evidence_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    snapshot_id TEXT REFERENCES source_snapshots(snapshot_id),
    chunk_id TEXT REFERENCES source_chunks(chunk_id),
    relationship_state TEXT NOT NULL CHECK (relationship_state IN ('SUPPORTS', 'PARTIALLY_SUPPORTS', 'CONTRADICTS', 'CONTEXTUALIZES', 'DOES_NOT_ESTABLISH')),
    quote_text TEXT,
    quote_start INTEGER,
    quote_end INTEGER,
    quote_sha256 TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(claim_id, source_id, relationship_state)
);

-- 8. Verification Audit Events
CREATE TABLE IF NOT EXISTS verification_events (
    verification_event_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    policy_version TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    basis_json TEXT NOT NULL,
    supporting_evidence_count INTEGER NOT NULL DEFAULT 0,
    independent_source_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- 9. Claim Relations & Successor Lineage
CREATE TABLE IF NOT EXISTS claim_relations (
    relation_id TEXT PRIMARY KEY,
    from_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    to_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    relation_type TEXT NOT NULL CHECK (relation_type IN ('SUPERSEDES', 'REFINES', 'DUPLICATE_OF', 'CORROBORATES')),
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 10. Contradiction Registry
CREATE TABLE IF NOT EXISTS contradictions (
    contradiction_id TEXT PRIMARY KEY,
    claim_id_a TEXT NOT NULL REFERENCES claims(claim_id),
    claim_id_b TEXT NOT NULL REFERENCES claims(claim_id),
    nature_of_conflict TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN_UNRESOLVED', 'EXPLICIT_DISPUTE', 'SUPERSEDED')),
    created_at TEXT NOT NULL
);

-- 11. Derived Editorial Insights
CREATE TABLE IF NOT EXISTS insights (
    insight_id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topics(topic_id),
    insight_text TEXT NOT NULL,
    primary_claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    created_at TEXT NOT NULL
);

-- 12. Story Angles
CREATE TABLE IF NOT EXISTS story_angles (
    angle_id TEXT PRIMARY KEY,
    insight_id TEXT NOT NULL REFERENCES insights(insight_id),
    angle_text TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    emotional_hook_hypothesis TEXT,
    used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    created_at TEXT NOT NULL
);

-- 13. Script Primitives (Read Boundary for Scriptwriters)
CREATE TABLE IF NOT EXISTS script_primitives (
    primitive_id TEXT PRIMARY KEY,
    angle_id TEXT NOT NULL REFERENCES story_angles(angle_id),
    primitive_type TEXT NOT NULL CHECK (primitive_type IN ('HOOK', 'QUESTION', 'SETUP', 'TENSION', 'CLAIM', 'PROOF', 'EXAMPLE', 'MISCONCEPTION', 'PAYOFF', 'CTA', 'VISUAL_CUE')),
    content TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('ALL', 'YOUTUBE', 'INSTAGRAM', 'FACEBOOK')),
    format TEXT NOT NULL CHECK (format IN ('ALL', 'LONG_FORM', 'SHORT_FORM')),
    orientation TEXT NOT NULL CHECK (orientation IN ('ALL', 'HORIZONTAL', 'VERTICAL')),
    created_at TEXT NOT NULL
);
