//! state_machine.rs — Compile-Time Typestate State Machine for Ten Shadows Kernel.
//!
//! Enforces that illegal lifecycle transitions are mathematically unrepresentable.

use crate::candidate::{CandidateClassification, CandidateLineage, ExternalCandidate, GovernedCandidate};
use crate::evidence::{EvidenceModality, VerificationType};
use crate::receipt::{
    DisaggregatedEpistemicClaims, ExecutionAttemptRecord, IndependentVerificationRecord,
    RoutingStrategy, RunStatus, TenShadowsReceipt, WorkerInvocationRecord,
};
use crate::time_utils::current_timestamp_rfc3339;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// Typestate Markers
// ---------------------------------------------------------------------------

pub struct Created;
pub struct BaselineCaptured;
pub struct WorkspaceReady;
pub struct WorkerAuthorized;
pub struct CandidateProduced;
pub struct Verified;
pub struct Promoted;

// ---------------------------------------------------------------------------
// Typed Kernel Run Struct
// ---------------------------------------------------------------------------

pub struct KernelRun<State> {
    pub run_id: String,
    pub task_id: String,
    pub objective: String,
    pub objective_hash: String,
    pub target_path: PathBuf,
    pub strategy: RoutingStrategy,
    pub capabilities: Vec<String>,
    pub routing_digest: String,
    pub starting_head: Option<String>,
    pub workspace_path: Option<PathBuf>,
    pub authorized_worker_id: Option<String>,
    pub worker_invocations: Vec<WorkerInvocationRecord>,
    pub candidate_classification: Option<CandidateClassification>,
    pub attempts: Vec<ExecutionAttemptRecord>,
    pub verification: Option<IndependentVerificationRecord>,
    pub final_head: Option<String>,
    pub created_at: String,
    pub state_marker: std::marker::PhantomData<State>,
}

impl KernelRun<Created> {
    pub fn new(
        objective: &str,
        target_path: &Path,
        task_id: Option<String>,
    ) -> Self {
        let millis = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
        let tid = task_id.unwrap_or_else(|| format!("task_{}", millis));
        let run_id = format!("run_{}_{}", tid, millis % 10000000);
        
        let mut hasher = Sha256::new();
        hasher.update(objective.as_bytes());
        let objective_hash = format!("{:x}", hasher.finalize());

        let (strategy, caps) = Self::characterize_objective(objective);
        let routing_digest = Self::compute_routing_digest(&run_id, &strategy, &caps);

        Self {
            run_id,
            task_id: tid,
            objective: objective.to_string(),
            objective_hash,
            target_path: target_path.to_path_buf(),
            strategy,
            capabilities: caps,
            routing_digest,
            starting_head: None,
            workspace_path: None,
            authorized_worker_id: None,
            worker_invocations: Vec::new(),
            candidate_classification: None,
            attempts: Vec::new(),
            verification: None,
            final_head: None,
            created_at: current_timestamp_rfc3339(),
            state_marker: std::marker::PhantomData,
        }
    }

    fn characterize_objective(obj: &str) -> (RoutingStrategy, Vec<String>) {
        let lower = obj.to_lowercase();
        if lower.contains("harden") || lower.contains("zero trust") || lower.contains("persist") {
            (
                RoutingStrategy::CodeHardening,
                vec![
                    "PERSISTENCE_HARDENING".into(),
                    "DETERMINISTIC_TIME".into(),
                    "ATOMIC_MUTATION".into(),
                    "INDEPENDENT_VERIFICATION".into(),
                ],
            )
        } else if lower.contains("audit") || lower.contains("verify") || lower.contains("falsify") {
            (
                RoutingStrategy::AdversarialAudit,
                vec![
                    "STATIC_INSPECTION".into(),
                    "ADVERSARIAL_FALSIFICATION".into(),
                    "CONTRACT_VERIFICATION".into(),
                ],
            )
        } else if lower.contains("trivial") || lower.contains("ping") || lower.contains("echo") {
            (
                RoutingStrategy::DirectDelegation,
                vec!["DIRECT_EXECUTION".into()],
            )
        } else {
            (
                RoutingStrategy::GoalDecomposition,
                vec![
                    "INTENT_ADEQUACY".into(),
                    "OBLIGATION_DERIVATION".into(),
                    "BUILD_COMPILATION".into(),
                    "INDEPENDENT_VERIFICATION".into(),
                ],
            )
        }
    }

    fn compute_routing_digest(run_id: &str, strat: &RoutingStrategy, caps: &[String]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(format!("{}:{:#?}:{:#?}", run_id, strat, caps).as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn capture_baseline(
        mut self,
        starting_head: Option<String>,
    ) -> KernelRun<BaselineCaptured> {
        self.starting_head = starting_head;
        KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: None,
            authorized_worker_id: None,
            worker_invocations: self.worker_invocations,
            candidate_classification: None,
            attempts: self.attempts,
            verification: None,
            final_head: None,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }
}

impl KernelRun<BaselineCaptured> {
    pub fn prepare_workspace(
        mut self,
        workspace_path: &Path,
    ) -> KernelRun<WorkspaceReady> {
        self.workspace_path = Some(workspace_path.to_path_buf());
        KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: self.workspace_path,
            authorized_worker_id: None,
            worker_invocations: self.worker_invocations,
            candidate_classification: None,
            attempts: self.attempts,
            verification: None,
            final_head: None,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }
}

impl KernelRun<WorkspaceReady> {
    pub fn authorize_worker(
        mut self,
        worker_id: &str,
    ) -> KernelRun<WorkerAuthorized> {
        self.authorized_worker_id = Some(worker_id.to_string());
        KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: self.workspace_path,
            authorized_worker_id: self.authorized_worker_id,
            worker_invocations: self.worker_invocations,
            candidate_classification: None,
            attempts: self.attempts,
            verification: None,
            final_head: None,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }
}

impl KernelRun<WorkerAuthorized> {
    pub fn record_governed_candidate(
        mut self,
        candidate_sha: &str,
        worker_record: WorkerInvocationRecord,
        mutations_count: usize,
    ) -> KernelRun<CandidateProduced> {
        let parent_sha = self.starting_head.clone().unwrap_or_else(|| "UNKNOWN".into());
        let ws_id = self.workspace_path.as_ref().map(|p| p.display().to_string()).unwrap_or_default();
        
        let lineage = CandidateLineage {
            parent_baseline_sha: parent_sha,
            workspace_id: ws_id,
            worker_invocation_id: worker_record.invocation_id.clone(),
            mutations_count,
            candidate_sha: candidate_sha.to_string(),
            created_at: current_timestamp_rfc3339(),
        };

        self.worker_invocations.push(worker_record);
        self.candidate_classification = Some(CandidateClassification::Governed(GovernedCandidate { lineage }));
        self.final_head = Some(candidate_sha.to_string());

        KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: self.workspace_path,
            authorized_worker_id: self.authorized_worker_id,
            worker_invocations: self.worker_invocations,
            candidate_classification: self.candidate_classification,
            attempts: self.attempts,
            verification: None,
            final_head: self.final_head,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }

    pub fn record_external_candidate(
        mut self,
        candidate_sha: &str,
        source_note: &str,
    ) -> KernelRun<CandidateProduced> {
        self.candidate_classification = Some(CandidateClassification::External(ExternalCandidate {
            candidate_sha: candidate_sha.to_string(),
            source_note: source_note.to_string(),
        }));
        self.final_head = Some(candidate_sha.to_string());

        KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: self.workspace_path,
            authorized_worker_id: self.authorized_worker_id,
            worker_invocations: self.worker_invocations,
            candidate_classification: self.candidate_classification,
            attempts: self.attempts,
            verification: None,
            final_head: self.final_head,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }
}

impl KernelRun<CandidateProduced> {
    pub fn record_verification(
        mut self,
        verification: IndependentVerificationRecord,
    ) -> KernelRun<Verified> {
        self.verification = Some(verification);
        KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: self.workspace_path,
            authorized_worker_id: self.authorized_worker_id,
            worker_invocations: self.worker_invocations,
            candidate_classification: self.candidate_classification,
            attempts: self.attempts,
            verification: self.verification,
            final_head: self.final_head,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }
}

impl KernelRun<Verified> {
    pub fn promote_and_seal(
        self,
    ) -> (KernelRun<Promoted>, TenShadowsReceipt) {
        let is_verified = self.verification.as_ref().map(|v| v.verified_status == "PASS" && v.exit_code == 0).unwrap_or(false);
        let is_governed = self.candidate_classification.as_ref().map(|c| c.is_governed()).unwrap_or(false);
        
        let has_empirical = self.worker_invocations.iter().any(|w| {
            w.modality == EvidenceModality::Empirical && w.provider_receipt.is_some()
        });

        let final_status = if is_verified {
            RunStatus::VerifiedSuccess
        } else {
            RunStatus::Failed
        };

        let claims = DisaggregatedEpistemicClaims {
            claim_kernel_run_created: true,
            claim_kernel_routed: true,
            claim_worker_executed: !self.worker_invocations.is_empty(),
            claim_empirical_provider_invoked: has_empirical,
            claim_candidate_mutated: is_governed,
            claim_candidate_produced_under_custody: is_governed,
            claim_independently_verified: is_verified,
            claim_promoted: is_verified,
            claim_target_behaviorally_tested: is_verified,
            claim_semantic_objective_satisfied: is_verified && self.verification.as_ref().map(|v| v.verifier_type == VerificationType::IndependentSemanticFalsification).unwrap_or(false),
        };

        let cand_class = self.candidate_classification.clone().unwrap_or_else(|| {
            CandidateClassification::External(ExternalCandidate {
                candidate_sha: self.final_head.clone().unwrap_or_default(),
                source_note: "Unclassified candidate".into(),
            })
        });

        let mut receipt = TenShadowsReceipt {
            receipt_version: "3.0.0".into(),
            kernel_version: "TEN_SHADOWS_TRUSTED_KERNEL_RUST_v3".into(),
            run_id: self.run_id.clone(),
            task_id: self.task_id.clone(),
            objective: self.objective.clone(),
            objective_hash: self.objective_hash.clone(),
            target_path: self.target_path.display().to_string(),
            starting_head: self.starting_head.clone(),
            final_head: self.final_head.clone(),
            candidate_classification: cand_class,
            routing_strategy: self.strategy.clone(),
            routing_decision_digest: self.routing_digest.clone(),
            capabilities_selected: self.capabilities.clone(),
            attempts: self.attempts.clone(),
            worker_invocations: self.worker_invocations.clone(),
            artifacts_produced: Vec::new(),
            verification: self.verification.clone(),
            promotion: Some(serde_json::json!({
                "status": if is_verified { "PROMOTED" } else { "REJECTED" },
                "head": self.final_head,
            })),
            epistemic_claims: claims,
            final_status,
            created_at: self.created_at.clone(),
            sealed_at: current_timestamp_rfc3339(),
            receipt_signature: String::new(),
        };

        receipt.receipt_signature = receipt.compute_signature();

        let promoted_run = KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: self.workspace_path,
            authorized_worker_id: self.authorized_worker_id,
            worker_invocations: self.worker_invocations,
            candidate_classification: self.candidate_classification,
            attempts: self.attempts,
            verification: self.verification,
            final_head: self.final_head,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        };

        (promoted_run, receipt)
    }
}
