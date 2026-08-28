//! adversarial_authority_tests.rs — 10 Complete Adversarial Authority Tests for Ten Shadows Kernel.

use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use ten_shadows_kernel::candidate::{CandidateClassification, CandidateLineage, ExternalCandidate, GovernedCandidate};
use ten_shadows_kernel::current_timestamp_rfc3339;
use ten_shadows_kernel::db::KernelDb;
use ten_shadows_kernel::evidence::{
    assert_evidence_monotonicity, EvidenceModality, EvidencePurpose, SubstrateLawError,
    VerificationType,
};
use ten_shadows_kernel::predicate::evaluate_receipt;
use ten_shadows_kernel::receipt::{
    DisaggregatedEpistemicClaims, IndependentVerificationRecord, RoutingStrategy, RunStatus,
    TenShadowsReceipt, WorkerInvocationRecord, WorkerRole,
};
use ten_shadows_kernel::state_machine::KernelRun;

fn create_test_dir(name: &str) -> PathBuf {
    let millis = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
    let dir = std::env::temp_dir().join(format!("ts_adv_test_{}_{}", name, millis));
    fs::create_dir_all(&dir).unwrap();
    dir
}

/// TEST 1: Post-Hoc Candidate (Audited after the fact) must NOT qualify as Ten Shadows produced.
#[test]
fn test_01_post_hoc_candidate_fails_production_custody() {
    let tmp = create_test_dir("post_hoc");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run = KernelRun::new("Audit external codebase", &target, None);
    let run_id = run.run_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &run.task_id, &obj_hash, "baseline_sha_123").unwrap();

    let run_base = run.capture_baseline(Some("baseline_sha_123".into()));
    let run_ws = run_base.prepare_workspace(&target);
    let run_auth = run_ws.authorize_worker("auditor_01");

    // External candidate recorded (post-hoc audit)
    let run_cand = run_auth.record_external_candidate("ext_candidate_456", "External candidate audited post-hoc");

    let verifier_rec = IndependentVerificationRecord {
        verifier_id: "svris_verifier_01".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "auditor_01".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "digest_123".into(),
        tests_collected: 10,
        tests_passed: 10,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.1,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: None,
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(verifier_rec);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid, "Audit receipt itself is valid execution record");
    assert!(!report.is_production_valid, "External candidate must NOT qualify as Ten Shadows produced");
    assert!(report.errors.iter().any(|e| e.contains("Candidate was NOT produced under Ten Shadows custody")));
}

/// TEST 2: Fake receipt without database anchor must fail execution validity.
#[test]
fn test_02_fake_receipt_unanchored_fails() {
    let tmp = create_test_dir("fake_receipt");
    let db = KernelDb::open(&tmp).unwrap();

    let fake_receipt = TenShadowsReceipt {
        receipt_version: "3.0.0".into(),
        kernel_version: "TEN_SHADOWS_TRUSTED_KERNEL_RUST_v3".into(),
        run_id: "TS-UNANCHORED-FAKE-001".into(),
        task_id: "task_fake".into(),
        objective: "Fake run".into(),
        objective_hash: "0".repeat(64),
        target_path: "C:\\fake".into(),
        starting_head: None,
        final_head: None,
        candidate_classification: CandidateClassification::External(ExternalCandidate {
            candidate_sha: "fake_sha".into(),
            source_note: "Fake".into(),
        }),
        routing_strategy: RoutingStrategy::DirectDelegation,
        routing_decision_digest: "1".repeat(64),
        capabilities_selected: vec![],
        attempts: vec![],
        worker_invocations: vec![],
        artifacts_produced: vec![],
        verification: None,
        promotion: None,
        epistemic_claims: DisaggregatedEpistemicClaims {
            claim_kernel_run_created: true,
            claim_kernel_routed: true,
            claim_worker_executed: false,
            claim_empirical_provider_invoked: false,
            claim_candidate_mutated: false,
            claim_candidate_produced_under_custody: false,
            claim_independently_verified: false,
            claim_promoted: false,
            claim_target_behaviorally_tested: false,
            claim_semantic_objective_satisfied: false,
        },
        final_status: RunStatus::CompletedUnverified,
        created_at: current_timestamp_rfc3339(),
        sealed_at: current_timestamp_rfc3339(),
        receipt_signature: "invalid_signature".into(),
    };

    let report = evaluate_receipt(&fake_receipt, Some(&db));
    assert!(!report.is_execution_valid);
    assert!(!report.is_production_valid);
    assert!(report.errors.iter().any(|e| e.contains("signature mismatch")));
    assert!(report.errors.iter().any(|e| e.contains("does not exist in authoritative KernelDatabase")));
}

/// TEST 3: Self-certification (builder_id == verifier_id) must be rejected.
#[test]
fn test_03_self_certification_rejected() {
    let tmp = create_test_dir("self_cert");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run = KernelRun::new("Test self certification", &target, None);
    let run_id = run.run_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &run.task_id, &obj_hash, "base_sha").unwrap();

    let run_base = run.capture_baseline(Some("base_sha".into()));
    let run_ws = run_base.prepare_workspace(&target);
    let run_auth = run_ws.authorize_worker("builder_alpha");

    let worker_rec = WorkerInvocationRecord {
        invocation_id: "inv_1".into(),
        worker_id: "builder_alpha".into(),
        provider: "gemini".into(),
        model: "gemini-2.5-flash".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Structural,
        input_digest: obj_hash.clone(),
        output_digest: "out_digest".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    let run_cand = run_auth.record_governed_candidate("cand_sha_99", worker_rec, 1);

    let self_ver = IndependentVerificationRecord {
        verifier_id: "builder_alpha".into(), // VIOLATION
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_alpha".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "digest".into(),
        tests_collected: 5,
        tests_passed: 5,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: false,
        verified_status: "PASS".into(),
        execution_trace: None,
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(self_ver);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(!report.is_execution_valid);
    assert!(report.errors.iter().any(|e| e.contains("builder_id 'builder_alpha' is identical to verifier_id 'builder_alpha'")));
}

/// TEST 4: Stale receipt replay must fail signature verification.
#[test]
fn test_04_stale_receipt_replay_rejected() {
    let tmp = create_test_dir("stale_replay");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run = KernelRun::new("Original objective", &target, None);
    let run_id = run.run_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &run.task_id, &obj_hash, "base_1").unwrap();

    let run_base = run.capture_baseline(Some("base_1".into()));
    let run_ws = run_base.prepare_workspace(&target);
    let run_auth = run_ws.authorize_worker("builder_1");

    let worker_rec = WorkerInvocationRecord {
        invocation_id: "inv_1".into(),
        worker_id: "builder_1".into(),
        provider: "gemini".into(),
        model: "gemini-2.5-flash".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Structural,
        input_digest: obj_hash.clone(),
        output_digest: "out_1".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    let run_cand = run_auth.record_governed_candidate("cand_1", worker_rec, 1);
    let ver_rec = IndependentVerificationRecord {
        verifier_id: "verifier_1".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_1".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "t_1".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: None,
        timestamp: current_timestamp_rfc3339(),
    };

    let (_promoted, mut valid_receipt) = run_cand.record_verification(ver_rec).promote_and_seal();

    valid_receipt.run_id = "REPLAYED-RUN-ID-999".into();
    let report = evaluate_receipt(&valid_receipt, Some(&db));
    assert!(!report.is_execution_valid);
    assert!(report.errors.iter().any(|e| e.contains("signature mismatch")));
}

/// TEST 5: Law 4 Evidence Monotonicity Violation must be mechanically rejected.
#[test]
fn test_05_evidence_upgrade_law_4_violation() {
    let res = assert_evidence_monotonicity(
        EvidenceModality::Structural,
        EvidenceModality::Empirical,
    );
    assert!(matches!(res, Err(SubstrateLawError::MonotonicityViolation(_))));

    let res2 = assert_evidence_monotonicity(
        EvidenceModality::Simulated,
        EvidenceModality::DeterministicTest,
    );
    assert!(matches!(res2, Err(SubstrateLawError::MonotonicityViolation(_))));

    let valid_downgrade = assert_evidence_monotonicity(
        EvidenceModality::Empirical,
        EvidenceModality::Structural,
    );
    assert!(valid_downgrade.is_ok());
}

/// TEST 6: Valid Governed Execution & Production must pass all predicates.
#[test]
fn test_06_valid_governed_production_success() {
    let tmp = create_test_dir("governed_success");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run = KernelRun::new("Governed code improvement", &target, None);
    let run_id = run.run_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &run.task_id, &obj_hash, "baseline_sha_abc").unwrap();

    let run_base = run.capture_baseline(Some("baseline_sha_abc".into()));
    let run_ws = run_base.prepare_workspace(&target);
    let run_auth = run_ws.authorize_worker("builder_forge_01");

    let worker_rec = WorkerInvocationRecord {
        invocation_id: "inv_governed_01".into(),
        worker_id: "builder_forge_01".into(),
        provider: "gemini".into(),
        model: "gemini-2.5-flash".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Structural,
        input_digest: obj_hash.clone(),
        output_digest: "mut_digest_01".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.25,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    let run_cand = run_auth.record_governed_candidate("promoted_sha_xyz", worker_rec, 3);

    let ver_rec = IndependentVerificationRecord {
        verifier_id: "svris_independent_oracle".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_forge_01".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "oracle_digest_01".into(),
        tests_collected: 25,
        tests_passed: 25,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.5,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("25 passed in 0.5s".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(ver_rec);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid, "Valid execution receipt");
    assert!(report.is_production_valid, "Candidate was produced under Ten Shadows custody");
    assert_eq!(report.errors.len(), 0);
}

/// TEST 7: Retroactive Worker / Broken Ingress Lineage fails production validity.
#[test]
fn test_07_retroactive_worker_fails_lineage() {
    let tmp = create_test_dir("retroactive_worker");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run = KernelRun::new("Check retroactive worker", &target, None);
    let run_id = run.run_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &run.task_id, &obj_hash, "base_07").unwrap();

    let run_base = run.capture_baseline(Some("base_07".into()));
    let run_ws = run_base.prepare_workspace(&target);
    let run_auth = run_ws.authorize_worker("authorized_builder");

    // An external candidate was secretly substituted
    let external_cand = CandidateClassification::External(ExternalCandidate {
        candidate_sha: "unauthorized_ext_sha".into(),
        source_note: "Produced before worker authorized".into(),
    });

    let ver_rec = IndependentVerificationRecord {
        verifier_id: "svris_oracle".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "authorized_builder".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "digest".into(),
        tests_collected: 10,
        tests_passed: 10,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.1,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: None,
        timestamp: current_timestamp_rfc3339(),
    };

    let mut receipt = TenShadowsReceipt {
        receipt_version: "3.0.0".into(),
        kernel_version: "TEN_SHADOWS_TRUSTED_KERNEL_RUST_v3".into(),
        run_id: run_id.clone(),
        task_id: "task_07".into(),
        objective: "Check retroactive worker".into(),
        objective_hash: obj_hash,
        target_path: target.display().to_string(),
        starting_head: Some("base_07".into()),
        final_head: Some("unauthorized_ext_sha".into()),
        candidate_classification: external_cand,
        routing_strategy: RoutingStrategy::CodeHardening,
        routing_decision_digest: "digest_strat".into(),
        capabilities_selected: vec![],
        attempts: vec![],
        worker_invocations: vec![],
        artifacts_produced: vec![],
        verification: Some(ver_rec),
        promotion: None,
        epistemic_claims: DisaggregatedEpistemicClaims {
            claim_kernel_run_created: true,
            claim_kernel_routed: true,
            claim_worker_executed: false,
            claim_empirical_provider_invoked: false,
            claim_candidate_mutated: false,
            claim_candidate_produced_under_custody: false,
            claim_independently_verified: true,
            claim_promoted: true,
            claim_target_behaviorally_tested: true,
            claim_semantic_objective_satisfied: false,
        },
        final_status: RunStatus::VerifiedSuccess,
        created_at: current_timestamp_rfc3339(),
        sealed_at: current_timestamp_rfc3339(),
        receipt_signature: String::new(),
    };
    receipt.receipt_signature = receipt.compute_signature();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid);
    assert!(!report.is_production_valid);
    assert!(report.errors.iter().any(|e| e.contains("Candidate was NOT produced under Ten Shadows custody")));
}

/// TEST 8: Wrong Baseline Mismatch (Candidate lineage doesn't match starting_head).
#[test]
fn test_08_wrong_baseline_fails_lineage() {
    let tmp = create_test_dir("wrong_baseline");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run_id = "run_wrong_base_08".to_string();
    let obj_hash = "obj_hash_08".to_string();
    db.record_run_created(&run_id, "task_08", &obj_hash, "true_baseline_sha").unwrap();

    let forged_lineage = CandidateLineage {
        parent_baseline_sha: "WRONG_FORGED_BASELINE".into(),
        workspace_id: "ws_08".into(),
        worker_invocation_id: "inv_08".into(),
        mutations_count: 2,
        candidate_sha: "candidate_08".into(),
        created_at: current_timestamp_rfc3339(),
    };

    let ver_rec = IndependentVerificationRecord {
        verifier_id: "svris_08".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_08".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "digest_08".into(),
        tests_collected: 5,
        tests_passed: 5,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.1,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: None,
        timestamp: current_timestamp_rfc3339(),
    };

    let mut receipt = TenShadowsReceipt {
        receipt_version: "3.0.0".into(),
        kernel_version: "TEN_SHADOWS_TRUSTED_KERNEL_RUST_v3".into(),
        run_id: run_id.clone(),
        task_id: "task_08".into(),
        objective: "Test baseline mismatch".into(),
        objective_hash: obj_hash,
        target_path: target.display().to_string(),
        starting_head: Some("true_baseline_sha".into()),
        final_head: Some("candidate_08".into()),
        candidate_classification: CandidateClassification::Governed(GovernedCandidate { lineage: forged_lineage }),
        routing_strategy: RoutingStrategy::CodeHardening,
        routing_decision_digest: "digest".into(),
        capabilities_selected: vec![],
        attempts: vec![],
        worker_invocations: vec![],
        artifacts_produced: vec![],
        verification: Some(ver_rec),
        promotion: None,
        epistemic_claims: DisaggregatedEpistemicClaims {
            claim_kernel_run_created: true,
            claim_kernel_routed: true,
            claim_worker_executed: true,
            claim_empirical_provider_invoked: false,
            claim_candidate_mutated: true,
            claim_candidate_produced_under_custody: true,
            claim_independently_verified: true,
            claim_promoted: true,
            claim_target_behaviorally_tested: true,
            claim_semantic_objective_satisfied: false,
        },
        final_status: RunStatus::VerifiedSuccess,
        created_at: current_timestamp_rfc3339(),
        sealed_at: current_timestamp_rfc3339(),
        receipt_signature: String::new(),
    };
    receipt.receipt_signature = receipt.compute_signature();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(!report.is_production_valid);
    assert!(report.errors.iter().any(|e| e.contains("Lineage baseline mismatch")));
}

/// TEST 9: Interrupted / Failed Verification Rejects Promotion.
#[test]
fn test_09_failed_verification_rejects_promotion() {
    let tmp = create_test_dir("failed_ver");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run = KernelRun::new("Failing test run", &target, None);
    let run_id = run.run_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &run.task_id, &obj_hash, "base_09").unwrap();

    let run_base = run.capture_baseline(Some("base_09".into()));
    let run_ws = run_base.prepare_workspace(&target);
    let run_auth = run_ws.authorize_worker("builder_09");

    let worker_rec = WorkerInvocationRecord {
        invocation_id: "inv_09".into(),
        worker_id: "builder_09".into(),
        provider: "gemini".into(),
        model: "gemini-2.5-flash".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Structural,
        input_digest: obj_hash.clone(),
        output_digest: "out_09".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    let run_cand = run_auth.record_governed_candidate("cand_09", worker_rec, 1);

    // Verification failed! (exit_code = 1, tests_failed = 2)
    let failing_ver = IndependentVerificationRecord {
        verifier_id: "svris_09".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_09".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "digest_fail".into(),
        tests_collected: 10,
        tests_passed: 8,
        tests_failed: 2,
        exit_code: 1,
        duration_seconds: 0.2,
        falsification_attempted: true,
        verified_status: "FAIL".into(),
        execution_trace: Some("2 failed".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(failing_ver);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    assert_eq!(receipt.final_status, RunStatus::Failed);
    assert_eq!(receipt.epistemic_claims.claim_independently_verified, false);
    assert_eq!(receipt.epistemic_claims.claim_promoted, false);

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid, "Failure is a valid execution receipt");
    assert!(!report.is_production_valid, "Failed run cannot produce promoted candidate");
}

/// TEST 10: Missing empirical provider receipt when claiming EMPIRICAL modality fails execution.
#[test]
fn test_10_missing_empirical_provider_receipt_fails() {
    let tmp = create_test_dir("empirical_fail");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run_id = "run_emp_10".to_string();
    let obj_hash = "obj_hash_10".to_string();
    db.record_run_created(&run_id, "task_10", &obj_hash, "base_10").unwrap();

    // Worker claims EMPIRICAL modality but has None provider_receipt
    let bad_worker = WorkerInvocationRecord {
        invocation_id: "inv_10".into(),
        worker_id: "builder_10".into(),
        provider: "gemini".into(),
        model: "gemini-2.5-flash".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Empirical, // CLAIM
        input_digest: obj_hash.clone(),
        output_digest: "out_10".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None, // MISSING RECEIPT
    };

    let ver_rec = IndependentVerificationRecord {
        verifier_id: "svris_10".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_10".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "t_10".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: None,
        timestamp: current_timestamp_rfc3339(),
    };

    let mut receipt = TenShadowsReceipt {
        receipt_version: "3.0.0".into(),
        kernel_version: "TEN_SHADOWS_TRUSTED_KERNEL_RUST_v3".into(),
        run_id: run_id.clone(),
        task_id: "task_10".into(),
        objective: "Empirical claim test".into(),
        objective_hash: obj_hash,
        target_path: target.display().to_string(),
        starting_head: Some("base_10".into()),
        final_head: Some("cand_10".into()),
        candidate_classification: CandidateClassification::External(ExternalCandidate {
            candidate_sha: "cand_10".into(),
            source_note: "Test".into(),
        }),
        routing_strategy: RoutingStrategy::DirectDelegation,
        routing_decision_digest: "digest".into(),
        capabilities_selected: vec![],
        attempts: vec![],
        worker_invocations: vec![bad_worker],
        artifacts_produced: vec![],
        verification: Some(ver_rec),
        promotion: None,
        epistemic_claims: DisaggregatedEpistemicClaims {
            claim_kernel_run_created: true,
            claim_kernel_routed: true,
            claim_worker_executed: true,
            claim_empirical_provider_invoked: true,
            claim_candidate_mutated: false,
            claim_candidate_produced_under_custody: false,
            claim_independently_verified: true,
            claim_promoted: true,
            claim_target_behaviorally_tested: true,
            claim_semantic_objective_satisfied: false,
        },
        final_status: RunStatus::VerifiedSuccess,
        created_at: current_timestamp_rfc3339(),
        sealed_at: current_timestamp_rfc3339(),
        receipt_signature: String::new(),
    };
    receipt.receipt_signature = receipt.compute_signature();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(!report.is_execution_valid);
    assert!(report.errors.iter().any(|e| e.contains("claims EMPIRICAL modality but missing provider_receipt")));
}
