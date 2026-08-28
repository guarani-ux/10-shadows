"""
loop_engine/schema.py
Typed state models, cryptographic hash bindings, and failure classifications for 10 SHADOWS.
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional



from loop_engine.epistemic import (
    EvidenceOrigin,
    EpistemicStatus,
    EpistemicDisposition,
    EvidenceEnvelope,
    SemanticLaunderingError,
    create_envelope,
    transform_envelope,
)



class State(str, Enum):
    CANDIDATE_SEALED = "CANDIDATE_SEALED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    PROMOTION_PENDING = "PROMOTION_PENDING"
    PROMOTED = "PROMOTED"
    POST_PROMOTION_VERIFIED = "POST_PROMOTION_VERIFIED"


# Valid state machine transitions
LEGAL_STATE_TRANSITIONS: Dict[State, List[State]] = {
    State.CANDIDATE_SEALED: [State.VERIFYING],
    State.VERIFYING: [State.VERIFIED, State.REJECTED, State.BLOCKED],
    State.VERIFIED: [State.PROMOTION_PENDING, State.VERIFYING],
    State.REJECTED: [State.VERIFYING],
    State.BLOCKED: [State.VERIFYING],
    State.PROMOTION_PENDING: [State.PROMOTED, State.VERIFIED],  # Can rollback to VERIFIED on reconcile
    State.PROMOTED: [State.POST_PROMOTION_VERIFIED],
    State.POST_PROMOTION_VERIFIED: [],
}


class FailureClassification(str, Enum):
    CANDIDATE_FAILURE = "CANDIDATE_FAILURE"      # Implementation bug (consumes strike)
    REGRESSION_FAILURE = "REGRESSION_FAILURE"    # Broke existing test (consumes strike)
    SPEC_FAILURE = "SPEC_FAILURE"                # Ambiguous or invalid spec (no strike)
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"  # OOM, socket, platform error (no strike)
    NETWORK_FAILURE = "NETWORK_FAILURE"          # Transient upstream API error (no strike)
    PERMISSION_FAILURE = "PERMISSION_FAILURE"    # Permission / auth failure (no strike)
    FLAKY_FAILURE = "FLAKY_FAILURE"              # Non-deterministic failure (no strike)
    GOVERNOR_FAILURE = "GOVERNOR_FAILURE"        # Harness / anti-tamper abort (no strike)


@dataclass(frozen=True)
class EnvironmentFingerprint:
    python_version: str
    platform_system: str
    platform_release: str
    architecture: str
    env_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "python_version": self.python_version,
            "platform_system": self.platform_system,
            "platform_release": self.platform_release,
            "architecture": self.architecture,
            "env_hash": self.env_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentFingerprint":
        return cls(
            python_version=data["python_version"],
            platform_system=data["platform_system"],
            platform_release=data["platform_release"],
            architecture=data["architecture"],
            env_hash=data["env_hash"],
        )


@dataclass
class ProposalManifest:
    task_id: str
    spec_hash: str
    base_commit_sha: str
    candidate_commit_sha: str
    candidate_tree_sha: str
    verifier_version: str
    acceptance_test_digest: str
    env_fingerprint: EnvironmentFingerprint
    state: State = State.CANDIDATE_SEALED
    timestamp: Optional[float] = None


@dataclass
class VerificationReceipt:
    receipt_id: Optional[int]
    task_id: str
    spec_hash: str
    base_commit_sha: str
    candidate_commit_sha: str
    candidate_tree_sha: str
    physical_tree_hash: str
    verifier_version: str
    acceptance_test_digest: str
    env_fingerprint: EnvironmentFingerprint
    status: State
    failure_classification: Optional[FailureClassification] = None
    failure_signature: Optional[str] = None
    execution_trace: Optional[str] = None
    epistemic_disposition: Optional[str] = "SATISFIED"
    timestamp: Optional[float] = None



@dataclass
class QuarantineRecord:
    quarantine_id: Optional[int]
    task_id: str
    quarantine_dir: str
    candidate_commit_sha: str
    failure_classification: FailureClassification
    failure_signature: str
    execution_trace: str
    timestamp: float


def compute_spec_hash(spec_text: str) -> str:
    """Computes SHA-256 digest of normalized task specification."""
    normalized = spec_text.strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_tree_hash(directory_path: Path) -> str:
    """Computes physical deterministic tree digest from directory state."""
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(directory_path):
        dirs.sort()
        for filename in sorted(files):
            if filename.startswith(".git") or filename.endswith(".pyc") or filename == "__pycache__":
                continue
            file_path = Path(root) / filename
            if file_path.is_symlink():
                continue
            rel_path = file_path.relative_to(directory_path).as_posix()
            hasher.update(rel_path.encode("utf-8"))
            try:
                hasher.update(file_path.read_bytes())
            except Exception:
                pass
    return hasher.hexdigest()


def compute_test_digest(fixtures_path: Path) -> str:
    """Computes SHA-256 digest across all canonical acceptance fixtures."""
    return compute_tree_hash(fixtures_path)


def compute_env_fingerprint() -> EnvironmentFingerprint:
    """Captures deterministic runtime fingerprint."""
    env_keys = sorted(["PATH", "VIRTUAL_ENV", "PYTHONPATH", "LANG", "LC_ALL"])
    filtered_env = {k: os.environ.get(k, "") for k in env_keys}
    env_serialized = json.dumps(filtered_env, sort_keys=True)
    env_hash = hashlib.sha256(env_serialized.encode("utf-8")).hexdigest()
    
    return EnvironmentFingerprint(
        python_version=sys.version.split()[0],
        platform_system=platform.system(),
        platform_release=platform.release(),
        architecture=platform.machine(),
        env_hash=env_hash,
    )


def compute_failure_signature(failure_trace: str) -> str:
    """Extracts structural crash AST/exception signature to detect oscillation."""
    lines = [line.strip() for line in failure_trace.splitlines() if line.strip()]
    sig_lines = [l for l in lines if ("Error:" in l or "Exception:" in l or "FAILED" in l)]
    target = "\n".join(sig_lines) if sig_lines else failure_trace[:500]
    return hashlib.sha256(target.encode("utf-8")).hexdigest()
