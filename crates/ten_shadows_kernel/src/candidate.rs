//! candidate.rs — Typed Candidate Classifications & Lineage Custody.
//!
//! Mechanically separates Governed Candidates from External Candidates.

use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CandidateLineage {
    pub parent_baseline_sha: String,
    pub workspace_id: String,
    pub worker_invocation_id: String,
    pub mutations_count: usize,
    pub candidate_sha: String,
    pub created_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GovernedCandidate {
    pub lineage: CandidateLineage,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExternalCandidate {
    pub candidate_sha: String,
    pub source_note: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", content = "details")]
pub enum CandidateClassification {
    Governed(GovernedCandidate),
    External(ExternalCandidate),
}

impl CandidateClassification {
    pub fn is_governed(&self) -> bool {
        matches!(self, CandidateClassification::Governed(_))
    }

    pub fn candidate_sha(&self) -> &str {
        match self {
            CandidateClassification::Governed(g) => &g.lineage.candidate_sha,
            CandidateClassification::External(e) => &e.candidate_sha,
        }
    }
}

impl fmt::Display for CandidateClassification {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CandidateClassification::Governed(g) => {
                write!(
                    f,
                    "GovernedCandidate(sha={}, parent={}, worker={})",
                    g.lineage.candidate_sha,
                    g.lineage.parent_baseline_sha,
                    g.lineage.worker_invocation_id
                )
            }
            CandidateClassification::External(e) => {
                write!(
                    f,
                    "ExternalCandidate(sha={}, note={})",
                    e.candidate_sha, e.source_note
                )
            }
        }
    }
}
