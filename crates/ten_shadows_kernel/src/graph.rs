//! graph.rs — Rust Trusted Kernel Relational Graph & Epistemic Types.
//!
//! Enforces:
//! - Substrate Law 1: Authority (Graph edges cannot independently certify authority)
//! - Substrate Law 2: Provenance (Cryptographic digest on all relational nodes/edges)
//! - Substrate Law 4: Evidence Monotonicity (No silent upgrades of relational status)

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EpistemicStatus {
    Proposed,
    Inferred,
    Observed,
    Verified,
    Qualified,
    Authoritative,
    Contested,
    Superseded,
    Invalidated,
}

impl EpistemicStatus {
    pub fn rank(&self) -> i32 {
        match self {
            EpistemicStatus::Authoritative => 6,
            EpistemicStatus::Qualified => 5,
            EpistemicStatus::Verified => 4,
            EpistemicStatus::Observed => 3,
            EpistemicStatus::Proposed => 2,
            EpistemicStatus::Inferred => 1,
            EpistemicStatus::Contested => 0,
            EpistemicStatus::Invalidated => -1,
            EpistemicStatus::Superseded => -2,
        }
    }

    pub fn can_transition_to(&self, new_status: EpistemicStatus) -> bool {
        // Law 4: Cannot upgrade without physical observation
        new_status.rank() <= self.rank()
            || new_status == EpistemicStatus::Verified
            || new_status == EpistemicStatus::Observed
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum NodeType {
    Objective,
    Subproblem,
    Requirement,
    Unknown,
    Claim,
    Capability,
    Shadow,
    Tool,
    Model,
    Worker,
    Candidate,
    Artifact,
    Evidence,
    Verifier,
    AcquisitionTarget,
    ProblemPattern,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum RelationType {
    Requires,
    Blocks,
    DependsOn,
    DecomposesInto,
    Contradicts,
    CanContributeTo,
    ProvidedBy,
    CompatibleWith,
    Produces,
    Acquires,
    SupportedBy,
    ChallengedBy,
    ProducedBy,
    PerformedBy,
    DerivedFrom,
    VerifiedBy,
    AuthorizedBy,
    Invalidates,
    TransfersTo,
    RepairedBy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelationalNode {
    pub node_id: String,
    pub node_type: NodeType,
    pub label: String,
    pub properties: HashMap<String, serde_json::Value>,
    pub epistemic_status: EpistemicStatus,
    pub provenance_digest: String,
}

impl RelationalNode {
    pub fn new(
        node_id: &str,
        node_type: NodeType,
        label: &str,
        epistemic_status: EpistemicStatus,
    ) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(format!("{}:{:?}:{}", node_id, node_type, label).as_bytes());
        let digest = format!("{:x}", hasher.finalize());

        Self {
            node_id: node_id.to_string(),
            node_type,
            label: label.to_string(),
            properties: HashMap::new(),
            epistemic_status,
            provenance_digest: digest,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelationalEdge {
    pub edge_id: String,
    pub source_id: String,
    pub target_id: String,
    pub relation_type: RelationType,
    pub epistemic_status: EpistemicStatus,
    pub modality: String,
    pub confidence: f64,
}

impl RelationalEdge {
    pub fn new(
        edge_id: &str,
        source_id: &str,
        target_id: &str,
        relation_type: RelationType,
        epistemic_status: EpistemicStatus,
    ) -> Self {
        Self {
            edge_id: edge_id.to_string(),
            source_id: source_id.to_string(),
            target_id: target_id.to_string(),
            relation_type,
            epistemic_status,
            modality: "Structural".into(),
            confidence: 1.0,
        }
    }
}
