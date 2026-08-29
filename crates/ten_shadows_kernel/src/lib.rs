//! ten_shadows_kernel — Mechanically Authoritative Trusted Kernel for 10 SHADOWS.

pub mod candidate;
pub mod constitution;
pub mod db;
pub mod dispatcher;
pub mod evidence;
pub mod graph;
pub mod predicate;
pub mod receipt;
pub mod repository;
pub mod state_machine;
pub mod time_utils;
pub mod verifier;

pub use candidate::{
    CandidateClassification, CandidateLineage, ExternalCandidate, GovernedCandidate,
};
pub use constitution::{
    EvidenceEntailment, ObjectiveContract, ObjectiveSufficiencyProof, Obligation, ObligationStatus,
    SufficiencyRule,
};
pub use db::KernelDb;
pub use dispatcher::{
    DispatchError, ProviderUsage, WorkerAuthorization, WorkerDispatcher, WorkerExecutionResult,
};
pub use evidence::{
    assert_evidence_monotonicity, EvidenceModality, EvidencePurpose, SubstrateLawError,
    VerificationType,
};
pub use predicate::{evaluate_receipt, VerificationReport};
pub use receipt::{
    DisaggregatedEpistemicClaims, ExecutionAttemptRecord, IndependentVerificationRecord,
    ProviderExecutionReceipt, RoutingStrategy, RunStatus, TenShadowsReceipt,
    WorkerInvocationRecord, WorkerRole,
};
pub use repository::{AuthoritativeSource, GovernedWorkspace, RepositoryRoleError};
pub use state_machine::{Created, KernelRun, Promoted};
pub use time_utils::current_timestamp_rfc3339;
pub use verifier::SubprocessVerifier;
