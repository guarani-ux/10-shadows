//! state_machine.rs — Compile-Time Typestate State Machine for Ten Shadows Kernel.
//!
//! Enforces that illegal lifecycle transitions are mathematically unrepresentable.

use crate::candidate::{CandidateClassification, CandidateLineage, ExternalCandidate, GovernedCandidate};
use crate::dispatcher::{WorkerAuthorization, WorkerDispatcher};
use crate::evidence::{EvidenceModality, VerificationType};
use crate::receipt::{
    DisaggregatedEpistemicClaims, ExecutionAttemptRecord, IndependentVerificationRecord,
    ProviderExecutionReceipt, RoutingStrategy, RunStatus, TenShadowsReceipt, WorkerInvocationRecord, WorkerRole,
};
use crate::repository::{AuthoritativeSource, GovernedWorkspace, RepositoryRoleError};
use crate::time_utils::current_timestamp_rfc3339;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::process::Command;
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
    pub governed_workspace: Option<GovernedWorkspace>,
    pub authorized_worker_id: Option<String>,
    pub current_attempt: usize,
    pub last_failure_evidence: Option<String>,
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
            governed_workspace: None,
            authorized_worker_id: None,
            current_attempt: 1,
            last_failure_evidence: None,
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
            governed_workspace: None,
            authorized_worker_id: None,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
    /// Creates a run-owned, isolated ephemeral GovernedWorkspace from baseline SHA.
    pub fn prepare_governed_workspace(
        self,
        worktrees_dir: Option<&Path>,
    ) -> Result<KernelRun<WorkspaceReady>, RepositoryRoleError> {
        let baseline_sha = self.starting_head.as_ref().ok_or_else(|| {
            RepositoryRoleError::InvalidGitRepository("Baseline commit SHA missing for governed workspace".into())
        })?;

        let source = AuthoritativeSource::new(&self.target_path)?;
        let ws = GovernedWorkspace::create_ephemeral(&self.run_id, &source, baseline_sha, worktrees_dir)?;
        let ws_path = ws.workspace_root.clone();

        Ok(KernelRun {
            run_id: self.run_id,
            task_id: self.task_id,
            objective: self.objective,
            objective_hash: self.objective_hash,
            target_path: self.target_path,
            strategy: self.strategy,
            capabilities: self.capabilities,
            routing_digest: self.routing_digest,
            starting_head: self.starting_head,
            workspace_path: Some(ws_path),
            governed_workspace: Some(ws),
            authorized_worker_id: None,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
            worker_invocations: self.worker_invocations,
            candidate_classification: None,
            attempts: self.attempts,
            verification: None,
            final_head: None,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        })
    }

    /// Sets up a read-only audit workspace for an external target.
    pub fn prepare_audit_workspace(
        mut self,
        target_path: &Path,
    ) -> KernelRun<WorkspaceReady> {
        self.workspace_path = Some(target_path.to_path_buf());
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
            governed_workspace: None,
            authorized_worker_id: None,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
            governed_workspace: self.governed_workspace,
            authorized_worker_id: self.authorized_worker_id,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
    /// Dispatches the authorized worker through the language-neutral WorkerDispatcher.
    pub fn dispatch_and_produce_candidate(
        mut self,
        requested_provider: &str,
        requested_model: &str,
        python_executable: Option<&str>,
    ) -> Result<KernelRun<CandidateProduced>, Box<dyn std::error::Error>> {
        let ws_path = self.workspace_path.as_ref().ok_or("Workspace path missing")?;
        let worker_id = self.authorized_worker_id.as_deref().unwrap_or("worker_default");
        let invocation_id = format!("inv_{}_{}", self.task_id, self.current_attempt);
        let baseline = self.starting_head.as_deref().unwrap_or("UNKNOWN_BASELINE");
        let authorized_at = current_timestamp_rfc3339();

        let auth = WorkerAuthorization::new(
            &self.run_id,
            &self.task_id,
            &invocation_id,
            worker_id,
            "Builder",
            &self.objective,
            &self.objective_hash,
            baseline,
            ws_path,
            requested_provider,
            requested_model,
            self.current_attempt,
            self.last_failure_evidence.clone(),
            &authorized_at,
        );

        let dispatch_res = WorkerDispatcher::dispatch(&auth, python_executable)?;

        let modality = match dispatch_res.modality.as_str() {
            "Empirical" => EvidenceModality::Empirical,
            "Simulated" => EvidenceModality::Simulated,
            "DeterministicTest" => EvidenceModality::DeterministicTest,
            _ => EvidenceModality::Structural,
        };

        let prov_receipt = dispatch_res.provider_receipt.and_then(|pr| {
            serde_json::from_value::<ProviderExecutionReceipt>(pr).ok()
        });

        let worker_rec = WorkerInvocationRecord {
            invocation_id: dispatch_res.invocation_id.clone(),
            worker_id: dispatch_res.worker_id.clone(),
            provider: dispatch_res.resolved_provider.clone(),
            model: dispatch_res.resolved_model.clone(),
            role: WorkerRole::Builder,
            modality,
            input_digest: self.objective_hash.clone(),
            output_digest: dispatch_res.output_digest.clone(),
            started_at: dispatch_res.started_at,
            ended_at: dispatch_res.ended_at,
            duration_seconds: dispatch_res.duration_seconds,
            status: dispatch_res.exit_status.clone(),
            provider_receipt: prov_receipt,
        };

        let candidate_sha = dispatch_res.workspace_after_sha.clone();
        let is_mutated = candidate_sha != baseline && dispatch_res.exit_status == "SUCCESS";

        let run_cand = if is_mutated && self.governed_workspace.is_some() {
            self.record_governed_candidate(&candidate_sha, worker_rec, dispatch_res.files_changed.len())
        } else {
            self.worker_invocations.push(worker_rec);
            self.record_external_candidate(&candidate_sha, "Worker execution produced zero valid governed mutations")
        };

        Ok(run_cand)
    }

    pub fn record_governed_candidate(
        mut self,
        candidate_sha: &str,
        worker_record: WorkerInvocationRecord,
        mutations_count: usize,
    ) -> KernelRun<CandidateProduced> {
        let parent_sha = self.starting_head.clone().unwrap_or_else(|| "UNKNOWN".into());
        let ws_id = self.workspace_path.as_ref().map(|p| p.display().to_string()).unwrap_or_default();
        
        let is_valid_governed = mutations_count > 0 
            && candidate_sha != parent_sha 
            && self.governed_workspace.is_some()
            && self.authorized_worker_id.is_some();

        if is_valid_governed {
            let lineage = CandidateLineage {
                parent_baseline_sha: parent_sha,
                workspace_id: ws_id,
                worker_invocation_id: worker_record.invocation_id.clone(),
                mutations_count,
                candidate_sha: candidate_sha.to_string(),
                created_at: current_timestamp_rfc3339(),
            };
            self.candidate_classification = Some(CandidateClassification::Governed(GovernedCandidate { lineage }));
        } else {
            self.candidate_classification = Some(CandidateClassification::External(ExternalCandidate {
                candidate_sha: candidate_sha.to_string(),
                source_note: if candidate_sha == parent_sha {
                    "Zero mutations produced: Candidate SHA is identical to starting baseline".into()
                } else if self.governed_workspace.is_none() {
                    "Candidate produced outside isolated GovernedWorkspace".into()
                } else {
                    "Invalid governed production parameters".into()
                },
            }));
        }

        self.worker_invocations.push(worker_record);
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
            governed_workspace: self.governed_workspace,
            authorized_worker_id: self.authorized_worker_id,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
            governed_workspace: self.governed_workspace,
            authorized_worker_id: self.authorized_worker_id,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
            governed_workspace: self.governed_workspace,
            authorized_worker_id: self.authorized_worker_id,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
    /// Governed repair transition: records failed attempt and transitions back to WorkerAuthorized.
    pub fn retry_repair(
        mut self,
        failure_evidence: &str,
    ) -> KernelRun<WorkerAuthorized> {
        let attempt_rec = ExecutionAttemptRecord {
            attempt_number: self.current_attempt,
            started_at: self.created_at.clone(),
            ended_at: current_timestamp_rfc3339(),
            duration_seconds: 0.1,
            worker_invocations: self.worker_invocations.clone(),
            artifacts_staged: Vec::new(),
            verification: self.verification.clone(),
            promotion_decision: "REJECTED_NEEDS_REPAIR".into(),
            status: "FAILED_ATTEMPT".into(),
            rejection_reason: Some(failure_evidence.to_string()),
        };
        self.attempts.push(attempt_rec);
        self.current_attempt += 1;
        self.last_failure_evidence = Some(failure_evidence.to_string());

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
            governed_workspace: self.governed_workspace,
            authorized_worker_id: self.authorized_worker_id,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
            worker_invocations: self.worker_invocations,
            candidate_classification: None,
            attempts: self.attempts,
            verification: None,
            final_head: None,
            created_at: self.created_at,
            state_marker: std::marker::PhantomData,
        }
    }

    pub fn promote_and_seal(
        mut self,
    ) -> (KernelRun<Promoted>, TenShadowsReceipt) {
        let is_verified = self.verification.as_ref().map(|v| v.verified_status == "PASS" && v.exit_code == 0).unwrap_or(false);
        let is_governed = self.candidate_classification.as_ref().map(|c| c.is_governed()).unwrap_or(false);
        
        let has_empirical = self.worker_invocations.iter().any(|w| {
            w.modality == EvidenceModality::Empirical && w.provider_receipt.is_some()
        });

        // Invariant: Divergence check before promotion on authoritative source
        let mut promotion_succeeded = false;
        let mut rejection_reason = None;

        if is_verified && is_governed {
            if let Some(ref ws) = self.governed_workspace {
                let current_source_head = AuthoritativeSource::new(&self.target_path)
                    .ok()
                    .and_then(|s| s.capture_head());

                if let (Some(ref cur), Some(ref start)) = (current_source_head.as_ref(), self.starting_head.as_ref()) {
                    if cur != start {
                        rejection_reason = Some(format!(
                            "Authoritative source diverged before promotion (expected '{}', found '{}').",
                            start, cur
                        ));
                    } else {
                        // Atomic promotion: Merge branch back to source
                        let merge_out = Command::new("git")
                            .args(["merge", "--ff-only", &ws.branch_name])
                            .current_dir(&self.target_path)
                            .output();

                        match merge_out {
                            Ok(o) if o.status.success() => {
                                promotion_succeeded = true;
                            }
                            _ => {
                                rejection_reason = Some("Git fast-forward merge failed during promotion.".into());
                            }
                        }
                    }
                }
            } else {
                // Non-worktree governed run
                promotion_succeeded = true;
            }
        }

        let final_status = if is_verified && is_governed && promotion_succeeded {
            RunStatus::VerifiedSuccess
        } else if is_verified && !is_governed {
            RunStatus::ExternalAuditVerified
        } else {
            RunStatus::Failed
        };

        let claims = DisaggregatedEpistemicClaims {
            claim_kernel_run_created: true,
            claim_kernel_routed: true,
            claim_worker_executed: !self.worker_invocations.is_empty(),
            claim_empirical_provider_invoked: has_empirical,
            claim_candidate_mutated: is_governed && promotion_succeeded,
            claim_candidate_produced_under_custody: is_governed && promotion_succeeded,
            claim_independently_verified: is_verified,
            claim_promoted: promotion_succeeded,
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
                "status": if promotion_succeeded { "PROMOTED" } else { "REJECTED" },
                "head": self.final_head,
                "rejection_reason": rejection_reason,
            })),
            epistemic_claims: claims,
            final_status,
            created_at: self.created_at.clone(),
            sealed_at: current_timestamp_rfc3339(),
            receipt_signature: String::new(),
        };

        receipt.receipt_signature = receipt.compute_signature();

        // Destroy governed workspace after promotion
        if let Some(ws) = self.governed_workspace.take() {
            ws.destroy();
        }

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
            governed_workspace: None,
            authorized_worker_id: self.authorized_worker_id,
            current_attempt: self.current_attempt,
            last_failure_evidence: self.last_failure_evidence,
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
