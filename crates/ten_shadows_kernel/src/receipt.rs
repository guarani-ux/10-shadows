//! receipt.rs — Canonical Sealed Execution Receipts and Claim Disaggregation.

use crate::candidate::CandidateClassification;
use crate::evidence::{EvidenceModality, EvidencePurpose, VerificationType};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RunStatus {
    Created,
    Routed,
    Running,
    Verifying,
    VerifiedSuccess,
    CompletedUnverified,
    Failed,
    Blocked,
    NotComputable,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RoutingStrategy {
    CodeHardening,
    GoalDecomposition,
    ZeroTrustProposalVerification,
    AdversarialAudit,
    DirectDelegation,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum WorkerRole {
    Planner,
    Builder,
    Verifier,
    Auditor,
    Decomposer,
    Delegate,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProviderExecutionReceipt {
    pub provider: String,
    pub model: String,
    pub transaction_id: String,
    pub started_at: String,
    pub ended_at: String,
    pub duration_seconds: f64,
    #[serde(default)]
    pub token_usage: BTreeMap<String, u64>,
    pub modality: EvidenceModality,
    pub raw_response_digest: String,
    pub status: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorkerInvocationRecord {
    pub invocation_id: String,
    pub worker_id: String,
    pub provider: String,
    pub model: String,
    pub role: WorkerRole,
    pub modality: EvidenceModality,
    pub input_digest: String,
    pub output_digest: String,
    pub started_at: String,
    pub ended_at: String,
    pub duration_seconds: f64,
    pub status: String,
    pub provider_receipt: Option<ProviderExecutionReceipt>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IndependentVerificationRecord {
    pub verifier_id: String,
    pub verifier_type: VerificationType,
    pub builder_id: String,
    pub modality: EvidenceModality,
    pub purpose: EvidencePurpose,
    pub test_digest: String,
    pub tests_collected: usize,
    pub tests_passed: usize,
    pub tests_failed: usize,
    pub exit_code: i32,
    pub duration_seconds: f64,
    pub falsification_attempted: bool,
    pub verified_status: String,
    pub execution_trace: Option<String>,
    pub timestamp: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionAttemptRecord {
    pub attempt_number: usize,
    pub started_at: String,
    pub ended_at: String,
    pub duration_seconds: f64,
    #[serde(default)]
    pub worker_invocations: Vec<WorkerInvocationRecord>,
    #[serde(default)]
    pub artifacts_staged: Vec<serde_json::Value>,
    pub verification: Option<IndependentVerificationRecord>,
    pub promotion_decision: String,
    pub status: String,
    pub rejection_reason: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisaggregatedEpistemicClaims {
    pub claim_kernel_run_created: bool,
    pub claim_kernel_routed: bool,
    pub claim_worker_executed: bool,
    pub claim_empirical_provider_invoked: bool,
    pub claim_candidate_mutated: bool,
    pub claim_candidate_produced_under_custody: bool,
    pub claim_independently_verified: bool,
    pub claim_promoted: bool,
    pub claim_target_behaviorally_tested: bool,
    pub claim_semantic_objective_satisfied: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TenShadowsReceipt {
    pub receipt_version: String,
    pub kernel_version: String,
    pub run_id: String,
    pub task_id: String,
    pub objective: String,
    pub objective_hash: String,
    pub target_path: String,
    pub starting_head: Option<String>,
    pub final_head: Option<String>,
    pub candidate_classification: CandidateClassification,
    pub routing_strategy: RoutingStrategy,
    pub routing_decision_digest: String,
    #[serde(default)]
    pub capabilities_selected: Vec<String>,
    #[serde(default)]
    pub attempts: Vec<ExecutionAttemptRecord>,
    #[serde(default)]
    pub worker_invocations: Vec<WorkerInvocationRecord>,
    #[serde(default)]
    pub artifacts_produced: Vec<serde_json::Value>,
    pub verification: Option<IndependentVerificationRecord>,
    pub promotion: Option<serde_json::Value>,
    pub epistemic_claims: DisaggregatedEpistemicClaims,
    pub final_status: RunStatus,
    pub created_at: String,
    pub sealed_at: String,
    pub receipt_signature: String,
}

impl TenShadowsReceipt {
    pub fn compute_signature_for_data(data: &serde_json::Value) -> String {
        let mut obj = data.clone();
        if let Some(map) = obj.as_object_mut() {
            map.remove("receipt_signature");
        }
        let canonical_str = serde_json::to_string(&obj).unwrap_or_default();
        let mut hasher = Sha256::new();
        hasher.update(canonical_str.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn compute_signature(&self) -> String {
        let val = serde_json::to_value(self).unwrap_or(serde_json::Value::Null);
        Self::compute_signature_for_data(&val)
    }

    pub fn is_signature_valid(&self) -> bool {
        self.receipt_signature == self.compute_signature()
    }
}
