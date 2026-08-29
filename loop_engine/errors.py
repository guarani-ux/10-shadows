"""
loop_engine/errors.py
Typed Error Hierarchy and Causal Failure Classification for 10 SHADOWS.

Invariants:
1. All domain exceptions inherit from TenShadowsError.
2. Structured context retains causality without leaking secrets or tokens.
3. Distinguishes epistemic deficits, authority violations, execution limits, and persistence errors.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class TenShadowsError(Exception):
    """Base exception for all Ten Shadows errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# Configuration & Setup Errors
class ConfigurationError(TenShadowsError):
    """Raised when environment or path configuration is invalid or missing."""


class PreflightCheckError(TenShadowsError):
    """Raised when deterministic preflight environment checks fail."""


# Authority & Governance Errors
class AuthorityError(TenShadowsError):
    """Base exception for authority boundary and permission violations."""


class UnauthorizedRevisionError(AuthorityError):
    """Raised when an untrusted worker attempts to revise an objective without valid authority token."""


class SelfCertificationForbiddenError(AuthorityError):
    """Raised when builder_id == verifier_id on verification (Law 3 violation)."""


class AuthoritativeSourceProtectionError(AuthorityError):
    """Raised when a worker attempts to directly mutate the authoritative repository."""


class WorkerTokenTamperedError(AuthorityError):
    """Raised when a worker authorization token does not match expected cryptographic digest."""


# Epistemic & Semantic Deficit Errors
class EpistemicDeficitError(TenShadowsError):
    """Base exception for missing or ungrounded knowledge/semantics."""


class DroppedClauseError(EpistemicDeficitError):
    """Raised when raw intent clauses are omitted in candidate interpretations."""


class UnauthorizedAssumptionError(EpistemicDeficitError):
    """Raised when candidate requirements introduce ungated assumed knowledge."""


# Evidence Errors
class EvidenceError(TenShadowsError):
    """Base exception for evidence evaluation failures."""


class EvidenceContradictedError(EvidenceError):
    """Raised when independent verifier observations contradict claimed properties."""


class CandidateMismatchError(EvidenceError):
    """Raised when evidence observed on candidate SHA_A is applied to candidate SHA_B."""


class EnvironmentMismatchError(EvidenceError):
    """Raised when evidence observed in environment_A is applied to environment_B."""


# Capability Errors
class CapabilityDeficitError(TenShadowsError):
    """Raised when required state transitions lack qualified executable operators."""


# Execution & Resource Bounds Errors
class ExecutionError(TenShadowsError):
    """Base exception for subprocess and runner execution failures."""


class TimeoutExceededError(ExecutionError):
    """Raised when subprocess execution exceeds configured time boundary."""


class OutputLimitExceededError(ExecutionError):
    """Raised when stdout/stderr capture exceeds max output byte boundary."""


class GovernorThreeStrikeAbort(ExecutionError):
    """Raised when repair attempts exceed the 3-strike governor limit (Law 9)."""


# Persistence & Schema Errors
class PersistenceError(TenShadowsError):
    """Base exception for database and state persistence failures."""


class SchemaMigrationRequiredError(PersistenceError):
    """Raised when physical database schema version does not match expected system schema."""


class ReceiptIntegrityError(PersistenceError):
    """Raised when cryptographic receipt signatures or hashes fail verification."""


class ConcurrencyConflictError(PersistenceError):
    """Raised when concurrent operations attempt conflicting mutations on governed resources."""


class InternalInvariantViolation(TenShadowsError):
    """Raised when physical system state violates a core mathematical TCB invariant."""
