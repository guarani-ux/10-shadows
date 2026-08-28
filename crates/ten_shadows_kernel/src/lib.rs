//! ten_shadows_kernel — Mechanically Authoritative Trusted Kernel for 10 SHADOWS.

pub mod candidate;
pub mod db;
pub mod evidence;
pub mod predicate;
pub mod receipt;
pub mod state_machine;
pub mod time_utils;
pub mod verifier;

pub use candidate::{CandidateClassification, CandidateLineage, ExternalCandidate, GovernedCandidate};
pub use db::KernelDb;
pub use evidence::{assert_evidence_monotonicity, EvidenceModality, EvidencePurpose, SubstrateLawError, VerificationType};
pub use predicate::{evaluate_receipt, VerificationReport};
pub use receipt::{
    DisaggregatedEpistemicClaims, ExecutionAttemptRecord, IndependentVerificationRecord,
    ProviderExecutionReceipt, RoutingStrategy, RunStatus, TenShadowsReceipt,
    WorkerInvocationRecord, WorkerRole,
};
pub use state_machine::{Created, KernelRun, Promoted};
pub use time_utils::current_timestamp_rfc3339;
pub use verifier::SubprocessVerifier;
