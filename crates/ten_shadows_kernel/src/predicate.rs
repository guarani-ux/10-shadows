//! predicate.rs — Authoritative Execution and Production Predicates.
//!
//! Enforces:
//! 1. `is_ten_shadows_execution`: Verifies that the run was lawfully governed.
//! 2. `is_ten_shadows_production`: Verifies that the candidate code was ACTUALLY produced
//!    under Ten Shadows run custody (not imported, post-hoc audited, or external).

use crate::candidate::CandidateClassification;
use crate::db::KernelDb;
use crate::evidence::{EvidenceModality, VerificationType};
use crate::receipt::{RunStatus, TenShadowsReceipt};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerificationReport {
    pub is_execution_valid: bool,
    pub is_production_valid: bool,
    pub errors: Vec<String>,
}

pub fn evaluate_receipt(
    receipt: &TenShadowsReceipt,
    db: Option<&KernelDb>,
) -> VerificationReport {
    let mut errors = Vec::new();

    // 1. Cryptographic Signature Verification
    if !receipt.is_signature_valid() {
        errors.push(format!(
            "Receipt signature mismatch: computed '{}', found '{}' (Tampered or forged receipt).",
            receipt.compute_signature(),
            receipt.receipt_signature
        ));
    }

    // 2. Database Anchor Check (if connection provided)
    if let Some(kernel_db) = db {
        if kernel_db.has_run(&receipt.run_id) {
            if let Some(db_hash) = kernel_db.get_run_objective_hash(&receipt.run_id) {
                if db_hash != receipt.objective_hash {
                    errors.push(format!(
                        "Objective hash mismatch: receipt='{}', db='{}'.",
                        receipt.objective_hash, db_hash
                    ));
                }
            }
        } else {
            errors.push(format!(
                "Run '{}' does not exist in authoritative KernelDatabase (Unanchored receipt).",
                receipt.run_id
            ));
        }
    }

    // 3. Verification Independence
    if let Some(ref v) = receipt.verification {
        if v.builder_id == v.verifier_id {
            errors.push(format!(
                "Verification Independence Violation: builder_id '{}' is identical to verifier_id '{}'.",
                v.builder_id, v.verifier_id
            ));
        }
        if receipt.final_status == RunStatus::VerifiedSuccess {
            if v.exit_code != 0 || v.tests_passed == 0 || v.verified_status != "PASS" {
                errors.push(format!(
                    "Invalid VERIFIED_SUCCESS: exit_code={}, passed={}, status='{}'.",
                    v.exit_code, v.tests_passed, v.verified_status
                ));
            }
            if v.verifier_type == VerificationType::BuilderTest {
                errors.push("BUILDER_TEST evidence is insufficient for consequential VERIFIED_SUCCESS.".into());
            }
        }
    } else if receipt.final_status == RunStatus::VerifiedSuccess {
        errors.push("Consequential VERIFIED_SUCCESS status requires independent verification evidence.".into());
    }

    // 4. Empirical Worker Verification
    for w in &receipt.worker_invocations {
        if w.modality == EvidenceModality::Empirical {
            if let Some(ref pr) = w.provider_receipt {
                if pr.duration_seconds <= 0.0 || pr.transaction_id.is_empty() {
                    errors.push(format!("Worker '{}' has invalid empirical receipt details.", w.worker_id));
                }
            } else {
                errors.push(format!("Worker '{}' claims EMPIRICAL modality but missing provider_receipt.", w.worker_id));
            }
        }
    }

    let is_execution_valid = errors.is_empty();

    // 5. Strict Production Custody Checks (is_ten_shadows_production)
    let mut prod_errors = Vec::new();
    if !is_execution_valid {
        prod_errors.push("Execution validity failed.".into());
    }

    if receipt.final_status != RunStatus::VerifiedSuccess {
        prod_errors.push(format!(
            "Run status is '{:?}' (not VERIFIED_SUCCESS). Candidate is unpromoted or failed.",
            receipt.final_status
        ));
    }

    if !receipt.epistemic_claims.claim_promoted {
        prod_errors.push("Epistemic claims indicate candidate was NOT promoted.".into());
    }

    match &receipt.candidate_classification {
        CandidateClassification::Governed(g) => {
            if !receipt.epistemic_claims.claim_candidate_produced_under_custody {
                prod_errors.push("Epistemic claims do not assert candidate was produced under custody.".into());
            }
            if let Some(ref start) = receipt.starting_head {
                if g.lineage.parent_baseline_sha != *start {
                    prod_errors.push(format!(
                        "Lineage baseline mismatch: lineage='{}', starting_head='{}'.",
                        g.lineage.parent_baseline_sha, start
                    ));
                }
            }
            if let Some(ref fin) = receipt.final_head {
                if g.lineage.candidate_sha != *fin {
                    prod_errors.push(format!(
                        "Lineage candidate mismatch: lineage='{}', final_head='{}'.",
                        g.lineage.candidate_sha, fin
                    ));
                }
            }
        }
        CandidateClassification::External(e) => {
            prod_errors.push(format!(
                "Candidate was NOT produced under Ten Shadows custody (ExternalCandidate: sha='{}', note='{}').",
                e.candidate_sha, e.source_note
            ));
        }
    }

    let is_production_valid = is_execution_valid && prod_errors.is_empty();
    errors.extend(prod_errors);

    VerificationReport {
        is_execution_valid,
        is_production_valid,
        errors,
    }
}
