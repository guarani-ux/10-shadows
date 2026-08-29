//! evidence.rs — Evidence Modality, Purpose, and Substrate Laws for 10 SHADOWS.
//!
//! Enforces the Four Substrate Laws:
//! LAW 1 — AUTHORITY: Only mechanically privileged components create authoritative state.
//! LAW 2 — PROVENANCE: Every consequential claim retains an unbroken causal chain.
//! LAW 3 — INDEPENDENCE: The causal path producing a candidate cannot certify that candidate.
//! LAW 4 — EVIDENCE MONOTONICITY: Weaker evidence modalities cannot silently become stronger modalities.

use serde::{Deserialize, Serialize};
use std::error::Error;
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EvidenceModality {
    Simulated = 1,
    Structural = 2,
    DeterministicTest = 3,
    Integration = 4,
    Empirical = 5,
}

impl fmt::Display for EvidenceModality {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EvidenceModality::Simulated => write!(f, "SIMULATED"),
            EvidenceModality::Structural => write!(f, "STRUCTURAL"),
            EvidenceModality::DeterministicTest => write!(f, "DETERMINISTIC_TEST"),
            EvidenceModality::Integration => write!(f, "INTEGRATION"),
            EvidenceModality::Empirical => write!(f, "EMPIRICAL"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum EvidencePurpose {
    Execution,
    Integrity,
    Provenance,
    BehavioralVerification,
    SemanticVerification,
    Promotion,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum VerificationType {
    BuilderTest,
    IndependentBehavioralOracle,
    IndependentSemanticFalsification,
    StaticAnalysisGuard,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SubstrateLawError {
    AuthorityViolation(String),
    ProvenanceViolation(String),
    IndependenceViolation(String),
    MonotonicityViolation(String),
}

impl fmt::Display for SubstrateLawError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SubstrateLawError::AuthorityViolation(s) => {
                write!(f, "LAW 1 (AUTHORITY) VIOLATION: {}", s)
            }
            SubstrateLawError::ProvenanceViolation(s) => {
                write!(f, "LAW 2 (PROVENANCE) VIOLATION: {}", s)
            }
            SubstrateLawError::IndependenceViolation(s) => {
                write!(f, "LAW 3 (INDEPENDENCE) VIOLATION: {}", s)
            }
            SubstrateLawError::MonotonicityViolation(s) => {
                write!(f, "LAW 4 (MONOTONICITY) VIOLATION: {}", s)
            }
        }
    }
}

impl Error for SubstrateLawError {}

/// Enforces Law 4: Evidence Monotonicity.
/// A weaker modality must NEVER silently become a stronger modality.
pub fn assert_evidence_monotonicity(
    declared: EvidenceModality,
    claimed: EvidenceModality,
) -> Result<(), SubstrateLawError> {
    if (claimed as u8) > (declared as u8) {
        Err(SubstrateLawError::MonotonicityViolation(format!(
            "Attempted illegal upgrade from '{}' to '{}'.",
            declared, claimed
        )))
    } else {
        Ok(())
    }
}
