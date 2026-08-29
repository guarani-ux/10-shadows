//! constitution.rs — Constitutional Ontology, Obligation Semantics, and Objective Sufficiency for Ten Shadows.
//!
//! Enforces:
//! - LAW 6 — SUFFICIENCY / OBJECTIVE SATISFACTION:
//!   No higher-order conclusion (such as objective accomplishment) may become authoritative
//!   solely from the local success of its components. An explicit, qualified sufficiency
//!   evaluation over verified satisfaction obligations must authorize that conclusion.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashSet;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ObligationStatus {
    Unresolved,
    Satisfied,
    Falsified,
    Inapplicable,
    Contested,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Obligation {
    pub obligation_id: String,
    pub description: String,
    pub required_effect: String,
    pub is_mandatory: bool,
    pub satisfaction_status: ObligationStatus,
    pub bound_evidence_digest: Option<String>,
    pub rationale: Option<String>,
}

impl Obligation {
    pub fn new(
        obligation_id: &str,
        description: &str,
        required_effect: &str,
        is_mandatory: bool,
    ) -> Self {
        Self {
            obligation_id: obligation_id.to_string(),
            description: description.to_string(),
            required_effect: required_effect.to_string(),
            is_mandatory,
            satisfaction_status: ObligationStatus::Unresolved,
            bound_evidence_digest: None,
            rationale: None,
        }
    }

    pub fn satisfy(&mut self, evidence_digest: &str, rationale: &str) {
        self.satisfaction_status = ObligationStatus::Satisfied;
        self.bound_evidence_digest = Some(evidence_digest.to_string());
        self.rationale = Some(rationale.to_string());
    }

    pub fn falsify(&mut self, reason: &str) {
        self.satisfaction_status = ObligationStatus::Falsified;
        self.rationale = Some(reason.to_string());
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", content = "details")]
pub enum SufficiencyRule {
    AllMandatory,
    AnyOf(Vec<String>),
    Custom(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectiveContract {
    pub objective_id: String,
    pub canonical_intent: String,
    pub intent_hash: String,
    pub obligations: Vec<Obligation>,
    pub sufficiency_rule: SufficiencyRule,
}

impl ObjectiveContract {
    pub fn new(
        objective_id: &str,
        canonical_intent: &str,
        obligations: Vec<Obligation>,
        sufficiency_rule: SufficiencyRule,
    ) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(canonical_intent.as_bytes());
        let intent_hash = format!("{:x}", hasher.finalize());

        Self {
            objective_id: objective_id.to_string(),
            canonical_intent: canonical_intent.to_string(),
            intent_hash,
            obligations,
            sufficiency_rule,
        }
    }

    /// Evaluates whether the current obligations satisfy the objective under Law 6.
    pub fn evaluate_sufficiency(&self) -> ObjectiveSufficiencyProof {
        let mut satisfied_ids = HashSet::new();
        let mut unresolved_mandatory = Vec::new();
        let mut falsified_mandatory = Vec::new();

        // INVARIANT: An empty obligation set on a non-trivial objective CAN NEVER be sufficient!
        if self.obligations.is_empty() {
            if !self.canonical_intent.trim().is_empty() {
                unresolved_mandatory.push("INSUFFICIENT_REQUIREMENTS_EMPTY_SET".to_string());
            }
            let mut hasher = Sha256::new();
            hasher.update(
                format!(
                    "{}:{:?}:false:empty_obligations",
                    self.objective_id, self.sufficiency_rule
                )
                .as_bytes(),
            );
            let proof_digest = format!("{:x}", hasher.finalize());

            return ObjectiveSufficiencyProof {
                objective_id: self.objective_id.clone(),
                is_satisfied: false,
                satisfied_obligations: vec![],
                unresolved_mandatory,
                falsified_mandatory: vec![],
                proof_digest,
            };
        }

        for ob in &self.obligations {
            match ob.satisfaction_status {
                ObligationStatus::Satisfied => {
                    satisfied_ids.insert(ob.obligation_id.clone());
                }
                ObligationStatus::Falsified => {
                    if ob.is_mandatory {
                        falsified_mandatory.push(ob.obligation_id.clone());
                    }
                }
                ObligationStatus::Unresolved | ObligationStatus::Contested => {
                    if ob.is_mandatory {
                        unresolved_mandatory.push(ob.obligation_id.clone());
                    }
                }
                ObligationStatus::Inapplicable => {}
            }
        }

        let is_sufficient = if !falsified_mandatory.is_empty() {
            false
        } else {
            match &self.sufficiency_rule {
                SufficiencyRule::AllMandatory => {
                    unresolved_mandatory.is_empty() && !satisfied_ids.is_empty()
                }
                SufficiencyRule::AnyOf(ids) => {
                    let has_match = ids.iter().any(|id| satisfied_ids.contains(id));
                    has_match && unresolved_mandatory.is_empty()
                }
                SufficiencyRule::Custom(_) => {
                    unresolved_mandatory.is_empty() && !satisfied_ids.is_empty()
                }
            }
        };

        let mut hasher = Sha256::new();
        hasher.update(
            format!(
                "{}:{:?}:{}",
                self.objective_id, self.sufficiency_rule, is_sufficient
            )
            .as_bytes(),
        );
        let proof_digest = format!("{:x}", hasher.finalize());

        ObjectiveSufficiencyProof {
            objective_id: self.objective_id.clone(),
            is_satisfied: is_sufficient,
            satisfied_obligations: satisfied_ids.into_iter().collect(),
            unresolved_mandatory,
            falsified_mandatory,
            proof_digest,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObjectiveSufficiencyProof {
    pub objective_id: String,
    pub is_satisfied: bool,
    pub satisfied_obligations: Vec<String>,
    pub unresolved_mandatory: Vec<String>,
    pub falsified_mandatory: Vec<String>,
    pub proof_digest: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EvidenceEntailment {
    pub evidence_digest: String,
    pub target_obligation_id: String,
    pub tested_effect: String,
    pub is_applicable: bool,
    pub justification: String,
}

impl EvidenceEntailment {
    pub fn verify_entailment(
        evidence_digest: &str,
        obligation: &Obligation,
        tested_effect: &str,
    ) -> Self {
        // Strict Entailment Check: Tested effect must match required effect and evidence digest must be valid
        let is_applicable = !evidence_digest.trim().is_empty()
            && tested_effect
                .trim()
                .eq_ignore_ascii_case(obligation.required_effect.trim());
        let justification = if is_applicable {
            format!(
                "Evidence '{}' directly tests required effect '{}'",
                evidence_digest, obligation.required_effect
            )
        } else {
            format!("Irrelevant Evidence: Tested effect '{}' does not fulfill required obligation effect '{}'", tested_effect, obligation.required_effect)
        };

        Self {
            evidence_digest: evidence_digest.to_string(),
            target_obligation_id: obligation.obligation_id.clone(),
            tested_effect: tested_effect.to_string(),
            is_applicable,
            justification,
        }
    }
}
