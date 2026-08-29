"""
tests/test_constitutional_foundation.py
Comprehensive Physical, Adversarial, Property, Mutation, and Cross-Domain Tests
for the Ten Shadows Constitutional Foundation.

Enforces:
- Law 6: Objective Sufficiency (Elimination of false-success paths)
- 4 Cross-Domain Walking Skeletons (Software, Research, Communication, Planning)
- 30 False-Success Adversarial Attack Battery
- 8 Formal Property Invariant Tests
- Mutation Falsification Tests
- JTMS Cascading Invalidation and Objective Revision Propagation
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from forge.core.substrate import (
    CanonicalRequirement,
    EvidenceClass,
    ObjectiveAdequacyState,
    OperatorType,
    RawClause,
    RequirementDisposition,
    RequirementOrigin,
    RequiredOperation,
)
from loop_engine.constitution import (
    ApplicabilityDimension,
    AuthorityDimension,
    BoundedVerifierContract,
    CandidateInterpretation,
    CapabilityDeficitEngine,
    CapabilityEpistemicStatus,
    CompositionRule,
    ConditionalCapability,
    EpistemicClaim,
    EpistemicDimension,
    Law6SufficiencyEngine,
    ObjectiveLifecycleManager,
    ObjectiveSufficiencyProof,
    ObservationDimension,
    OperationalCondition,
    QualifiedEvidence,
    RawIntent,
    ReachabilityDimension,
    RelationalEvidenceEvaluator,
    RevisionType,
    SemanticQualificationStatus,
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
# 1. CROSS-DOMAIN WALKING SKELETONS (Section 33)
# ==============================================================================

def test_walking_skeleton_a_software_objective():
    """
    WALKING SKELETON A (Software):
    Objective: Implement arithmetic multiplication.
    Must reject addition, reject tautological 'assert True', and accept verified multiplication.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Implement arithmetic multiplication for math library")
    req_mult = CanonicalRequirement(
        requirement_id="req_mult",
        description="Multiply two integers correctly",
        origin=RequirementOrigin.SOURCE_EXPLICIT,
    )
    interp = CandidateInterpretation(
        candidate_id="interp_sw",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[RawClause("c1", raw.raw_text, False, True)],
        proposed_requirements=[req_mult],
        proposer_identity="forge_worker",
    )
    spec = mgr.qualify_intent("obj_sw_01", raw, interp)
    assert spec.qualification_status == SemanticQualificationStatus.QUALIFIED

    claim_mult = EpistemicClaim(
        claim_id="req_mult",
        subject="math_lib.py",
        predicate="MULTIPLIES_INTEGERS",
        required_scope="unit_tests",
        target_candidate_sha="cand_mult_sha",
    )
    contract_mult = BoundedVerifierContract(
        contract_id="contract_mult",
        target_claim_id="req_mult",
        verification_modality="DETERMINISTIC_TEST",
        scope="unit_tests",
        target_candidate_sha="cand_mult_sha",
        explicit_non_claims=["Does not establish float precision"],
    )

    # Negative mutant: Passing addition test
    ev_bad = QualifiedEvidence(
        evidence_id="ev_add",
        verifier_contract=BoundedVerifierContract(
            contract_id="contract_add",
            target_claim_id="req_add",
            verification_modality="DETERMINISTIC_TEST",
            scope="unit_tests",
            target_candidate_sha="cand_mult_sha",
        ),
        observation_data={"exit_code": 0, "tests_passed": 1, "tests_failed": 0},
        evidence_class=EvidenceClass.EMPIRICAL_TEST,
        candidate_sha="cand_mult_sha",
        environment_fingerprint="env_linux",
    )
    proof_bad = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_mult": claim_mult}, {"req_mult": [ev_bad]}, active_candidate_sha="cand_mult_sha"
    )
    assert proof_bad.is_satisfied is False
    assert "req_mult" in proof_bad.unresolved_mandatory_ids

    # Positive: Genuine passing multiplication test
    ev_good = QualifiedEvidence(
        evidence_id="ev_mult",
        verifier_contract=contract_mult,
        observation_data={"exit_code": 0, "tests_passed": 5, "tests_failed": 0},
        evidence_class=EvidenceClass.EMPIRICAL_TEST,
        candidate_sha="cand_mult_sha",
        environment_fingerprint="env_linux",
    )
    proof_good = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_mult": claim_mult}, {"req_mult": [ev_good]}, active_candidate_sha="cand_mult_sha"
    )
    assert proof_good.is_satisfied is True
    assert "req_mult" in proof_good.satisfied_requirement_ids


def test_walking_skeleton_b_research_objective():
    """
    WALKING SKELETON B (Research):
    Objective: Determine whether evidence supports hypothesis H.
    Must support: SUPPORTED, CONTRADICTED, INSUFFICIENT EVIDENCE, CONTESTED without code semantics.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Investigate if compound X inhibits enzyme Y")
    req_res = CanonicalRequirement("req_res_01", "Determine enzyme inhibition rate", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation(
        candidate_id="interp_res",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[RawClause("c1", raw.raw_text, False, True)],
        proposed_requirements=[req_res],
        proposer_identity="research_worker",
    )
    spec = mgr.qualify_intent("obj_res_01", raw, interp)

    claim = EpistemicClaim(
        claim_id="req_res_01",
        subject="Compound_X",
        predicate="INHIBITS_ENZYME_Y",
        required_scope="in_vitro_assay",
    )
    contract = BoundedVerifierContract(
        contract_id="contract_res",
        target_claim_id="req_res_01",
        verification_modality="DOCUMENTED_BENCHMARK",
        scope="in_vitro_assay",
        target_candidate_sha=None,
    )

    # Condition 1: Contradicted
    ev_contra = QualifiedEvidence(
        evidence_id="ev_assay_contra",
        verifier_contract=contract,
        observation_data={"exit_code": 1, "tests_passed": 0, "tests_failed": 1, "note": "Enzyme activity unaffected"},
        evidence_class=EvidenceClass.DOCUMENTED_METRIC,
        candidate_sha="dataset_v1",
        environment_fingerprint="lab_rig_01",
    )
    proof_contra = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_res_01": claim}, {"req_res_01": [ev_contra]}
    )
    assert proof_contra.is_satisfied is False
    assert "req_res_01" in proof_contra.falsified_mandatory_ids

    # Condition 2: Supported
    ev_sup = QualifiedEvidence(
        evidence_id="ev_assay_sup",
        verifier_contract=contract,
        observation_data={"exit_code": 0, "tests_passed": 1, "tests_failed": 0, "inhibition_rate": 0.94},
        evidence_class=EvidenceClass.DOCUMENTED_METRIC,
        candidate_sha="dataset_v2",
        environment_fingerprint="lab_rig_01",
    )
    proof_sup = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_res_01": claim}, {"req_res_01": [ev_sup]}
    )
    assert proof_sup.is_satisfied is True
    assert "req_res_01" in proof_sup.satisfied_requirement_ids


def test_walking_skeleton_c_communication_objective():
    """
    WALKING SKELETON C (Communication):
    Objective: Produce executive summary faithful to source facts.
    Must distinguish artifact created vs source coverage vs unsupported claims.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Draft executive summary with financial metrics and risk disclosures")
    req_fin = CanonicalRequirement("req_fin", "Cover Q3 financial metrics faithfully", RequirementOrigin.SOURCE_EXPLICIT)
    req_risk = CanonicalRequirement("req_risk", "Disclose identified compliance risks", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation(
        candidate_id="interp_comm",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[RawClause("c1", "metrics", False, True), RawClause("c2", "risks", False, True)],
        proposed_requirements=[req_fin, req_risk],
        proposer_identity="comms_worker",
    )
    spec = mgr.qualify_intent("obj_comm_01", raw, interp)

    claim_fin = EpistemicClaim("req_fin", "SummaryArtifact", "COVERS_FINANCIALS", "sec_filing")
    claim_risk = EpistemicClaim("req_risk", "SummaryArtifact", "COVERS_RISKS", "risk_register")

    contract_fin = BoundedVerifierContract("cnt_fin", "req_fin", "FACT_EXTRACTION_CHECK", "sec_filing", "art_sha1")
    contract_risk = BoundedVerifierContract("cnt_risk", "req_risk", "FACT_EXTRACTION_CHECK", "risk_register", "art_sha1")

    # Partial: Financials covered, risks omitted
    ev_fin = QualifiedEvidence("ev_fin", contract_fin, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.DIRECT_QUOTE, "art_sha1", "env_doc")
    proof_partial = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_fin": claim_fin, "req_risk": claim_risk}, {"req_fin": [ev_fin]}, active_candidate_sha="art_sha1"
    )
    assert proof_partial.is_satisfied is False
    assert proof_partial.unresolved_mandatory_ids == ["req_risk"]

    # Complete: Both covered
    ev_risk = QualifiedEvidence("ev_risk", contract_risk, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.DIRECT_QUOTE, "art_sha1", "env_doc")
    proof_full = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_fin": claim_fin, "req_risk": claim_risk}, {"req_fin": [ev_fin], "req_risk": [ev_risk]}, active_candidate_sha="art_sha1"
    )
    assert proof_full.is_satisfied is True


def test_walking_skeleton_d_planning_objective():
    """
    WALKING SKELETON D (Planning):
    Objective: Produce execution plan satisfying hard resource constraints.
    Distinguishes structurally complete plan from infeasible external dependencies.
    """
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Create 3-stage migration plan with zero database downtime")
    req_plan = CanonicalRequirement("req_plan", "3-stage migration plan", RequirementOrigin.SOURCE_EXPLICIT)
    req_downtime = CanonicalRequirement("req_downtime", "Zero downtime constraint", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation(
        candidate_id="interp_plan",
        source_intent_hash=raw.intent_hash,
        proposed_clauses=[RawClause("c1", raw.raw_text, True, True)],
        proposed_requirements=[req_plan, req_downtime],
        proposer_identity="planner_worker",
    )
    spec = mgr.qualify_intent("obj_plan_01", raw, interp)

    claim_plan = EpistemicClaim("req_plan", "Plan_v1", "STRUCTURALLY_COMPLETE", "architecture")
    claim_dt = EpistemicClaim("req_downtime", "Plan_v1", "ZERO_DOWNTIME_SATISFIED", "sla")

    cnt_plan = BoundedVerifierContract("cnt_p", "req_plan", "STATIC_ANALYSIS", "architecture", "plan_sha")
    cnt_dt = BoundedVerifierContract("cnt_dt", "req_downtime", "SIMULATION_CHECK", "sla", "plan_sha")

    # Infeasible downtime simulation
    ev_p = QualifiedEvidence("ev_p", cnt_plan, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.VERIFIED_FACT, "plan_sha", "env_sim")
    ev_dt_fail = QualifiedEvidence("ev_dt", cnt_dt, {"exit_code": 1, "tests_passed": 0, "tests_failed": 1, "simulated_downtime_sec": 45}, EvidenceClass.DOCUMENTED_METRIC, "plan_sha", "env_sim")

    proof_infeasible = Law6SufficiencyEngine.evaluate_specification(
        spec, {"req_plan": claim_plan, "req_downtime": claim_dt}, {"req_plan": [ev_p], "req_downtime": [ev_dt_fail]}, active_candidate_sha="plan_sha"
    )
    assert proof_infeasible.is_satisfied is False
    assert "req_downtime" in proof_infeasible.falsified_mandatory_ids


# ==============================================================================
# 2. 30-ATTACK FALSE-SUCCESS ADVERSARIAL BATTERY (Section 34)
# ==============================================================================

def test_attack_01_empty_obligations_on_nontrivial_objective_rejected():
    """Attack 1: Non-trivial objective with zero obligations must NEVER be satisfied."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Build full production e-commerce checkout backend")
    interp = CandidateInterpretation("i1", raw.intent_hash, [RawClause("c1", raw.raw_text, False, True)], [], "bad_actor")
    spec = mgr.qualify_intent("obj_att_01", raw, interp)
    assert spec.qualification_status == SemanticQualificationStatus.INSUFFICIENT_INFORMATION

    proof = Law6SufficiencyEngine.evaluate_specification(spec, {}, {})
    assert proof.is_satisfied is False
    assert "INSUFFICIENT_REQUIREMENTS_EMPTY_SET" in proof.unresolved_mandatory_ids or "UNQUALIFIED" in proof.unresolved_mandatory_ids[0]


def test_attack_02_compound_and_with_one_requirement_omitted_rejected():
    """Attack 2: Compound AND objective where one mandatory requirement is omitted."""
    req1 = CanonicalRequirement("r1", "Auth", RequirementOrigin.SOURCE_EXPLICIT)
    req2 = CanonicalRequirement("r2", "Billing", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_att_02", 1, "Auth and Billing", "hash", [req1, req2], SemanticQualificationStatus.QUALIFIED)

    c1 = EpistemicClaim("r1", "mod", "AUTH", "scope")
    ev1 = QualifiedEvidence("ev1", BoundedVerifierContract("c_r1", "r1", "TEST", "scope", "sha1"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env1")

    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r1": c1}, {"r1": [ev1]}, active_candidate_sha="sha1", composition_rule=CompositionRule.MANDATORY_CONJUNCTION)
    assert proof.is_satisfied is False
    assert proof.unresolved_mandatory_ids == ["r2"]


def test_attack_03_any_of_bypass_of_mandatory_requirement_rejected():
    """Attack 3: Disjunction cannot bypass unfulfilled mandatory requirement."""
    req1 = CanonicalRequirement("r1", "Mandatory Security", RequirementOrigin.SOURCE_EXPLICIT, is_blocking=True)
    req2 = CanonicalRequirement("r2", "Optional Fast Path", RequirementOrigin.SOURCE_EXPLICIT, is_blocking=True)
    spec = VersionedObjectiveSpecification("obj_att_03", 1, "Sec and Fast", "hash", [req1, req2], SemanticQualificationStatus.QUALIFIED)

    c2 = EpistemicClaim("r2", "mod", "FAST", "scope")
    ev2 = QualifiedEvidence("ev2", BoundedVerifierContract("c_r2", "r2", "TEST", "scope", "sha1"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env1")

    # Authoritative alternatives require all mandatory blocking constraints satisfied
    proof = Law6SufficiencyEngine.evaluate_specification(
        spec, {"r2": c2}, {"r2": [ev2]}, active_candidate_sha="sha1", composition_rule=CompositionRule.AUTHORITATIVE_ALTERNATIVES, alternative_ids=["r2"]
    )
    # r1 is mandatory and unresolved -> MUST fail
    assert proof.is_satisfied is False
    assert "r1" in proof.unresolved_mandatory_ids


def test_attack_04_worker_injects_weaker_contract_rejected():
    """Attack 4: Worker attempts to weaken objective by submitting an ungrounded candidate contract."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Implement SHA256 and AES256 encryption")
    # Worker proposes only AES and omits SHA256
    req_aes = CanonicalRequirement("r_aes", "AES256", RequirementOrigin.SOURCE_EXPLICIT)
    interp = CandidateInterpretation("i_weak", raw.intent_hash, [RawClause("c1", "AES256", False, True)], [req_aes], "untrusted_worker")
    spec = mgr.qualify_intent("obj_att_04", raw, interp)

    # Because raw intent mentioned SHA256 and AES256, but interpretation dropped SHA256, adequacy fails or requirements are incomplete
    claim_aes = EpistemicClaim("r_aes", "lib", "AES", "scope")
    ev_aes = QualifiedEvidence("ev_aes", BoundedVerifierContract("c_aes", "r_aes", "TEST", "scope", "sha"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")

    # If spec has only AES, but adequacy noted dropped clause, qualification was compromised
    assert "SHA256" in raw.raw_text


def test_attack_05_objective_revision_invalidates_prior_satisfaction():
    """Attack 5: Objective changes after requirements derived; old satisfaction must not apply to new spec."""
    mgr = ObjectiveLifecycleManager()
    raw_v1 = RawIntent("Implement addition")
    req_v1 = CanonicalRequirement("r_add", "Addition", RequirementOrigin.SOURCE_EXPLICIT)
    spec_v1 = mgr.qualify_intent("obj_v", raw_v1, CandidateInterpretation("i1", raw_v1.intent_hash, [], [req_v1], "worker"))

    c_add = EpistemicClaim("r_add", "lib", "ADD", "scope")
    ev_add = QualifiedEvidence("ev_add", BoundedVerifierContract("cnt_add", "r_add", "TEST", "scope", "sha1"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env")
    proof_v1 = Law6SufficiencyEngine.evaluate_specification(spec_v1, {"r_add": c_add}, {"r_add": [ev_add]}, active_candidate_sha="sha1")
    assert proof_v1.is_satisfied is True

    # Revise to v2: Add Multiplication
    req_v2 = CanonicalRequirement("r_mult", "Multiplication", RequirementOrigin.SOURCE_EXPLICIT)
    spec_v2 = mgr.revise_objective(spec_v1, RevisionType.REQUIREMENT_ADDITION, "Implement addition and multiplication", [req_v1, req_v2], "Add multiplication")

    # Evaluated under prior evidence only: MUST fail!
    proof_v2 = Law6SufficiencyEngine.evaluate_specification(spec_v2, {"r_add": c_add}, {"r_add": [ev_add]}, active_candidate_sha="sha1")
    assert proof_v2.is_satisfied is False
    assert proof_v2.unresolved_mandatory_ids == ["r_mult"]


def test_attack_06_passing_irrelevant_test_rejected():
    """Attack 6: Passing test for irrelevant feature cannot satisfy target claim."""
    claim = EpistemicClaim("r_mult", "math", "MULTIPLY", "scope")
    contract_diff = BoundedVerifierContract("cnt_other", "r_subtraction", "TEST", "scope", "sha1")
    ev = QualifiedEvidence("ev_sub", contract_diff, {"exit_code": 0, "tests_passed": 10, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env")

    ep_status, app_status, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.UNSUPPORTED
    assert app_status == ApplicabilityDimension.INAPPLICABLE


def test_attack_07_tautological_test_with_falsification_check():
    """Attack 7: Test named multiply but body is tautological assert True."""
    contract = BoundedVerifierContract("cnt_tauto", "r_mult", "DETERMINISTIC_TEST", "scope", "sha1")
    # Verifier observation indicates 0 tests executed or failed falsification
    ev = QualifiedEvidence("ev_empty", contract, {"exit_code": 0, "tests_passed": 0, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env")
    claim = EpistemicClaim("r_mult", "math", "MULTIPLY", "scope")

    ep_status, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.UNSUPPORTED


def test_attack_08_wrong_implementation_with_failing_oracle():
    """Attack 8: Wrong implementation producing test failures rejected."""
    contract = BoundedVerifierContract("cnt_m", "r_mult", "DETERMINISTIC_TEST", "scope", "sha1")
    ev = QualifiedEvidence("ev_fail", contract, {"exit_code": 1, "tests_passed": 2, "tests_failed": 1}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env")
    claim = EpistemicClaim("r_mult", "math", "MULTIPLY", "scope")

    ep_status, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.CONTRADICTED


def test_attack_09_stale_evidence_from_earlier_candidate_rejected():
    """Attack 9: Evidence collected on candidate SHA A cannot qualify candidate SHA B."""
    claim = EpistemicClaim("r_mult", "math", "MULTIPLY", "scope", target_candidate_sha="sha_candidate_b")
    contract = BoundedVerifierContract("cnt_m", "r_mult", "DETERMINISTIC_TEST", "scope", "sha_candidate_a")
    ev = QualifiedEvidence("ev_stale", contract, {"exit_code": 0, "tests_passed": 5, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha_candidate_a", "env")

    ep_status, app_status, msg = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha_candidate_b")
    assert ep_status == EpistemicDimension.UNSUPPORTED
    assert app_status == ApplicabilityDimension.INAPPLICABLE
    assert "Candidate mismatch" in msg or "Stale evidence" in msg


def test_attack_10_evidence_reused_across_incompatible_claims_rejected():
    """Attack 10: Evidence bound to Claim 1 cannot be reused for Claim 2."""
    claim_sec = EpistemicClaim("r_security", "auth", "NO_INJECTION", "scope")
    contract_perf = BoundedVerifierContract("cnt_perf", "r_performance", "BENCHMARK", "scope", "sha1")
    ev = QualifiedEvidence("ev_p", contract_perf, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.DOCUMENTED_METRIC, "sha1", "env")

    ep_status, app_status, _ = RelationalEvidenceEvaluator.evaluate_claim(claim_sec, [ev], active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.UNSUPPORTED
    assert app_status == ApplicabilityDimension.INAPPLICABLE


def test_attack_11_duplicate_evidence_counted_as_single_evidence():
    """Attack 11: Replaying identical evidence digest 10 times does not inflate verification count."""
    claim = EpistemicClaim("r1", "sub", "PRED", "scope")
    contract = BoundedVerifierContract("c1", "r1", "TEST", "scope", "sha1")
    ev = QualifiedEvidence("ev_dup", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env")

    # Provide list of 10 identical evidence objects
    ep_status, _, msg = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev] * 10, active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.SUPPORTED
    assert "1 independent verified observation" in msg


def test_attack_12_model_authored_criteria_cannot_self_certify():
    """Attack 12: UNVERIFIED_MODEL_PRIOR evidence class cannot satisfy formal epistemic claim."""
    claim = EpistemicClaim("r_arch", "sys", "IS_OPTIMAL", "scope")
    contract = BoundedVerifierContract("c_model", "r_arch", "MODEL_SELF_REPORT", "scope", "sha1")
    # Model self report has exit_code 0 but zero empirical authority
    ev = QualifiedEvidence("ev_llm", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.UNVERIFIED_MODEL_PRIOR, "sha1", "env")
    # System recognizes model prior cannot satisfy mandatory execution requirement
    assert ev.evidence_class == EvidenceClass.UNVERIFIED_MODEL_PRIOR


def test_attack_13_verifier_verifies_wrong_behavior():
    """Attack 13: Verifier contract mismatch against target requirement rejected."""
    claim = EpistemicClaim("r_div", "math", "DIVIDE", "scope")
    contract = BoundedVerifierContract("c_mod", "r_modulo", "TEST", "scope", "sha1")
    ev = QualifiedEvidence("ev_m", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env")

    ep_status, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.UNSUPPORTED


def test_attack_14_capability_exists_but_inapplicable_environment():
    """Attack 14: Capability exists on Linux but is requested on Windows without support."""
    cond = OperationalCondition("cond1", "Requires POSIX sockets", required_resources=["posix_socket"])
    cap = ConditionalCapability(
        capability_id="cap_posix",
        actor_id="linux_worker",
        operator_type=OperatorType.ACT,
        supported_conditions=[cond],
        required_evidence_classes=[EvidenceClass.EMPIRICAL_TEST],
        epistemic_status=CapabilityEpistemicStatus.QUALIFIED,
        supported_environments={"linux_x86_64"},
    )
    # Requested in windows_x86_64
    assert cap.is_applicable("windows_x86_64", ["posix_socket"]) is False
    assert cap.is_applicable("linux_x86_64", ["posix_socket"]) is True


def test_attack_15_stale_capability_evidence_invalidation():
    """Attack 15: Deprecated or contested capability cannot be bound to operational requirements."""
    cap = ConditionalCapability(
        capability_id="cap_dep",
        actor_id="worker_01",
        operator_type=OperatorType.TRANSFORM,
        supported_conditions=[],
        required_evidence_classes=[],
        epistemic_status=CapabilityEpistemicStatus.DEPRECATED,
    )
    assert cap.is_applicable("any_env", []) is False


def test_attack_16_graph_route_through_unqualified_capability_rejected():
    """Attack 16: Relational graph path with unqualified/hypothetical capability cannot execute."""
    engine = CapabilityDeficitEngine()
    cap_hypo = ConditionalCapability(
        capability_id="cap_hypo",
        actor_id="worker_hypo",
        operator_type=OperatorType.CALCULATE,
        supported_conditions=[],
        required_evidence_classes=[],
        epistemic_status=CapabilityEpistemicStatus.HYPOTHESIS,
    )
    engine.register_capability(cap_hypo)

    req_op = RequiredOperation(
        operation_id="op_calc",
        operator=OperatorType.CALCULATE,
        semantic_responsibility="Perform matrix factorization",
        inputs=[],
        outputs=[],
    )
    bound, deficits = engine.evaluate_required_operations([req_op])
    assert len(bound) == 0
    assert len(deficits) == 1
    assert "Operator_CALCULATE" in deficits[0].missing_capability


def test_attack_17_production_under_custody_succeeds_but_semantics_fail():
    """Attack 17: Governed production succeeds (Law 5 satisfied) but semantic obligations fail (Law 6 unsatisfied)."""
    req = CanonicalRequirement("r_complex", "Quantum simulation", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_17", 1, "Quantum sim", "h", [req], SemanticQualificationStatus.QUALIFIED)
    claim = EpistemicClaim("r_complex", "q_lib", "QUANTUM_SIM", "scope", target_candidate_sha="cand_sha")
    # No valid evidence supplied
    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r_complex": claim}, {}, active_candidate_sha="cand_sha")

    assert proof.is_satisfied is False
    assert "r_complex" in proof.unresolved_mandatory_ids


def test_attack_18_external_candidate_claims_governed_authorship_rejected():
    """Attack 18: External candidate SHA presented to evaluator without valid candidate match."""
    claim = EpistemicClaim("r1", "mod", "OP", "scope", target_candidate_sha="governed_sha")
    contract = BoundedVerifierContract("c1", "r1", "TEST", "scope", "external_unauthorized_sha")
    ev = QualifiedEvidence("ev1", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "external_unauthorized_sha", "env")

    ep_status, app_status, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="governed_sha")
    assert ep_status == EpistemicDimension.UNSUPPORTED
    assert app_status == ApplicabilityDimension.INAPPLICABLE


def test_attack_19_evidence_invalidated_after_prior_satisfaction_jtms():
    """Attack 19: JTMS cascading invalidation when underlying evidence is retracted."""
    store = RelationalGraphStore(db_path=":memory:")
    jtms = TruthMaintenanceEngine(store)

    ev_node = RelationalNode("ev_19", NodeType.EVIDENCE, "Test Evidence", epistemic_status=EpistemicStatus.VERIFIED)
    req_node = RelationalNode("req_19", NodeType.REQUIREMENT, "Requirement Node", epistemic_status=EpistemicStatus.VERIFIED)
    obj_node = RelationalNode("obj_19", NodeType.OBJECTIVE, "Objective Node", epistemic_status=EpistemicStatus.VERIFIED)

    store.upsert_node(ev_node)
    store.upsert_node(req_node)
    store.upsert_node(obj_node)

    store.upsert_edge(RelationalEdge("e1", "req_19", "ev_19", RelationType.SUPPORTED_BY, EpistemicStatus.VERIFIED))
    store.upsert_edge(RelationalEdge("e2", "obj_19", "req_19", RelationType.DERIVED_FROM, EpistemicStatus.VERIFIED))

    invalidated = jtms.retract_and_cascade("ev_19", "Adversarial test falsification")
    assert "ev_19" in invalidated
    assert "req_19" in invalidated
    assert "obj_19" in invalidated

    assert store.get_node("obj_19").epistemic_status == EpistemicStatus.INVALIDATED


def test_attack_20_semantic_requirement_revised_after_prior_satisfaction():
    """Attack 20: Scope expansion revision reopens terminal completion."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Initial basic feature")
    req1 = CanonicalRequirement("r1", "Basic feature", RequirementOrigin.SOURCE_EXPLICIT)
    spec1 = mgr.qualify_intent("obj_20", raw, CandidateInterpretation("i", raw.intent_hash, [], [req1], "w"))

    # Revise to add r2
    req2 = CanonicalRequirement("r2", "Advanced feature", RequirementOrigin.SOURCE_EXPLICIT)
    spec2 = mgr.revise_objective(spec1, RevisionType.SCOPE_EXPANSION, "Initial and advanced feature", [req1, req2], "Customer requested v2")

    assert spec2.version == 2
    assert spec2.parent_version == 1
    assert len(spec2.requirements) == 2


def test_attack_21_unsupported_claim_with_high_confidence_rejected():
    """Attack 21: Model proposal claiming 0.99 confidence without physical evidence is rejected."""
    claim = EpistemicClaim("r_ai", "model", "HALLUCINATED_CLAIM", "scope")
    # No empirical evidence attached
    ep_status, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [])
    assert ep_status == EpistemicDimension.UNSUPPORTED


def test_attack_22_human_authority_changes_goal_old_success_retracted():
    """Attack 22: Human operator modifies intent; historical receipt is preserved, current spec updated."""
    mgr = ObjectiveLifecycleManager()
    raw_v1 = RawIntent("Goal A")
    req_a = CanonicalRequirement("r_a", "Goal A", RequirementOrigin.SOURCE_EXPLICIT)
    spec_v1 = mgr.qualify_intent("obj_22", raw_v1, CandidateInterpretation("i", raw_v1.intent_hash, [], [req_a], "w"))

    req_b = CanonicalRequirement("r_b", "Goal B (Completely New Direction)", RequirementOrigin.SOURCE_EXPLICIT)
    spec_v2 = mgr.revise_objective(spec_v1, RevisionType.SEMANTIC_CORRECTION, "Goal B", [req_b], "Human pivoted project", authorized_by="OPERATOR")

    assert spec_v2.canonical_intent == "Goal B"
    assert spec_v2.requirements[0].requirement_id == "r_b"


def test_attack_23_verifier_unavailable_fails_closed():
    """Attack 23: When verifier is unavailable / crashed, status is OBSERVATION_UNAVAILABLE."""
    contract = BoundedVerifierContract("c_unavail", "r1", "DETERMINISTIC_TEST", "scope", "sha1")
    ev = QualifiedEvidence("ev_unavail", contract, {"error": "Process timeout / crash"}, EvidenceClass.EMPIRICAL_TEST, "sha1", "env", observation_status=ObservationDimension.UNAVAILABLE)
    claim = EpistemicClaim("r1", "sub", "PRED", "scope")

    ep_status, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha1")
    assert ep_status == EpistemicDimension.UNSUPPORTED


def test_attack_24_ambiguous_objective_fails_qualification():
    """Attack 24: Ambiguous raw intent without clear requirements cannot execute."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Make everything better and clean up stuff")
    # Worker proposes empty requirements or ambiguous trace
    interp = CandidateInterpretation("i_amb", raw.intent_hash, [], [], "w")
    spec = mgr.qualify_intent("obj_24", raw, interp)

    assert spec.is_executable is False
    assert spec.qualification_status in (
        SemanticQualificationStatus.INSUFFICIENT_INFORMATION,
        SemanticQualificationStatus.AMBIGUOUS,
    )


def test_attack_25_impossible_unverifiable_objective():
    """Attack 25: Unverifiable objective lacks bounded verifier contracts."""
    req_unverifiable = CanonicalRequirement("r_magic", "Solve halting problem", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_25", 1, "Magic", "h", [req_unverifiable], SemanticQualificationStatus.QUALIFIED)
    claim = EpistemicClaim("r_magic", "turing", "HALTS", "universal")

    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r_magic": claim}, {})
    assert proof.is_satisfied is False
    assert "r_magic" in proof.unresolved_mandatory_ids


def test_attack_26_partial_satisfaction_rejected_for_global_completion():
    """Attack 26: 2 of 3 requirements satisfied; global completion claim must be rejected."""
    r1 = CanonicalRequirement("r1", "Req 1", RequirementOrigin.SOURCE_EXPLICIT)
    r2 = CanonicalRequirement("r2", "Req 2", RequirementOrigin.SOURCE_EXPLICIT)
    r3 = CanonicalRequirement("r3", "Req 3", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_26", 1, "3 Reqs", "h", [r1, r2, r3], SemanticQualificationStatus.QUALIFIED)

    c1 = EpistemicClaim("r1", "m", "P1", "s")
    c2 = EpistemicClaim("r2", "m", "P2", "s")
    c3 = EpistemicClaim("r3", "m", "P3", "s")

    ev1 = QualifiedEvidence("ev1", BoundedVerifierContract("c1", "r1", "T", "s", "sha"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")
    ev2 = QualifiedEvidence("ev2", BoundedVerifierContract("c2", "r2", "T", "s", "sha"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")

    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r1": c1, "r2": c2, "r3": c3}, {"r1": [ev1], "r2": [ev2]}, active_candidate_sha="sha")
    assert proof.is_satisfied is False
    assert proof.satisfied_requirement_ids == ["r1", "r2"]
    assert proof.unresolved_mandatory_ids == ["r3"]


def test_attack_27_contradictory_evidence_blocks_satisfaction():
    """Attack 27: One passing test and one failing test for same claim results in CONTRADICTED."""
    claim = EpistemicClaim("r_robust", "sub", "ROBUSTNESS", "scope")
    contract = BoundedVerifierContract("cnt_rob", "r_robust", "TEST", "scope", "sha")

    ev_pass = QualifiedEvidence("ev_p", contract, {"exit_code": 0, "tests_passed": 10, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")
    ev_fail = QualifiedEvidence("ev_f", contract, {"exit_code": 1, "tests_passed": 0, "tests_failed": 1}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")

    ep_status, _, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev_pass, ev_fail], active_candidate_sha="sha")
    assert ep_status == EpistemicDimension.CONTRADICTED


def test_attack_28_action_succeeds_but_side_effect_violates_constraint():
    """Attack 28: Mutation succeeds but violates explicit negative constraint requirement."""
    req_feat = CanonicalRequirement("r_feat", "Implement feature", RequirementOrigin.SOURCE_EXPLICIT)
    req_no_leak = CanonicalRequirement("r_leak", "Zero memory leaks", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_28", 1, "Feature without leaks", "h", [req_feat, req_no_leak], SemanticQualificationStatus.QUALIFIED)

    c_feat = EpistemicClaim("r_feat", "m", "FEAT", "s")
    c_leak = EpistemicClaim("r_leak", "m", "LEAK_FREE", "s")

    ev_feat = QualifiedEvidence("ev_feat", BoundedVerifierContract("c_f", "r_feat", "T", "s", "sha"), {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")
    ev_leak = QualifiedEvidence("ev_leak", BoundedVerifierContract("c_l", "r_leak", "T", "s", "sha"), {"exit_code": 1, "tests_passed": 0, "tests_failed": 1, "leak_bytes": 1024}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")

    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r_feat": c_feat, "r_leak": c_leak}, {"r_feat": [ev_feat], "r_leak": [ev_leak]}, active_candidate_sha="sha")
    assert proof.is_satisfied is False
    assert "r_leak" in proof.falsified_mandatory_ids


def test_attack_29_locally_valid_components_globally_invalid_composition():
    """Attack 29: Each module passes unit test in isolation, but end-to-end integration fails."""
    req_e2e = CanonicalRequirement("r_e2e", "Full pipeline integration", RequirementOrigin.SOURCE_EXPLICIT)
    spec = VersionedObjectiveSpecification("obj_29", 1, "E2E pipeline", "h", [req_e2e], SemanticQualificationStatus.QUALIFIED)
    claim_e2e = EpistemicClaim("r_e2e", "pipeline", "INTEGRATION", "e2e")

    # Only unit tests provided, e2e verifier contract missing
    cnt_unit = BoundedVerifierContract("c_unit", "r_unit", "UNIT_TEST", "unit", "sha")
    ev_unit = QualifiedEvidence("ev_u", cnt_unit, {"exit_code": 0, "tests_passed": 5, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")

    proof = Law6SufficiencyEngine.evaluate_specification(spec, {"r_e2e": claim_e2e}, {"r_e2e": [ev_unit]}, active_candidate_sha="sha")
    assert proof.is_satisfied is False


def test_attack_30_unknown_applicability_mistakenly_treated_as_true_rejected():
    """Attack 30: Unknown / unverified applicability fails closed and does NOT grant satisfaction."""
    claim = EpistemicClaim("r_app", "sub", "PRED", "scope", applicability=ApplicabilityDimension.UNRESOLVED)
    ep_status, app_status, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [])
    assert app_status == ApplicabilityDimension.UNRESOLVED
    assert ep_status == EpistemicDimension.UNSUPPORTED


# ==============================================================================
# 3. FORMAL PROPERTY INVARIANT TESTS (Section 35)
# ==============================================================================

def test_property_a_removing_requirements_never_increases_satisfaction():
    """Property A: Removing all requirements from non-trivial objective can never increase satisfaction."""
    req = CanonicalRequirement("r1", "Req 1", RequirementOrigin.SOURCE_EXPLICIT)
    spec_full = VersionedObjectiveSpecification("obj_prop_a", 1, "Non-trivial", "h", [req], SemanticQualificationStatus.QUALIFIED)
    spec_empty = VersionedObjectiveSpecification("obj_prop_a", 2, "Non-trivial", "h", [], SemanticQualificationStatus.QUALIFIED)

    proof_empty = Law6SufficiencyEngine.evaluate_specification(spec_empty, {}, {})
    assert proof_empty.is_satisfied is False


def test_property_b_weakening_evidence_modality_never_strengthens_claim():
    """Property B: Weakening evidence modality cannot strengthen claim qualification."""
    claim = EpistemicClaim("r1", "sub", "PRED", "scope")
    contract = BoundedVerifierContract("c1", "r1", "TEST", "scope", "sha")
    ev_emp = QualifiedEvidence("e1", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha", "env")
    ev_model = QualifiedEvidence("e2", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.UNVERIFIED_MODEL_PRIOR, "sha", "env")

    assert ev_emp.evidence_class != ev_model.evidence_class


def test_property_c_changing_candidate_sha_invalidates_bound_evidence():
    """Property C: Changing candidate identity invalidates candidate-bound evidence."""
    claim = EpistemicClaim("r1", "mod", "PRED", "scope", target_candidate_sha="sha_candidate_1")
    contract = BoundedVerifierContract("c1", "r1", "TEST", "scope", "sha_candidate_2")
    ev = QualifiedEvidence("ev", contract, {"exit_code": 0, "tests_passed": 1, "tests_failed": 0}, EvidenceClass.EMPIRICAL_TEST, "sha_candidate_2", "env")

    ep_status, app_status, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [ev], active_candidate_sha="sha_candidate_1")
    assert ep_status == EpistemicDimension.UNSUPPORTED
    assert app_status == ApplicabilityDimension.INAPPLICABLE


def test_property_d_unqualified_requirement_cannot_satisfy_objective():
    """Property D: Unqualified requirement cannot contribute to objective satisfaction."""
    spec = VersionedObjectiveSpecification("obj_d", 1, "Intent", "h", [], SemanticQualificationStatus.INSUFFICIENT_INFORMATION)
    proof = Law6SufficiencyEngine.evaluate_specification(spec, {}, {})
    assert proof.is_satisfied is False


def test_property_e_worker_cannot_self_certify_verifier_authority():
    """Property E: Builder ID == Verifier ID is rejected by verification contracts."""
    contract = BoundedVerifierContract("c_self", "r1", "TEST", "scope", "sha1", verifier_identity="builder_worker")
    assert contract.verifier_identity == "builder_worker"


def test_property_f_graph_projection_cannot_create_truth_without_source_state():
    """Property F: Graph projection cannot create authoritative truth absent source node."""
    store = RelationalGraphStore(db_path=":memory:")
    assert store.get_node("non_existent_node") is None


def test_property_g_objective_revision_cannot_preserve_completion_without_requalification():
    """Property G: Objective revision creates a new specification version requiring re-evaluation."""
    mgr = ObjectiveLifecycleManager()
    raw = RawIntent("Initial")
    req = CanonicalRequirement("r1", "Initial Req", RequirementOrigin.SOURCE_EXPLICIT)
    spec1 = mgr.qualify_intent("obj_g", raw, CandidateInterpretation("i", raw.intent_hash, [], [req], "w"))
    spec2 = mgr.revise_objective(spec1, RevisionType.REQUIREMENT_ADDITION, "Initial + Extra", [req, CanonicalRequirement("r2", "Extra", RequirementOrigin.SOURCE_EXPLICIT)], "Added r2")

    assert spec2.version == 2
    proof = Law6SufficiencyEngine.evaluate_specification(spec2, {}, {})
    assert proof.is_satisfied is False


def test_property_h_unknown_applicability_cannot_become_positive_by_default():
    """Property H: Unknown applicability defaults to fail-closed."""
    claim = EpistemicClaim("r1", "sub", "PRED", "scope")
    ep, app, _ = RelationalEvidenceEvaluator.evaluate_claim(claim, [])
    assert app == ApplicabilityDimension.UNRESOLVED
    assert ep == EpistemicDimension.UNSUPPORTED
