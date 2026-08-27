"""
Zero-Trust Autonomous Engine Package.
Enforces 6-state promotion lifecycle, 8-point cryptographic binding,
sterile verification isolation, 3-strike failure discrimination, and crash recovery.
"""

from zero_trust_engine.schema import (
    State,
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
from zero_trust_engine.db import StateDatabase
from zero_trust_engine.governor import GovernorEngine
from zero_trust_engine.verifier_gate import PhysicalVerifierGate
from zero_trust_engine.promoter import PromotionCoordinator
from zero_trust_engine.quarantine import QuarantineManager

__all__ = [
    "State",
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
    "StateDatabase",
    "GovernorEngine",
    "PhysicalVerifierGate",
    "PromotionCoordinator",
    "QuarantineManager",
]
