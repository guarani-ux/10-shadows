"""
zero_trust_engine/schema.py
Re-exports canonical schemas and types from loop_engine.schema.
"""

from loop_engine.schema import (
    State,
    LEGAL_STATE_TRANSITIONS,
    FailureClassification,
    EnvironmentFingerprint,
    ProposalManifest,
    VerificationReceipt,
    QuarantineRecord,
    compute_spec_hash,
    compute_tree_hash,
    compute_test_digest,
    compute_env_fingerprint,
    compute_failure_signature,
)

__all__ = [
    "State",
    "LEGAL_STATE_TRANSITIONS",
    "FailureClassification",
    "EnvironmentFingerprint",
    "ProposalManifest",
    "VerificationReceipt",
    "QuarantineRecord",
    "compute_spec_hash",
    "compute_tree_hash",
    "compute_test_digest",
    "compute_env_fingerprint",
    "compute_failure_signature",
]
