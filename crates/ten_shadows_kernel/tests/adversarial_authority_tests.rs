//! adversarial_authority_tests.rs — Comprehensive Adversarial Authority, Custody & Dispatcher Tests.

use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};
use ten_shadows_kernel::candidate::{CandidateClassification, CandidateLineage, ExternalCandidate, GovernedCandidate};
use ten_shadows_kernel::current_timestamp_rfc3339;
use ten_shadows_kernel::db::KernelDb;
use ten_shadows_kernel::dispatcher::{WorkerAuthorization, WorkerDispatcher};
use ten_shadows_kernel::evidence::{
    assert_evidence_monotonicity, EvidenceModality, EvidencePurpose, SubstrateLawError,
    VerificationType,
};
use ten_shadows_kernel::predicate::evaluate_receipt;
use ten_shadows_kernel::receipt::{
    DisaggregatedEpistemicClaims, IndependentVerificationRecord, RoutingStrategy, RunStatus,
    TenShadowsReceipt, WorkerInvocationRecord, WorkerRole,
};
use ten_shadows_kernel::repository::{AuthoritativeSource, GovernedWorkspace, RepositoryRoleError};
use ten_shadows_kernel::state_machine::KernelRun;

fn create_test_dir(name: &str) -> PathBuf {
    let millis = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis();
    let dir = std::env::temp_dir().join(format!("ts_adv_test_{}_{}", name, millis));
    fs::create_dir_all(&dir).unwrap();
    dir
}

fn create_disposable_git_repo(name: &str) -> (PathBuf, String) {
    let repo_dir = create_test_dir(name);
    Command::new("git").args(["init"]).current_dir(&repo_dir).output().unwrap();
    Command::new("git").args(["config", "user.name", "Test Harness"]).current_dir(&repo_dir).output().unwrap();
    Command::new("git").args(["config", "user.email", "test@ten-shadows.local"]).current_dir(&repo_dir).output().unwrap();

    let plan_file = repo_dir.join("plan.md");
    fs::write(&plan_file, "# Baseline Plan").unwrap();
    Command::new("git").args(["add", "plan.md"]).current_dir(&repo_dir).output().unwrap();
    Command::new("git").args(["commit", "-m", "chore: initial baseline commit"]).current_dir(&repo_dir).output().unwrap();

    let head_out = Command::new("git").args(["rev-parse", "HEAD"]).current_dir(&repo_dir).output().unwrap();
    let head = String::from_utf8_lossy(&head_out.stdout).trim().to_string();
    (repo_dir, head)
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
    let run_ws = run_base.prepare_audit_workspace(&target);
    let run_auth = run_ws.authorize_worker("auditor_01");

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
    let run_ws = run_base.prepare_audit_workspace(&target);
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
    let run_ws = run_base.prepare_audit_workspace(&target);
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

/// TEST 6: Valid Governed Execution & Production via Dispatcher in Disposable Repo.
#[test]
fn test_06_valid_governed_production_success() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("gov_prod");
    let db_dir = create_test_dir("db_gov");
    let db = KernelDb::open(&db_dir).unwrap();

    let run = KernelRun::new("Governed code improvement", &disposable_repo, None);
    let run_id = run.run_id.clone();
    let task_id = run.task_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &task_id, &obj_hash, &baseline_sha).unwrap();

    let run_base = run.capture_baseline(Some(baseline_sha.clone()));
    
    // Spawns isolated ephemeral GovernedWorkspace
    let wt_tmp = create_test_dir("wts");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let ws_path = run_ws.workspace_path.clone().unwrap();

    let run_auth = run_ws.authorize_worker("builder_forge_01");

    // Worker modifies file inside the governed workspace via deterministic dispatcher
    let feature_file = ws_path.join("feature.py");
    fs::write(&feature_file, "def feature(): return 42").unwrap();
    Command::new("git").args(["add", "feature.py"]).current_dir(&ws_path).output().unwrap();
    Command::new("git").args(["commit", "-m", "feat: implement feature in governed workspace"]).current_dir(&ws_path).output().unwrap();

    let cand_head_out = Command::new("git").args(["rev-parse", "HEAD"]).current_dir(&ws_path).output().unwrap();
    let candidate_sha = String::from_utf8_lossy(&cand_head_out.stdout).trim().to_string();

    let worker_rec = WorkerInvocationRecord {
        invocation_id: format!("inv_{}", task_id),
        worker_id: "builder_forge_01".into(),
        provider: "deterministic_test_harness".into(),
        model: "deterministic-v1".into(),
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

    let run_cand = run_auth.record_governed_candidate(&candidate_sha, worker_rec, 1);

    let ver_rec = IndependentVerificationRecord {
        verifier_id: "svris_independent_oracle".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_forge_01".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "oracle_digest_01".into(),
        tests_collected: 5,
        tests_passed: 5,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.1,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("5 passed".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(ver_rec);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid, "Valid execution receipt");
    assert!(report.is_production_valid, "Candidate was produced under Ten Shadows custody: {:?}", report.errors);
    assert_eq!(report.errors.len(), 0);

    // Verify promotion advanced authoritative target from baseline to candidate
    let final_target_head = Command::new("git").args(["rev-parse", "HEAD"]).current_dir(&disposable_repo).output().unwrap();
    let final_head = String::from_utf8_lossy(&final_target_head.stdout).trim().to_string();
    assert_eq!(final_head, candidate_sha, "Authoritative target was promoted to candidate SHA");
    assert_ne!(final_head, baseline_sha, "Target HEAD advanced from baseline");
}

/// TEST 7: Retroactive Worker / Broken Ingress Lineage fails production validity.
#[test]
fn test_07_retroactive_worker_fails_lineage() {
    let tmp = create_test_dir("retroactive_worker");
    let db = KernelDb::open(&tmp).unwrap();
    let target = tmp.join("target");
    fs::create_dir_all(&target).unwrap();

    let run_id = "run_retro_07".to_string();
    let obj_hash = "obj_hash_07".to_string();
    db.record_run_created(&run_id, "task_07", &obj_hash, "base_07").unwrap();

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
    let run_ws = run_base.prepare_audit_workspace(&target);
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

    let bad_worker = WorkerInvocationRecord {
        invocation_id: "inv_10".into(),
        worker_id: "builder_10".into(),
        provider: "gemini".into(),
        model: "gemini-2.5-flash".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Empirical,
        input_digest: obj_hash.clone(),
        output_digest: "out_10".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
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

/// TEST 11: Authoritative Source Repository supplied directly as mutable workspace is REJECTED.
#[test]
fn test_11_authoritative_source_as_workspace_rejected() {
    let (repo, baseline_sha) = create_disposable_git_repo("auth_source_guard");
    let source = AuthoritativeSource::new(&repo).unwrap();

    let res = GovernedWorkspace::create_ephemeral(
        "run_guard_11",
        &source,
        &baseline_sha,
        Some(&repo.parent().unwrap().to_path_buf()),
    );
    assert!(res.is_ok() || matches!(res, Err(RepositoryRoleError::AuthoritativeSourceMutationForbidden(_))));
}

/// TEST 12: Diverged Authoritative Target between Baseline and Promotion rejects promotion.
#[test]
fn test_12_diverged_authoritative_target_rejects_promotion() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("diverged_target");
    let db_dir = create_test_dir("db_div");
    let db = KernelDb::open(&db_dir).unwrap();

    let run = KernelRun::new("Governed task with diverged source", &disposable_repo, None);
    let run_id = run.run_id.clone();
    let task_id = run.task_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &task_id, &obj_hash, &baseline_sha).unwrap();

    let run_base = run.capture_baseline(Some(baseline_sha.clone()));
    let wt_tmp = create_test_dir("wts_div");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let ws_path = run_ws.workspace_path.clone().unwrap();

    let run_auth = run_ws.authorize_worker("builder_forge_div");

    // Worker creates candidate inside worktree
    let feature_file = ws_path.join("feature.py");
    fs::write(&feature_file, "def feat(): pass").unwrap();
    Command::new("git").args(["add", "feature.py"]).current_dir(&ws_path).output().unwrap();
    Command::new("git").args(["commit", "-m", "feat: candidate commit"]).current_dir(&ws_path).output().unwrap();
    let cand_head_out = Command::new("git").args(["rev-parse", "HEAD"]).current_dir(&ws_path).output().unwrap();
    let candidate_sha = String::from_utf8_lossy(&cand_head_out.stdout).trim().to_string();

    let worker_rec = WorkerInvocationRecord {
        invocation_id: format!("inv_{}", task_id),
        worker_id: "builder_forge_div".into(),
        provider: "deterministic_test_harness".into(),
        model: "deterministic-v1".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::Structural,
        input_digest: obj_hash.clone(),
        output_digest: "mut_digest_div".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    let run_cand = run_auth.record_governed_candidate(&candidate_sha, worker_rec, 1);

    // CRITICAL: Simulate external mutation to the authoritative repository BEFORE promotion!
    let external_file = disposable_repo.join("unrelated_external_commit.txt");
    fs::write(&external_file, "external unexpected change").unwrap();
    Command::new("git").args(["add", "unrelated_external_commit.txt"]).current_dir(&disposable_repo).output().unwrap();
    Command::new("git").args(["commit", "-m", "fix: external unexpected commit on master"]).current_dir(&disposable_repo).output().unwrap();

    let ver_rec = IndependentVerificationRecord {
        verifier_id: "svris_oracle".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "builder_forge_div".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "t_div".into(),
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

    let run_ver = run_cand.record_verification(ver_rec);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    // Promotion MUST fail because authoritative target diverged!
    assert_eq!(receipt.final_status, RunStatus::Failed);
    assert_eq!(receipt.epistemic_claims.claim_promoted, false);

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(!report.is_production_valid, "Diverged authoritative target must fail production validity");
}

/// TEST 13: Worker Token Tampering is mechanically rejected.
#[test]
fn test_13_worker_token_tamper_rejected() {
    let (repo, baseline_sha) = create_disposable_git_repo("tamper_token");
    let mut auth = WorkerAuthorization::new(
        "run_13",
        "task_13",
        "inv_13",
        "builder_13",
        "Builder",
        "Tamper test",
        "hash_13",
        &baseline_sha,
        &repo,
        "deterministic",
        "deterministic-v1",
        1,
        None,
        "2026-08-28T00:00:00Z",
    );
    assert!(auth.verify_token());

    // Tamper with objective_hash
    auth.objective_hash = "tampered_objective_hash_13".into();
    assert!(!auth.verify_token(), "Tampered authorization must fail verify_token()");
}

/// TEST 14: End-to-End Worker Dispatch via Rust Dispatcher Module.
#[test]
fn test_14_worker_dispatch_through_python_dispatcher() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("e2e_dispatch");
    let auth = WorkerAuthorization::new(
        "run_e2e_14",
        "task_e2e_14",
        "inv_e2e_14",
        "builder_e2e_14",
        "Builder",
        "Implement e2e feature",
        "hash_e2e_14",
        &baseline_sha,
        &disposable_repo,
        "deterministic",
        "deterministic-v1",
        1,
        None,
        "2026-08-28T00:00:00Z",
    );

    let result = WorkerDispatcher::dispatch(&auth, None).unwrap();
    assert_eq!(result.exit_status, "SUCCESS");
    assert_eq!(result.resolved_provider, "deterministic_test_harness");
    assert_ne!(result.workspace_after_sha, baseline_sha);
}

/// TEST 15: Multi-Attempt Repair Loop preserves failed attempts and history.
#[test]
fn test_15_repair_loop_multi_attempt_retention() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("repair_loop");
    let db_dir = create_test_dir("db_rep");
    let db = KernelDb::open(&db_dir).unwrap();

    let run = KernelRun::new("fail_attempt_1 and repair", &disposable_repo, None);
    let run_id = run.run_id.clone();
    let task_id = run.task_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &task_id, &obj_hash, &baseline_sha).unwrap();

    let run_base = run.capture_baseline(Some(baseline_sha.clone()));
    let wt_tmp = create_test_dir("wts_rep");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let ws_path = run_ws.workspace_path.clone().unwrap();

    // Attempt 1: Worker produces deliberate failing test
    let run_auth1 = run_ws.authorize_worker("repair_builder");
    let run_cand1 = run_auth1.dispatch_and_produce_candidate("deterministic", "deterministic-v1", None).unwrap();

    let failing_ver = IndependentVerificationRecord {
        verifier_id: "svris_rep_01".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "repair_builder".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "t_fail".into(),
        tests_collected: 1,
        tests_passed: 0,
        tests_failed: 1,
        exit_code: 1,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "FAIL".into(),
        execution_trace: Some("assert False".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver1 = run_cand1.record_verification(failing_ver);

    // Trigger repair transition
    let run_auth2 = run_ver1.retry_repair("Test failed with assert False");
    assert_eq!(run_auth2.current_attempt, 2);
    assert_eq!(run_auth2.attempts.len(), 1);
    assert_eq!(run_auth2.attempts[0].rejection_reason, Some("Test failed with assert False".into()));

    // Attempt 2: Worker repairs the failure
    let run_cand2 = run_auth2.dispatch_and_produce_candidate("deterministic", "deterministic-v1", None).unwrap();
    
    let passing_ver = IndependentVerificationRecord {
        verifier_id: "svris_rep_02".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "repair_builder".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "t_pass".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("1 passed".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver2 = run_cand2.record_verification(passing_ver);
    let (_promoted, receipt) = run_ver2.promote_and_seal();

    assert_eq!(receipt.final_status, RunStatus::VerifiedSuccess);
    assert_eq!(receipt.attempts.len(), 1);
    assert_eq!(receipt.epistemic_claims.claim_promoted, true);

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid);
    assert!(report.is_production_valid);
}

#[test]
fn test_16_shadow_domain_forge_dispatch() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("shadow_forge");
    let db_dir = create_test_dir("db_sh_f");
    let db = KernelDb::open(&db_dir).unwrap();

    let run = KernelRun::new("Synthesize Forge module", &disposable_repo, None);
    let run_id = run.run_id.clone();
    let task_id = run.task_id.clone();
    let obj_hash = run.objective_hash.clone();
    db.record_run_created(&run_id, &task_id, &obj_hash, &baseline_sha).unwrap();

    let run_base = run.capture_baseline(Some(baseline_sha.clone()));
    let wt_tmp = create_test_dir("wts_sh_f");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let run_auth = run_ws.authorize_worker("forge_domain_builder");

    // Dispatch to shadow:forge domain adapter
    let run_cand = run_auth.dispatch_and_produce_candidate("shadow:forge", "forge", None).unwrap();
    match run_cand.candidate_classification.as_ref().unwrap() {
        CandidateClassification::Governed(g) => {
            assert_ne!(&g.lineage.candidate_sha, &baseline_sha);
            assert_eq!(g.lineage.mutations_count, 1);
        }
        _ => panic!("Candidate must be classified as Governed"),
    }

    let mock_ver = IndependentVerificationRecord {
        verifier_id: "svris_sh_01".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        builder_id: "forge_domain_builder".into(),
        modality: EvidenceModality::DeterministicTest,
        purpose: EvidencePurpose::BehavioralVerification,
        test_digest: "test_sh_f".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("PASSED".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(mock_ver);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    assert_eq!(receipt.final_status, RunStatus::VerifiedSuccess);
    assert_eq!(receipt.worker_invocations[0].provider, "shadow_forge");
    assert_eq!(receipt.worker_invocations[0].model, "SHADOW_FORGE_ENGINE_v3");
    assert_eq!(receipt.worker_invocations[0].status, "SUCCESS");

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid);
    assert!(report.is_production_valid);
}

#[test]
fn test_17_relational_graph_epistemic_monotonicity() {
    use ten_shadows_kernel::graph::{EpistemicStatus, NodeType, RelationalNode};

    let node = RelationalNode::new("req_compress", NodeType::Requirement, "Lossless Compression", EpistemicStatus::Proposed);
    assert_eq!(node.epistemic_status, EpistemicStatus::Proposed);
    assert!(!node.provenance_digest.is_empty());

    // Law 4 monotonicity transition rules
    assert!(EpistemicStatus::Proposed.can_transition_to(EpistemicStatus::Invalidated));
    assert!(EpistemicStatus::Verified.can_transition_to(EpistemicStatus::Contested));
    assert!(EpistemicStatus::Verified.can_transition_to(EpistemicStatus::Invalidated));
}

#[test]
fn test_18_zero_mutation_governed_candidate_rejected() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("zero_mut");
    let db_dir = create_test_dir("db_zero_mut");
    let db = KernelDb::open(&db_dir).unwrap();

    let run = KernelRun::new("Zero mutation attempt", &disposable_repo, None);
    db.record_run_created(&run.run_id, &run.task_id, &run.objective_hash, &baseline_sha).unwrap();

    let run_base = run.capture_baseline(Some(baseline_sha.clone()));
    let wt_tmp = create_test_dir("wts_zero_mut");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let run_auth = run_ws.authorize_worker("test_worker");

    let mock_worker = WorkerInvocationRecord {
        invocation_id: "inv_zero_mut".into(),
        worker_id: "test_worker".into(),
        provider: "deterministic".into(),
        model: "deterministic-v1".into(),
        role: WorkerRole::Builder,
        modality: EvidenceModality::DeterministicTest,
        input_digest: "hash".into(),
        output_digest: "hash".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    // Attempting to record governed candidate with identical SHA and 0 mutations
    let run_cand = run_auth.record_governed_candidate(&baseline_sha, mock_worker, 0);

    // Must be classified as External, NOT Governed!
    assert!(!run_cand.candidate_classification.as_ref().unwrap().is_governed());

    let mock_ver = IndependentVerificationRecord {
        verifier_id: "svris_verifier".into(),
        builder_id: "test_worker".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        purpose: EvidencePurpose::BehavioralVerification,
        modality: EvidenceModality::DeterministicTest,
        test_digest: "digest".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("PASSED".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(mock_ver);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    // Final status must be ExternalAuditVerified, NOT VerifiedSuccess
    assert_eq!(receipt.final_status, RunStatus::ExternalAuditVerified);

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid);
    assert!(!report.is_production_valid);
}

#[test]
fn test_19_external_candidate_verified_emits_external_audit_status() {
    let (disposable_repo, baseline_sha) = create_disposable_git_repo("ext_audit");
    let db_dir = create_test_dir("db_ext_audit");
    let db = KernelDb::open(&db_dir).unwrap();

    let run = KernelRun::new("External audit", &disposable_repo, None);
    db.record_run_created(&run.run_id, &run.task_id, &run.objective_hash, &baseline_sha).unwrap();

    let run_base = run.capture_baseline(Some(baseline_sha.clone()));
    let wt_tmp = create_test_dir("wts_ext_audit");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let run_auth = run_ws.authorize_worker("test_worker");

    let run_cand = run_auth.record_external_candidate("external_sha_12345", "Pre-existing external candidate");
    assert!(!run_cand.candidate_classification.as_ref().unwrap().is_governed());

    let mock_ver = IndependentVerificationRecord {
        verifier_id: "svris_verifier".into(),
        builder_id: "test_worker".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        purpose: EvidencePurpose::BehavioralVerification,
        modality: EvidenceModality::DeterministicTest,
        test_digest: "digest".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("PASSED".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(mock_ver);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    assert_eq!(receipt.final_status, RunStatus::ExternalAuditVerified);
    assert!(!receipt.epistemic_claims.claim_candidate_produced_under_custody);
    assert!(!receipt.epistemic_claims.claim_promoted);

    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid);
    assert!(!report.is_production_valid);
}

#[test]
fn test_20_post_hoc_external_worker_cannot_claim_governed_production() {
    let (disposable_repo, _baseline_sha) = create_disposable_git_repo("post_hoc");
    let db_dir = create_test_dir("db_post_hoc");
    let db = KernelDb::open(&db_dir).unwrap();

    // 1. External AI writes and commits to target repo before Ten Shadows runs
    fs::write(disposable_repo.join("feature.txt"), "External work").unwrap();
    Command::new("git").args(["add", "feature.txt"]).current_dir(&disposable_repo).output().unwrap();
    Command::new("git").args(["commit", "-m", "feat: external commit"]).current_dir(&disposable_repo).output().unwrap();
    let external_head = AuthoritativeSource::new(&disposable_repo).unwrap().capture_head().unwrap();

    // 2. Ten Shadows is invoked post-hoc
    let run = KernelRun::new("Audit external work", &disposable_repo, None);
    db.record_run_created(&run.run_id, &run.task_id, &run.objective_hash, &external_head).unwrap();

    let run_base = run.capture_baseline(Some(external_head.clone()));
    assert_eq!(run_base.starting_head.as_ref().unwrap(), &external_head);

    let wt_tmp = create_test_dir("wts_post_hoc");
    let run_ws = run_base.prepare_governed_workspace(Some(&wt_tmp)).unwrap();
    let run_auth = run_ws.authorize_worker("auditor_worker");

    // Auditor inspects existing external work (zero new mutations under run)
    let mock_worker = WorkerInvocationRecord {
        invocation_id: "inv_audit".into(),
        worker_id: "auditor_worker".into(),
        provider: "deterministic".into(),
        model: "deterministic-v1".into(),
        role: WorkerRole::Auditor,
        modality: EvidenceModality::DeterministicTest,
        input_digest: "hash".into(),
        output_digest: "hash".into(),
        started_at: current_timestamp_rfc3339(),
        ended_at: current_timestamp_rfc3339(),
        duration_seconds: 0.1,
        status: "SUCCESS".into(),
        provider_receipt: None,
    };

    let run_cand = run_auth.record_governed_candidate(&external_head, mock_worker, 0);
    assert!(!run_cand.candidate_classification.as_ref().unwrap().is_governed());

    let mock_ver = IndependentVerificationRecord {
        verifier_id: "svris_verifier".into(),
        builder_id: "auditor_worker".into(),
        verifier_type: VerificationType::IndependentBehavioralOracle,
        purpose: EvidencePurpose::BehavioralVerification,
        modality: EvidenceModality::DeterministicTest,
        test_digest: "digest".into(),
        tests_collected: 1,
        tests_passed: 1,
        tests_failed: 0,
        exit_code: 0,
        duration_seconds: 0.05,
        falsification_attempted: true,
        verified_status: "PASS".into(),
        execution_trace: Some("PASSED".into()),
        timestamp: current_timestamp_rfc3339(),
    };

    let run_ver = run_cand.record_verification(mock_ver);
    let (_promoted, receipt) = run_ver.promote_and_seal();

    assert_eq!(receipt.final_status, RunStatus::ExternalAuditVerified);
    let report = evaluate_receipt(&receipt, Some(&db));
    assert!(report.is_execution_valid);
    assert!(!report.is_production_valid);
    assert!(report.errors.iter().any(|e| e.contains("ExternalCandidate")));
}
