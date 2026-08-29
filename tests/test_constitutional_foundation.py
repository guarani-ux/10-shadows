"""
tests/test_constitutional_foundation.py
Comprehensive Physical and Adversarial Tests for Ten Shadows Constitutional Foundation.

Enforces:
- Law 6: Objective Sufficiency
- Obligation-Evidence Entailment
- Separation of Behavioral Pass from Objective Satisfaction
- Negative Control Falsification Fixture
"""

import pytest
from loop_engine.constitution import (
    EvidenceEntailment,
    ObjectiveContract,
    ObjectiveSufficiencyProof,
    Obligation,
    ObligationStatus,
    SufficiencyRule,
    SufficiencyRuleKind,
)


def test_positive_control_multiplication_objective_satisfied():
    """
    POSITIVE CONTROL:
    Objective: Implement multiplication
    Candidate: Implements multiplication
    Verifier: Tests multiplication
    Result: Obligation SATISFIED -> Objective SATISFIED -> Completion Claim AUTHORIZED.
    """
    ob_mult = Obligation(
        obligation_id="ob_mult",
        description="Implement and verify multiplication",
        required_effect="ARITHMETIC_MULTIPLICATION",
        is_mandatory=True,
    )
    contract = ObjectiveContract(
        objective_id="obj_math_01",
        canonical_intent="Add multiplication function to math library",
        obligations=[ob_mult],
        sufficiency_rule=SufficiencyRule(kind=SufficiencyRuleKind.ALL_MANDATORY),
    )

    # Verifier runs and produces machine-signed test evidence for multiplication
    test_digest = "test_run_mult_passed_sha256"
    tested_effect = "ARITHMETIC_MULTIPLICATION"

    entailment = EvidenceEntailment.verify_entailment(
        evidence_digest=test_digest,
        obligation=ob_mult,
        tested_effect=tested_effect,
    )
    assert entailment.is_applicable is True
    assert "directly tests required effect" in entailment.justification

    ob_mult.satisfy(test_digest, entailment.justification)
    proof = contract.evaluate_sufficiency()

    assert proof.is_satisfied is True
    assert "ob_mult" in proof.satisfied_obligations
    assert len(proof.unresolved_mandatory) == 0
    assert len(proof.falsified_mandatory) == 0


def test_negative_falsification_fixture_irrelevant_test_rejected():
    """
    REQUIRED FALSIFICATION FIXTURE (Negative Control):
    Objective: Add multiplication capability.
    Candidate: Makes a governed mutation.
    Verifier: Executes successfully but ONLY tests addition.
    Expected:
    - Behavioral test execution = true (passing exit code)
    - BUT multiplication obligation satisfied = FALSE
    - Semantic objective satisfied = FALSE
    - Completion claim authorized = FALSE!
    """
    ob_mult = Obligation(
        obligation_id="ob_mult",
        description="Implement and verify multiplication",
        required_effect="ARITHMETIC_MULTIPLICATION",
        is_mandatory=True,
    )
    contract = ObjectiveContract(
        objective_id="obj_math_02",
        canonical_intent="Add multiplication function to math library",
        obligations=[ob_mult],
        sufficiency_rule=SufficiencyRule(kind=SufficiencyRuleKind.ALL_MANDATORY),
    )

    # Verifier runs passing test for ADDITION, not multiplication
    test_digest = "test_run_add_passed_sha256"
    tested_effect = "ARITHMETIC_ADDITION"  # IRRELEVANT EFFECT!

    entailment = EvidenceEntailment.verify_entailment(
        evidence_digest=test_digest,
        obligation=ob_mult,
        tested_effect=tested_effect,
    )
    assert entailment.is_applicable is False
    assert "Irrelevant Evidence" in entailment.justification

    # Attempting to falsify or leaving unresolved
    ob_mult.falsify(entailment.justification)
    proof = contract.evaluate_sufficiency()

    # MUST NOT be satisfied!
    assert proof.is_satisfied is False
    assert len(proof.satisfied_obligations) == 0
    assert "ob_mult" in proof.falsified_mandatory


def test_incomplete_obligation_coverage_blocks_sufficiency():
    """
    Attack Vector 2: Candidate satisfies 1 of 2 mandatory obligations.
    Objective sufficiency MUST be false.
    """
    ob1 = Obligation("ob1", "Add multiplication", "ARITHMETIC_MULTIPLICATION", is_mandatory=True)
    ob2 = Obligation("ob2", "Add division", "ARITHMETIC_DIVISION", is_mandatory=True)

    contract = ObjectiveContract(
        objective_id="obj_math_multi",
        canonical_intent="Add multiplication and division",
        obligations=[ob1, ob2],
        sufficiency_rule=SufficiencyRule(kind=SufficiencyRuleKind.ALL_MANDATORY),
    )

    # Only ob1 is satisfied
    ob1.satisfy("digest_mult", "Multiplication verified")
    proof = contract.evaluate_sufficiency()

    assert proof.is_satisfied is False
    assert proof.unresolved_mandatory == ["ob2"]


from loop_engine.relational.graph_db import RelationalGraphStore
from loop_engine.relational.schema import (
    EpistemicStatus,
    NodeType,
    RelationalEdge,
    RelationalNode,
    RelationType,
)
from loop_engine.relational.truth_maintenance import TruthMaintenanceEngine


def test_sufficiency_reopening_upon_evidence_invalidation():
    """
    Attack Vector 22: Satisfied objective reopened when underlying evidence is invalidated.
    """
    store = RelationalGraphStore(db_path=":memory:")
    jtms = TruthMaintenanceEngine(store)

    ev_node = RelationalNode(
        node_id="ev_mult_test",
        node_type=NodeType.EVIDENCE,
        label="Multiplication test evidence",
        epistemic_status=EpistemicStatus.VERIFIED,
    )
    ob_node = RelationalNode(
        node_id="ob_mult_satisfied",
        node_type=NodeType.REQUIREMENT,
        label="Multiplication obligation",
        epistemic_status=EpistemicStatus.VERIFIED,
    )
    obj_node = RelationalNode(
        node_id="objective_accomplished",
        node_type=NodeType.OBJECTIVE,
        label="Math enhancement objective",
        epistemic_status=EpistemicStatus.VERIFIED,
    )

    store.upsert_node(ev_node)
    store.upsert_node(ob_node)
    store.upsert_node(obj_node)

    # Edge: ob_mult_satisfied is SUPPORTED_BY ev_mult_test
    store.upsert_edge(RelationalEdge(
        edge_id="edge_ev_ob",
        source_id="ob_mult_satisfied",
        target_id="ev_mult_test",
        relation_type=RelationType.SUPPORTED_BY,
        epistemic_status=EpistemicStatus.VERIFIED,
    ))
    # Edge: objective_accomplished is DERIVED_FROM ob_mult_satisfied
    store.upsert_edge(RelationalEdge(
        edge_id="edge_ob_obj",
        source_id="objective_accomplished",
        target_id="ob_mult_satisfied",
        relation_type=RelationType.DERIVED_FROM,
        epistemic_status=EpistemicStatus.VERIFIED,
    ))

    assert store.get_node("objective_accomplished").epistemic_status == EpistemicStatus.VERIFIED

    # Invalidate evidence (e.g. found test flakiness or proxy metric)
    invalidated = jtms.retract_and_cascade("ev_mult_test", "Flaky proxy test discovered")

    assert "ev_mult_test" in invalidated
    assert "ob_mult_satisfied" in invalidated
    assert "objective_accomplished" in invalidated

    # Cascading retraction MUST invalidate downstream objective accomplishment!
    assert store.get_node("ob_mult_satisfied").epistemic_status == EpistemicStatus.INVALIDATED
    assert store.get_node("objective_accomplished").epistemic_status == EpistemicStatus.INVALIDATED


def test_any_of_sufficiency_rule():
    """
    Tests disjunctive (ANY_OF) sufficiency rule.
    """
    ob_primary = Obligation("ob_primary", "Primary method", "METHOD_A", is_mandatory=False)
    ob_fallback = Obligation("ob_fallback", "Fallback method", "METHOD_B", is_mandatory=False)

    contract = ObjectiveContract(
        objective_id="obj_any_of",
        canonical_intent="Execute via primary or fallback",
        obligations=[ob_primary, ob_fallback],
        sufficiency_rule=SufficiencyRule(
            kind=SufficiencyRuleKind.ANY_OF,
            details=["ob_primary", "ob_fallback"],
        ),
    )

    ob_fallback.satisfy("digest_fb", "Fallback verified")
    proof = contract.evaluate_sufficiency()

    assert proof.is_satisfied is True
    assert proof.satisfied_obligations == ["ob_fallback"]
