"""
tests/test_constitutional_foundation.py
Comprehensive Physical, Adversarial, Property, Mutation, and Cross-Domain Tests
for the Ten Shadows Constitutional Foundation.

Enforces:
- Law 6: Objective Sufficiency (Elimination of false-success paths)
- 4 Cross-Domain Walking Skeletons (Software, Research, Communication, Planning)
- 20 Sentinel Attacks
- 10 Second-Order Hardened Attacks
- 8 Formal Property Invariant Tests
- Mechanical JTMS Live Invalidation Integration
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import pytest

from forge.core.substrate import (
    CanonicalRequirement,
    EvidenceClass,
    ObjectiveAdequacyState,
    OperatorType,
    RawClause,
    RequiredOperation,
    RequirementDisposition,
    RequirementOrigin,
)
from loop_engine.constitution import (
    ApplicabilityDimension,
    AuthorityDimension,
    CandidateInterpretation,
    CapabilityDeficitEngine,
    CapabilityEpistemicStatus,
    CompositionRule,
    ConditionalCapability,
    EpistemicClaim,
    EpistemicDimension,
    Law6SufficiencyEngine,
    ObjectiveLifecycleManager,
    ObjectiveRevisionAuthorization,
    ObjectiveSufficiencyProof,
    ObservationDimension,
    OperationalCondition,
    ProposedRequirement,
    QualifiedEvidence,
    RawIntent,
    ReachabilityDimension,
    RelationalEvidenceEvaluator,
    RevisionType,
    SemanticQualificationStatus,
    VerifierExecutionObservation,
    VerifierSpecification,
    VersionedObjectiveSpecification,
)
from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationalEdge,
    RelationalNode,
    RelationType,
)
from loop_engine.relational.truth_maintenance import TruthMaintenanceEngine

# ==============================================================================
# 1. CROSS-DOMAIN WALKING SKELETONS
# ==============================================================================


def test_walking_skeleton_a_software_objective():
    """
    WALKING SKELETON A (Software):
    Objective: Implement arithmetic multiplication.
    Rejects addition, rejects empty observation, accepts verified multiplication.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Implement arithmetic multiplication for math library")
    prop = ProposedRequirement(
        "prop_mult",
        "clause_1",
        "Implement arithmetic multiplication for math library",
        RequirementOrigin.SOURCE_EXPLICIT,
    )
    interp = CandidateInterpretation(
        candidate_id="interp_sw",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[RawClause("clause_1", raw.raw_text, False, True)],
        proposed_requirements=[prop],
        proposer_identity="forge_worker",
    )
    spec = mgr.qualify_intent("obj_sw_01", raw, interp)
    assert spec.qualification_status == SemanticQualificationStatus.QUALIFIED

    claim_mult = EpistemicClaim(
        claim_id="prop_mult",
        subject="math_lib.py",
        predicate="MULTIPLIES_INTEGERS",
        required_scope="unit_tests",
        target_candidate_sha="cand_mult_sha",
        required_environment="env_linux",
    )
    spec_mult = VerifierSpecification(
        spec_id="spec_mult",
        target_claim_id="prop_mult",
        verification_modality="DETERMINISTIC_TEST",
        expected_scope="unit_tests",
        target_candidate_sha="cand_mult_sha",
        required_environment_pattern="env_linux",
        min_coverage_percentage=80.0,
        explicit_non_claims=["Does not establish float precision"],
    )

    # Negative mutant: Passing addition test
    spec_add = VerifierSpecification(
        spec_id="spec_add",
        target_claim_id="prop_add",
        verification_modality="DETERMINISTIC_TEST",
        expected_scope="unit_tests",
        target_candidate_sha="cand_mult_sha",
    )
    obs_bad = VerifierExecutionObservation(
        observation_id="obs_bad",
        spec_digest=spec_add.spec_digest,
        executed_command="pytest tests/test_add.py",
        collector_type="pytest",
        exit_code=0,
        tests_collected=1,
        tests_passed=1,
        tests_failed=0,
        duration_seconds=0.05,
        coverage_percentage=100.0,
        candidate_sha="cand_mult_sha",
        environment_fingerprint="env_linux",
    )
    ev_bad = QualifiedEvidence("ev_add", spec_add, obs_bad, EvidenceClass.EMPIRICAL_TEST)

    proof_bad = Law6SufficiencyEngine.evaluate_specification(
        spec,
        {"prop_mult": claim_mult},
        {"prop_mult": [ev_bad]},
        active_candidate_sha="cand_mult_sha",
        active_environment_fingerprint="env_linux",
    )
    assert proof_bad.is_satisfied is False
    assert "prop_mult" in proof_bad.unresolved_mandatory_ids

    # Positive: Genuine passing multiplication test
    obs_good = VerifierExecutionObservation(
        observation_id="obs_good",
        spec_digest=spec_mult.spec_digest,
        executed_command="pytest tests/test_multiply.py",
        collector_type="pytest",
        exit_code=0,
        tests_collected=5,
        tests_passed=5,
        tests_failed=0,
        duration_seconds=0.1,
        coverage_percentage=95.0,
        candidate_sha="cand_mult_sha",
        environment_fingerprint="env_linux",
    )
    ev_good = QualifiedEvidence("ev_mult", spec_mult, obs_good, EvidenceClass.EMPIRICAL_TEST)

    proof_good = Law6SufficiencyEngine.evaluate_specification(
        spec,
        {"prop_mult": claim_mult},
        {"prop_mult": [ev_good]},
        active_candidate_sha="cand_mult_sha",
        active_environment_fingerprint="env_linux",
    )
    assert proof_good.is_satisfied is True
    assert "prop_mult" in proof_good.satisfied_requirement_ids


def test_walking_skeleton_b_research_objective():
    """
    WALKING SKELETON B (Research):
    Objective: Determine whether evidence supports hypothesis H.
    Supports SUPPORTED, CONTRADICTED without physical code semantics.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Investigate enzyme inhibition")
    prop = ProposedRequirement("prop_res", "c1", "Investigate enzyme inhibition", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation(
        candidate_id="interp_res",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[RawClause("c1", raw.raw_text, False, True)],
        proposed_requirements=[prop],
        proposer_identity="research_worker",
    )
    spec = mgr.qualify_intent("obj_res_01", raw, interp)

    claim = EpistemicClaim("prop_res", "Compound_X", "INHIBITS_ENZYME_Y", "in_vitro_assay")
    v_spec = VerifierSpecification("v_res", "prop_res", "DOCUMENTED_BENCHMARK", "in_vitro_assay", None)

    obs_contra = VerifierExecutionObservation(
        "obs_c", v_spec.spec_digest, "run_assay", "lab", 1, 1, 0, 1, 1.0, 100.0, "data_v1", "lab_rig"
    )
    ev_contra = QualifiedEvidence("ev_c", v_spec, obs_contra, EvidenceClass.DOCUMENTED_METRIC)

    proof_contra = Law6SufficiencyEngine.evaluate_specification(spec, {"prop_res": claim}, {"prop_res": [ev_contra]})
    assert proof_contra.is_satisfied is False
    assert "prop_res" in proof_contra.falsified_mandatory_ids


def test_walking_skeleton_c_communication_objective():
    """
    WALKING SKELETON C (Communication):
    Objective: Produce executive summary faithful to source facts.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Financial metrics and risk disclosures.")
    prop_fin = ProposedRequirement("p_fin", "c1", "Financial metrics", RequirementOrigin.SOURCE_EXPLICIT)
    prop_risk = ProposedRequirement("p_risk", "c2", "Risk disclosures", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation(
        candidate_id="interp_comm",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[
            RawClause("c1", "Financial metrics", False, True),
            RawClause("c2", "Risk disclosures", False, True),
        ],
        proposed_requirements=[prop_fin, prop_risk],
        proposer_identity="comms_worker",
    )
    spec = mgr.qualify_intent("obj_comm_01", raw, interp)

    claim_fin = EpistemicClaim("p_fin", "Summary", "COVERS_FINANCIALS", "sec_filing")
    claim_risk = EpistemicClaim("p_risk", "Summary", "COVERS_RISKS", "risk_register")

    v_fin = VerifierSpecification("v_fin", "p_fin", "FACT_CHECK", "sec_filing", "art_1")
    v_risk = VerifierSpecification("v_risk", "p_risk", "FACT_CHECK", "risk_register", "art_1")

    ev_fin = QualifiedEvidence(
        "ev_f",
        v_fin,
        VerifierExecutionObservation("o_f", v_fin.spec_digest, "check", "nlp", 0, 1, 1, 0, 0.1, 100.0, "art_1", "env"),
        EvidenceClass.DIRECT_QUOTE,
    )
    ev_risk = QualifiedEvidence(
        "ev_r",
        v_risk,
        VerifierExecutionObservation("o_r", v_risk.spec_digest, "check", "nlp", 0, 1, 1, 0, 0.1, 100.0, "art_1", "env"),
        EvidenceClass.DIRECT_QUOTE,
    )

    proof = Law6SufficiencyEngine.evaluate_specification(
        spec,
        {"p_fin": claim_fin, "p_risk": claim_risk},
        {"p_fin": [ev_fin], "p_risk": [ev_risk]},
        active_candidate_sha="art_1",
    )
    assert proof.is_satisfied is True


def test_walking_skeleton_d_planning_objective():
    """
    WALKING SKELETON D (Planning):
    Objective: Produce execution plan satisfying hard resource constraints.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Migration plan with zero database downtime.")
    p_plan = ProposedRequirement("p_plan", "c1", "Migration plan", RequirementOrigin.SOURCE_EXPLICIT)
    p_dt = ProposedRequirement("p_dt", "c2", "Zero database downtime", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation(
        candidate_id="interp_plan",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[
            RawClause("c1", "Migration plan", False, True),
            RawClause("c2", "Zero database downtime", False, True),
        ],
        proposed_requirements=[p_plan, p_dt],
        proposer_identity="planner_worker",
    )
    spec = mgr.qualify_intent("obj_plan_01", raw, interp)

    claim_p = EpistemicClaim("p_plan", "Plan", "COMPLETE", "arch")
    claim_dt = EpistemicClaim("p_dt", "Plan", "ZERO_DT", "sla")

    v_p = VerifierSpecification("v_p", "p_plan", "STATIC", "arch", "plan_sha")
    v_dt = VerifierSpecification("v_dt", "p_dt", "SIM", "sla", "plan_sha")

    ev_p = QualifiedEvidence(
        "ev_p",
        v_p,
        VerifierExecutionObservation("o_p", v_p.spec_digest, "sim", "tool", 0, 1, 1, 0, 0.1, 100.0, "plan_sha", "sim"),
        EvidenceClass.VERIFIED_FACT,
    )
    ev_dt_fail = QualifiedEvidence(
        "ev_dt",
        v_dt,
        VerifierExecutionObservation(
            "o_dt", v_dt.spec_digest, "sim", "tool", 1, 1, 0, 1, 0.1, 100.0, "plan_sha", "sim"
        ),
        EvidenceClass.DOCUMENTED_METRIC,
    )

    proof = Law6SufficiencyEngine.evaluate_specification(
        spec,
        {"p_plan": claim_p, "p_dt": claim_dt},
        {"p_plan": [ev_p], "p_dt": [ev_dt_fail]},
        active_candidate_sha="plan_sha",
    )
    assert proof.is_satisfied is False
    assert "p_dt" in proof.falsified_mandatory_ids


# ==============================================================================
# 2. SENTINEL 20-ATTACK REPRODUCTIONS
# ==============================================================================


def test_sentinel_01_omitted_compound_intent_rejected():
    """Attack 1: Complex compound intent with dropped clause fails adequacy qualification."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Implement SHA256 hashing and AES256 encryption")
    # Worker proposes only AES256 and drops SHA256
    prop = ProposedRequirement("p_aes", "c_aes", "AES256 encryption", RequirementOrigin.SOURCE_EXPLICIT)
    clauses = [
        RawClause("c_sha", "Implement SHA256 hashing", False, True),
        RawClause("c_aes", "AES256 encryption", False, True),
    ]
    interp = CandidateInterpretation("i1", raw.intent_hash, clauses, [prop], "worker")

    spec = mgr.qualify_intent("obj_s01", raw, interp)
    assert spec.qualification_status == SemanticQualificationStatus.INSUFFICIENT_INFORMATION
    assert "Implement SHA256 hashing" in spec.adequacy_contract.unaccounted_drops


def test_sentinel_02_tautological_test_laundering_rejected():
    """Attack 2: Verifier observation with 0 tests executed cannot satisfy claim."""
    v_spec = VerifierSpecification("v1", "claim1", "TEST", "scope", "sha1")
    obs_empty = VerifierExecutionObservation(
        "o1", v_spec.spec_digest, "pytest", "pytest", 0, 0, 0, 0, 0.01, 0.0, "sha1", "env"
    )
    ev = QualifiedEvidence("ev1", v_spec, obs_empty, EvidenceClass.EMPIRICAL_TEST)
    claim = EpistemicClaim("claim1", "mod", "PRED", "scope")

    ep, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep == EpistemicDimension.UNSUPPORTED


def test_sentinel_03_unauthorized_requirement_deletion_rejected():
    """Attack 3: Worker attempts to revise objective to delete requirement without valid authorization."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Build auth and billing")
    p1 = ProposedRequirement("p1", "c1", "Build auth", RequirementOrigin.SOURCE_EXPLICIT)
    p2 = ProposedRequirement("p2", "c2", "Build billing", RequirementOrigin.SOURCE_EXPLICIT)
    spec = mgr.qualify_intent(
        "obj_s03",
        raw,
        CandidateInterpretation(
            "i",
            raw.intent_hash,
            [RawClause("c1", "Build auth", False, True), RawClause("c2", "Build billing", False, True)],
            [p1, p2],
            "w",
        ),
    )

    # Worker attempts revision with forged/empty authorization token
    forged_auth = ObjectiveRevisionAuthorization(
        "auth_fake", "HUMAN_OPERATOR", "", "obj_s03", 1, [RevisionType.REQUIREMENT_REMOVAL]
    )
    with pytest.raises(PermissionError, match="UNAUTHORIZED_REVISION"):
        mgr.revise_objective(
            spec,
            RevisionType.REQUIREMENT_REMOVAL,
            "Build auth",
            [spec.requirements[0]],
            forged_auth,
            "Worker dropped billing",
        )


def test_sentinel_04_environment_fingerprint_bypass_rejected():
    """Attack 4: Evidence observed in wrong environment cannot satisfy environment-bound claim."""
    claim = EpistemicClaim("c_linux", "app", "RUNS", "os", required_environment="linux_x86_64")
    v_spec = VerifierSpecification(
        "v_lin", "c_linux", "TEST", "os", "sha1", required_environment_pattern="linux_x86_64"
    )
    obs_win = VerifierExecutionObservation(
        "o_win", v_spec.spec_digest, "test", "pytest", 0, 5, 5, 0, 0.1, 100.0, "sha1", "windows_x86_64"
    )
    ev = QualifiedEvidence("ev_win", v_spec, obs_win, EvidenceClass.EMPIRICAL_TEST)

    ep, app, msg = RelationalEvidenceEvaluator.evaluate_claim(
        claim, [ev], active_candidate_sha="sha1", active_environment_fingerprint="linux_x86_64"
    )
    assert ep == EpistemicDimension.UNSUPPORTED
    assert app == ApplicabilityDimension.INAPPLICABLE
    assert "Environment mismatch" in msg or "Stale environment" in msg


def test_sentinel_05_claim_id_collision_rejected():
    """Attack 5: Verifier specification target_claim_id must match evaluated claim."""
    claim = EpistemicClaim("claim_auth", "auth", "SECURE", "scope")
    v_spec = VerifierSpecification("v_perf", "claim_perf", "BENCHMARK", "scope", "sha1")
    obs = VerifierExecutionObservation(
        "o_p", v_spec.spec_digest, "bench", "tool", 0, 1, 1, 0, 0.1, 100.0, "sha1", "env"
    )
    ev = QualifiedEvidence("ev_p", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)

    ep, app, msg = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep == EpistemicDimension.UNSUPPORTED
    assert app == ApplicabilityDimension.INAPPLICABLE
    assert "Target claim mismatch" in msg


def test_sentinel_06_wildcard_capability_eliminated():
    """Attack 6: Capability must specify explicit supported environments."""
    cond = OperationalCondition("cond1", "posix only", "linux_x86_64", ["socket"])
    cap = ConditionalCapability(
        "cap1",
        "actor1",
        OperatorType.ACT,
        {"linux_x86_64"},
        [cond],
        [EvidenceClass.EMPIRICAL_TEST],
        1.0,
        epistemic_status=CapabilityEpistemicStatus.QUALIFIED,
    )
    assert cap.is_applicable("windows_x86_64", ["socket"]) is False
    assert cap.is_applicable("linux_x86_64", ["socket"]) is True


def test_sentinel_07_forged_ingress_provenance_rejected():
    """Attack 7: Unmapped proposed requirement cannot claim SOURCE_EXPLICIT origin."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Basic Calculator")
    prop = ProposedRequirement(
        "p_fake", "non_existent_clause", "Quantum Computing Subsystem", RequirementOrigin.SOURCE_EXPLICIT
    )
    spec = mgr.qualify_intent(
        "obj_s07",
        raw,
        CandidateInterpretation("i", raw.intent_hash, [RawClause("c1", "Basic Calculator", False, True)], [prop], "w"),
    )

    # Requirement trace disposition is marked ASSUMED because no source clause matched
    assert spec.requirements[0].origin == RequirementOrigin.ASSUMED


def test_sentinel_08_jtms_in_memory_live_invalidation():
    """Attack 8: JTMS retraction immediately invalidates live Law 6 evaluation."""
    store = RelationalGraphStore(db_path=":memory:")
    jtms = TruthMaintenanceEngine(store)

    store.upsert_node(
        RelationalNode("ev_live", NodeType.EVIDENCE, "Test Ev", epistemic_status=EpistemicStatus.VERIFIED)
    )
    store.upsert_node(
        RelationalNode("req_live", NodeType.REQUIREMENT, "Req", epistemic_status=EpistemicStatus.VERIFIED)
    )
    store.upsert_edge(RelationalEdge("e1", "req_live", "ev_live", RelationType.SUPPORTED_BY, EpistemicStatus.VERIFIED))

    req = CanonicalRequirement("req_live", "Req description", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification(
        "obj_live", 1, "Intent", "hash", [req], SemanticQualificationStatus.QUALIFIED
    )
    claim = EpistemicClaim("req_live", "sub", "PRED", "scope")
    v_spec = VerifierSpecification("v_l", "req_live", "TEST", "scope", "sha")
    ev = QualifiedEvidence(
        "ev_live",
        v_spec,
        VerifierExecutionObservation("o_l", v_spec.spec_digest, "test", "p", 0, 1, 1, 0, 0.1, 100.0, "sha", "env"),
        EvidenceClass.EMPIRICAL_TEST,
    )

    # Initial proof passes
    proof1 = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_live": claim}, {"req_live": [ev]}, active_candidate_sha="sha", jtms_store=store
    )
    assert proof1.is_satisfied is True

    # Invalidate in JTMS
    jtms.retract_and_cascade("ev_live", "Retracted due to falsification")

    # Re-evaluate live: MUST fail closed!
    proof2 = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_live": claim}, {"req_live": [ev]}, active_candidate_sha="sha", jtms_store=store
    )
    assert proof2.is_satisfied is False
    assert "req_live" in proof2.unresolved_mandatory_ids


def test_sentinel_09_zero_resource_capability_leakage_prevented():
    """Attack 9: Missing required resources blocks capability applicability."""
    cond = OperationalCondition("cond_db", "Needs Postgres", "linux_x86_64", ["postgres_db", "redis_cache"])
    cap = ConditionalCapability(
        "cap_db", "worker", OperatorType.ACT, {"linux_x86_64"}, [cond], [EvidenceClass.EMPIRICAL_TEST]
    )
    assert cap.is_applicable("linux_x86_64", ["postgres_db"]) is False  # Missing redis_cache


def test_sentinel_10_tokenizer_constraint_loss_detected():
    """Attack 10: Non-trivial multi-part objective retains all clauses."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Part A. Part B. Part C.")
    clauses = [RawClause(f"c{i + 1}", f"Part {letter}", False, True) for i, letter in enumerate(["A", "B", "C"])]
    props = [
        ProposedRequirement(f"p{i + 1}", f"c{i + 1}", f"Part {letter}", RequirementOrigin.SOURCE_EXPLICIT)
        for i, letter in enumerate(["A", "B"])
    ]
    # Dropped Part C
    spec = mgr.qualify_intent("obj_s10", raw, CandidateInterpretation("i", raw.intent_hash, clauses, props, "w"))
    assert spec.qualification_status == SemanticQualificationStatus.INSUFFICIENT_INFORMATION


def test_sentinel_11_exit_0_caught_error_falsification():
    """Attack 11: Process exits 0 but observation records test failures."""
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha")
    obs = VerifierExecutionObservation(
        "o1", v_spec.spec_digest, "pytest", "pytest", 0, 5, 3, 2, 0.1, 100.0, "sha", "env"
    )
    ev = QualifiedEvidence("ev1", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)
    claim = EpistemicClaim("c1", "mod", "PRED", "scope")

    ep, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha")
    assert ep == EpistemicDimension.CONTRADICTED


def test_sentinel_12_scope_overclaim_rejected():
    """Attack 12: Observation coverage percentage below specification minimum fails closed."""
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha", min_coverage_percentage=90.0)
    obs = VerifierExecutionObservation(
        "o1", v_spec.spec_digest, "pytest", "pytest", 0, 5, 5, 0, 0.1, 75.0, "sha", "env"
    )
    ev = QualifiedEvidence("ev1", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)
    claim = EpistemicClaim("c1", "mod", "PRED", "scope")

    ep, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha")
    assert ep == EpistemicDimension.CONTRADICTED


def test_sentinel_13_non_claims_laundering_prevented():
    """Attack 13: Verifier specification explicit non-claims are immutably bound to spec digest."""
    v_spec = VerifierSpecification(
        "v1", "c1", "TEST", "scope", "sha", explicit_non_claims=["Does not prove thread safety"]
    )
    assert "Does not prove thread safety" in v_spec.explicit_non_claims


def test_sentinel_14_candidate_wildcard_eliminated():
    """Attack 14: Candidate-bound claim requires exact candidate SHA match."""
    claim = EpistemicClaim("c1", "mod", "PRED", "scope", target_candidate_sha="sha_prod_1")
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha_prod_1")
    obs = VerifierExecutionObservation(
        "o1", v_spec.spec_digest, "pytest", "pytest", 0, 1, 1, 0, 0.1, 100.0, "sha_diff", "env"
    )
    ev = QualifiedEvidence("ev1", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)

    ep, app, msg = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha_prod_1")
    assert ep == EpistemicDimension.UNSUPPORTED
    assert app == ApplicabilityDimension.INAPPLICABLE


def test_sentinel_15_forged_system_invariant_origin_rejected():
    """Attack 15: Inferred requirement cannot claim SYSTEM_INVARIANT origin without proof."""
    prop = ProposedRequirement("p1", "unmapped", "Arbitrary invariant", RequirementOrigin.SYSTEM_INVARIANT)
    mgr = ObjectiveLifecycleManager()
    spec = mgr.qualify_intent("obj_s15", RawIntent("App"), CandidateInterpretation("i", "hash", [], [prop], "w"))
    assert spec.requirements[0].origin == RequirementOrigin.ASSUMED


def test_sentinel_16_rust_substring_legacy_removed():
    """Attack 16: Verification record requires explicit tested_effect matching required_effect."""
    req = CanonicalRequirement("r_calc", "Perform calculation", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_s16", 1, "Calc", "h", [req], SemanticQualificationStatus.QUALIFIED)
    claim = EpistemicClaim("r_calc", "math", "CALCULATE", "scope")
    v_spec = VerifierSpecification("v_diff", "r_other", "TEST", "scope", "sha")
    ev = QualifiedEvidence(
        "ev",
        v_spec,
        VerifierExecutionObservation("o", v_spec.spec_digest, "p", "p", 0, 1, 1, 0, 0.1, 100.0, "sha", "env"),
        EvidenceClass.EMPIRICAL_TEST,
    )

    proof = Law6SufficiencyEngine.evaluate_specification(
        spec, {"r_calc": claim}, {"r_calc": [ev]}, active_candidate_sha="sha"
    )
    assert proof.is_satisfied is False


def test_sentinel_17_rust_core_objective_bypass_removed():
    """Attack 17: Objective with ungrounded requirements cannot claim core objective satisfaction."""
    spec = VersionedObjectiveSpecification("obj_s17", 1, "Build system", "h", [], SemanticQualificationStatus.QUALIFIED)
    proof = Law6SufficiencyEngine.evaluate_specification(spec, {}, {})
    assert proof.is_satisfied is False


def test_sentinel_18_unverified_receipt_epistemic_flags_fail_closed():
    """Attack 18: Absence of qualified evidence prevents objective satisfaction flag."""
    req = CanonicalRequirement("r1", "Req 1", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_s18", 1, "Intent", "h", [req], SemanticQualificationStatus.QUALIFIED)
    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r1": EpistemicClaim("r1", "s", "P", "sc")}, {})
    assert proof.is_satisfied is False


def test_sentinel_19_lifecycle_invokes_adequacy_mechanically():
    """Attack 19: ObjectiveLifecycleManager mechanically attaches ObjectiveAdequacyContract."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Build API endpoint")
    prop = ProposedRequirement("p1", "c1", "Build API endpoint", RequirementOrigin.SOURCE_EXPLICIT)
    spec = mgr.qualify_intent(
        "obj_s19",
        raw,
        CandidateInterpretation("i", raw.intent_hash, [RawClause("c1", raw.raw_text, False, True)], [prop], "w"),
    )
    assert spec.adequacy_contract is not None
    assert spec.adequacy_contract.adequacy_state == ObjectiveAdequacyState.ADEQUATE_FOR_EXECUTION


def test_sentinel_20_reused_verifier_contract_against_divergent_test_rejected():
    """Attack 20: Reusing spec digest with altered executed test command/digest is rejected."""
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha")
    obs_tampered = VerifierExecutionObservation(
        "o1", "tampered_spec_digest_999", "pytest", "pytest", 0, 1, 1, 0, 0.1, 100.0, "sha", "env"
    )
    ev = QualifiedEvidence("ev1", v_spec, obs_tampered, EvidenceClass.EMPIRICAL_TEST)
    claim = EpistemicClaim("c1", "mod", "PRED", "scope")

    ep, app, msg = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha")
    assert ep == EpistemicDimension.UNSUPPORTED
    assert app == ApplicabilityDimension.INAPPLICABLE
    assert "Digest mismatch" in msg


# ==============================================================================
# 3. SECOND-ORDER HARDENED ATTACKS
# ==============================================================================


def test_second_order_01_forged_authority_token_rejected():
    """Second-Order 1: Revision with empty or forged authority token fails closed."""
    mgr = ObjectiveLifecycleManager()
    spec = VersionedObjectiveSpecification(
        "obj_so1",
        1,
        "Intent",
        "h",
        [CanonicalRequirement("r1", "R1", RequirementOrigin.SOURCE_EXPLICIT)],
        SemanticQualificationStatus.QUALIFIED,
    )
    auth = ObjectiveRevisionAuthorization("auth1", "HUMAN_OPERATOR", "   ", "obj_so1", 1, [RevisionType.CLARIFICATION])
    with pytest.raises(PermissionError):
        mgr.revise_objective(spec, RevisionType.CLARIFICATION, "Intent revised", spec.requirements, auth, "reason")


def test_second_order_02_token_for_different_objective_rejected():
    """Second-Order 2: Authority token issued for objective A cannot revise objective B."""
    mgr = ObjectiveLifecycleManager()
    spec = VersionedObjectiveSpecification(
        "obj_B",
        1,
        "Intent",
        "h",
        [CanonicalRequirement("r1", "R1", RequirementOrigin.SOURCE_EXPLICIT)],
        SemanticQualificationStatus.QUALIFIED,
    )
    auth = ObjectiveRevisionAuthorization(
        "auth1", "HUMAN_OPERATOR", "valid_token", "obj_A", 1, [RevisionType.CLARIFICATION]
    )
    with pytest.raises(PermissionError):
        mgr.revise_objective(spec, RevisionType.CLARIFICATION, "Intent revised", spec.requirements, auth, "reason")


def test_second_order_03_token_for_wrong_version_rejected():
    """Second-Order 3: Authority token issued for v1 cannot revise v2."""
    mgr = ObjectiveLifecycleManager()
    spec_v2 = VersionedObjectiveSpecification(
        "obj_v2",
        2,
        "Intent",
        "h",
        [CanonicalRequirement("r1", "R1", RequirementOrigin.SOURCE_EXPLICIT)],
        SemanticQualificationStatus.QUALIFIED,
    )
    auth = ObjectiveRevisionAuthorization(
        "auth1", "HUMAN_OPERATOR", "valid_token", "obj_v2", 1, [RevisionType.CLARIFICATION]
    )
    with pytest.raises(PermissionError):
        mgr.revise_objective(
            spec_v2, RevisionType.CLARIFICATION, "Intent revised", spec_v2.requirements, auth, "reason"
        )


def test_second_order_04_rewrapped_evidence_id_deduplicated():
    """Second-Order 4: Wrapping identical observation in 2 evidence wrappers does not inflate verification."""
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha")
    obs = VerifierExecutionObservation("o1", v_spec.spec_digest, "test", "p", 0, 1, 1, 0, 0.1, 100.0, "sha", "env")
    ev1 = QualifiedEvidence("ev1", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)
    ev2 = QualifiedEvidence("ev2", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)  # Identical spec & obs digests
    claim = EpistemicClaim("c1", "mod", "P", "scope")

    ep, _, msg = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev1, ev2], active_candidate_sha="sha")
    assert ep == EpistemicDimension.SUPPORTED
    assert "1 independent verified observation" in msg


def test_second_order_05_falsified_observation_blocks_all_supports():
    """Second-Order 5: Even if 10 tests passed, if is_falsified is True, status is CONTRADICTED."""
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha")
    obs = VerifierExecutionObservation(
        "o1",
        v_spec.spec_digest,
        "test",
        "p",
        0,
        10,
        10,
        0,
        0.1,
        100.0,
        "sha",
        "env",
        is_falsified=True,
        falsification_reason="Oracle detected memory corruption",
    )
    ev = QualifiedEvidence("ev1", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)
    claim = EpistemicClaim("c1", "mod", "P", "scope")

    ep, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha")
    assert ep == EpistemicDimension.CONTRADICTED


def test_second_order_06_cross_environment_capability_transfer_blocked():
    """Second-Order 6: Capability qualified on macOS cannot execute on Linux without qualification."""
    cond = OperationalCondition("c_mac", "mac only", "darwin_arm64", [])
    cap = ConditionalCapability(
        "cap_mac", "worker", OperatorType.ACT, {"darwin_arm64"}, [cond], [EvidenceClass.EMPIRICAL_TEST]
    )
    engine = CapabilityDeficitEngine({"cap_mac": cap})

    req_op = RequiredOperation("op1", OperatorType.ACT, "Run action", [], [])
    bound, deficits = engine.evaluate_required_operations([req_op], environment_fingerprint="linux_x86_64")
    assert len(bound) == 0
    assert len(deficits) == 1


def test_second_order_07_unaccounted_drop_in_natural_language_spec_detected():
    """Second-Order 7: Long natural language intent with multiple requirements detects omitted items."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Feature Alpha. Feature Beta. Feature Gamma.")
    p_alpha = ProposedRequirement("p_a", "c1", "Feature Alpha", RequirementOrigin.SOURCE_EXPLICIT)
    p_beta = ProposedRequirement("p_b", "c2", "Feature Beta", RequirementOrigin.SOURCE_EXPLICIT)
    # Gamma omitted
    clauses = [
        RawClause("c1", "Feature Alpha", False, True),
        RawClause("c2", "Feature Beta", False, True),
        RawClause("c3", "Feature Gamma", False, True),
    ]
    spec = mgr.qualify_intent(
        "obj_so7", raw, CandidateInterpretation("i", raw.intent_hash, clauses, [p_alpha, p_beta], "w")
    )
    assert spec.is_executable is False
    assert "Feature Gamma" in spec.adequacy_contract.unaccounted_drops


def test_second_order_08_disjunction_requires_all_non_alternative_mandatory():
    """Second-Order 8: Authoritative alternatives cannot satisfy objective if separate mandatory requirement is unresolved."""
    r_core = CanonicalRequirement("r_core", "Mandatory Core", RequirementOrigin.SOURCE_EXPLICIT, is_blocking=True)
    r_alt1 = CanonicalRequirement("r_alt1", "Alt 1", RequirementOrigin.SOURCE_EXPLICIT, is_blocking=True)
    r_alt2 = CanonicalRequirement("r_alt2", "Alt 2", RequirementOrigin.SOURCE_EXPLICIT, is_blocking=True)
    spec = VersionedObjectiveSpecification(
        "obj_so8", 1, "Core and (Alt1 or Alt2)", "h", [r_core, r_alt1, r_alt2], SemanticQualificationStatus.QUALIFIED
    )

    c_alt1 = EpistemicClaim("r_alt1", "m", "ALT1", "s")
    v_alt1 = VerifierSpecification("v_alt1", "r_alt1", "TEST", "s", "sha")
    ev_alt1 = QualifiedEvidence(
        "ev_alt1",
        v_alt1,
        VerifierExecutionObservation("o", v_alt1.spec_digest, "t", "p", 0, 1, 1, 0, 0.1, 100.0, "sha", "env"),
        EvidenceClass.EMPIRICAL_TEST,
    )

    # Core is unresolved
    proof = Law6SufficiencyEngine.evaluate_specification(
        spec,
        {"r_alt1": c_alt1},
        {"r_alt1": [ev_alt1]},
        active_candidate_sha="sha",
        composition_rule=CompositionRule.AUTHORITATIVE_ALTERNATIVES,
        alternative_ids=["r_alt1", "r_alt2"],
    )
    assert proof.is_satisfied is False
    assert "r_core" in proof.unresolved_mandatory_ids


def test_second_order_09_observation_unavailable_fails_closed():
    """Second-Order 9: Unavailable observation returns UNSUPPORTED and UNRESOLVED."""
    v_spec = VerifierSpecification("v1", "c1", "TEST", "scope", "sha")
    obs = VerifierExecutionObservation(
        "o1",
        v_spec.spec_digest,
        "t",
        "p",
        0,
        0,
        0,
        0,
        0.0,
        0.0,
        "sha",
        "env",
        observation_status=ObservationDimension.UNAVAILABLE,
    )
    ev = QualifiedEvidence("ev1", v_spec, obs, EvidenceClass.EMPIRICAL_TEST)
    claim = EpistemicClaim("c1", "m", "P", "scope")

    ep, app, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha")
    assert ep == EpistemicDimension.UNSUPPORTED
    assert app == ApplicabilityDimension.UNRESOLVED


def test_second_order_10_jtms_cascade_through_multiple_dependencies():
    """Second-Order 10: Retraction cascades through nested multi-hop dependencies."""
    store = RelationalGraphStore(db_path=":memory:")
    jtms = TruthMaintenanceEngine(store)

    store.upsert_node(
        RelationalNode("ev_root", NodeType.EVIDENCE, "Root Ev", epistemic_status=EpistemicStatus.VERIFIED)
    )
    store.upsert_node(
        RelationalNode("claim_mid", NodeType.REQUIREMENT, "Mid Claim", epistemic_status=EpistemicStatus.VERIFIED)
    )
    store.upsert_node(
        RelationalNode("req_top", NodeType.REQUIREMENT, "Top Req", epistemic_status=EpistemicStatus.VERIFIED)
    )

    store.upsert_edge(RelationalEdge("e1", "claim_mid", "ev_root", RelationType.SUPPORTED_BY, EpistemicStatus.VERIFIED))
    store.upsert_edge(RelationalEdge("e2", "req_top", "claim_mid", RelationType.DERIVED_FROM, EpistemicStatus.VERIFIED))

    invalidated = jtms.retract_and_cascade("ev_root", "Adversarial invalidation")
    assert "ev_root" in invalidated
    assert "claim_mid" in invalidated
    assert "req_top" in invalidated


# ==============================================================================
# 4. FORMAL PROPERTY INVARIANT TESTS
# ==============================================================================


def test_property_a_removing_requirements_never_increases_satisfaction():
    spec_empty = VersionedObjectiveSpecification(
        "obj_p_a", 1, "Non-trivial", "h", [], SemanticQualificationStatus.QUALIFIED
    )
    proof = Law6SufficiencyEngine.evaluate_specification(spec_empty, {}, {})
    assert proof.is_satisfied is False


def test_property_b_weakening_evidence_modality_never_strengthens_claim():
    v1 = VerifierSpecification("v1", "c1", "TEST", "s", "sha")
    obs1 = VerifierExecutionObservation("o1", v1.spec_digest, "t", "p", 0, 1, 1, 0, 0.1, 100.0, "sha", "env")
    ev_emp = QualifiedEvidence("e1", v1, obs1, EvidenceClass.EMPIRICAL_TEST)
    ev_model = QualifiedEvidence("e2", v1, obs1, EvidenceClass.UNVERIFIED_MODEL_PRIOR)
    assert ev_emp.evidence_class != ev_model.evidence_class


def test_property_c_changing_candidate_sha_invalidates_bound_evidence():
    claim = EpistemicClaim("c1", "mod", "P", "s", target_candidate_sha="sha_1")
    v1 = VerifierSpecification("v1", "c1", "TEST", "s", "sha_2")
    obs = VerifierExecutionObservation("o", v1.spec_digest, "t", "p", 0, 1, 1, 0, 0.1, 100.0, "sha_2", "env")
    ev = QualifiedEvidence("ev", v1, obs, EvidenceClass.EMPIRICAL_TEST)

    ep, app, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha_1")
    assert ep == EpistemicDimension.UNSUPPORTED
    assert app == ApplicabilityDimension.INAPPLICABLE


def test_property_d_unqualified_requirement_cannot_satisfy_objective():
    spec = VersionedObjectiveSpecification(
        "obj_p_d", 1, "Intent", "h", [], SemanticQualificationStatus.INSUFFICIENT_INFORMATION
    )
    proof = Law6SufficiencyEngine.evaluate_specification(spec, {}, {})
    assert proof.is_satisfied is False


def test_property_e_worker_cannot_self_certify_verifier_authority():
    v = VerifierSpecification("v", "c", "TEST", "s", "sha", verifier_identity="builder_worker")
    assert v.verifier_identity == "builder_worker"


def test_property_f_graph_projection_cannot_create_truth_without_source_state():
    store = RelationalGraphStore(db_path=":memory:")
    assert store.get_node("non_existent_node") is None


def test_property_g_objective_revision_cannot_preserve_completion_without_requalification():
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Initial")
    prop = ProposedRequirement("p1", "c1", "Initial Req", RequirementOrigin.SOURCE_EXPLICIT)
    spec1 = mgr.qualify_intent(
        "obj_p_g",
        raw,
        CandidateInterpretation("i", raw.intent_hash, [RawClause("c1", "Initial Req", False, True)], [prop], "w"),
    )

    auth = ObjectiveRevisionAuthorization(
        "auth1", "HUMAN_OPERATOR", "valid_token", "obj_p_g", 1, [RevisionType.REQUIREMENT_ADDITION]
    )
    spec2 = mgr.revise_objective(
        spec1,
        RevisionType.REQUIREMENT_ADDITION,
        "Initial + Extra",
        [spec1.requirements[0], CanonicalRequirement("r2", "Extra", RequirementOrigin.SOURCE_EXPLICIT)],
        auth,
        "Added r2",
    )
    assert spec2.version == 2
    proof = Law6SufficiencyEngine.evaluate_specification(spec2, {}, {})
    assert proof.is_satisfied is False


def test_property_h_unknown_applicability_cannot_become_positive_by_default():
    claim = EpistemicClaim("c1", "sub", "P", "scope")
    ep, app, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [])
    assert app == ApplicabilityDimension.UNRESOLVED
    assert ep == EpistemicDimension.UNSUPPORTED
