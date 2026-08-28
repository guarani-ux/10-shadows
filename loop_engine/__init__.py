"""
Loop Engine Package - Sovereign Multi-Domain Autonomous Loop Runtime.
"""

from loop_engine.base import BaseLoop
from loop_engine.extractor import strip_markdown_fences, safe_extract_target
from loop_engine.preflight import (
    canonical_spec_hash,
    verify_disk_writable,
    probe_required_modules,
    run_pre_flight,
    assert_spec_untampered,
    PreflightCheckError,
    SpecTamperError,
)
from loop_engine.governor import Governor, StrikeCeilingExceededError
from loop_engine.receipts import (
    atomic_two_phase_commit,
    compute_file_sha256,
    ReceiptStore,
    AtomicCommitError,
)
from loop_engine.verifiers.ast_gate import (
    ASTSecurityViolation,
    ASTSecurityVisitor,
    validate_ast_security,
    inspect_file_ast,
)
from loop_engine.verifiers.test_gate import (
    SubprocessGateError,
    run_isolated_pytest,
)
from loop_engine.runners.code_runner import CodeRunnerLoop
from loop_engine.verifier_daemon import process_intent, run_daemon
from loop_engine.authority import ProofWitness, VerificationContractWitness, issue_proof_witness, create_verification_contract_witness
from loop_engine.capability import CapabilityContract, evaluate_capability_applicability
from loop_engine.epistemic import (
    EvidenceOrigin,
    EpistemicStatus,
    EpistemicDisposition,
    EvidenceEnvelope,
    create_unverified_envelope,
    mint_verified_envelope,
    transform_envelope,
)
from loop_engine.disposition import ActionDisposition, evaluate_execution_disposition
from loop_engine.sterile_env import build_sterile_environment
from loop_engine.ast_guard import scan_ast, scan_python_worktree
from loop_engine.governance import (
    GovernanceConfig,
    GovernanceConfigurationError,
    load_canonical_governance,
)
from loop_engine.transition import (
    PrivilegedTransitionEngine,
    TransitionRequest,
    TransitionReceipt,
    TransitionRejection,
)


__all__ = [
    "BaseLoop",
    "strip_markdown_fences",
    "safe_extract_target",
    "canonical_spec_hash",
    "verify_disk_writable",
    "probe_required_modules",
    "run_pre_flight",
    "assert_spec_untampered",
    "PreflightCheckError",
    "SpecTamperError",
    "Governor",
    "StrikeCeilingExceededError",
    "atomic_two_phase_commit",
    "compute_file_sha256",
    "ReceiptStore",
    "AtomicCommitError",
    "ASTSecurityViolation",
    "ASTSecurityVisitor",
    "validate_ast_security",
    "inspect_file_ast",
    "SubprocessGateError",
    "run_isolated_pytest",
    "CodeRunnerLoop",
    "process_intent",
    "run_daemon",
    "ProofWitness",
    "VerificationContractWitness",
    "issue_proof_witness",
    "create_verification_contract_witness",
    "CapabilityContract",
    "evaluate_capability_applicability",
    "EvidenceOrigin",
    "EpistemicStatus",
    "EpistemicDisposition",
    "EvidenceEnvelope",
    "create_unverified_envelope",
    "mint_verified_envelope",
    "transform_envelope",
    "ActionDisposition",
    "evaluate_execution_disposition",
    "build_sterile_environment",
    "scan_ast",
    "scan_python_worktree",
    "GovernanceConfig",
    "GovernanceConfigurationError",
    "load_canonical_governance",
    "PrivilegedTransitionEngine",
    "TransitionRequest",
    "TransitionReceipt",
    "TransitionRejection",
]


