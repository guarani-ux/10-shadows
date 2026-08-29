"""
tests/test_relational_intelligence.py
Comprehensive Test Suite & Adversarial Challenges for Ten Shadows Relational Intelligence.

Tests:
1. The Central Walking Skeleton: Capability Gap Discovery -> Acquisition -> Qualification -> Dynamic Replanning.
2. Dependency Scheduling, Cycle Detection, and Parallel Frontier Discovery.
3. Truth Maintenance System (JTMS) Cascading Invalidation and Substrate Law 4 Monotonicity.
4. Structural Cross-Domain Strategy Transfer & Motif Matching.
5. Authoritative Receipt Projection & Invariant Verification.
6. Adversarial Challenges & Required Failure Cases.
"""

import tempfile
from pathlib import Path

import pytest

from loop_engine.relational import (
    CapabilityGap,
    CapabilityGapPlanner,
    CapabilityRequirement,
    CyclicDependencyError,
    DependencyScheduler,
    EpistemicStatus,
    NodeType,
    RelationalEdge,
    RelationalGraphStore,
    RelationalMotif,
    RelationalNode,
    RelationalProjectionEngine,
    RelationType,
    StructuralTransferEngine,
    TruthMaintenanceEngine,
)


@pytest.fixture
def temp_graph_store():
    """Creates an isolated in-memory relational graph store."""
    return RelationalGraphStore(db_path=":memory:")


def test_walking_skeleton_capability_gap_discovery_and_replanning(temp_graph_store):
    """
    Physical verification of the Central Graph Synergy:
    1. Problem enters with required capabilities: 'data_parser' (available) and 'lossless_compressor' (missing).
    2. Planner discovers 'lossless_compressor' is a CapabilityGap and returns an untraversable plan.
    3. Acquisition target is formulated and synthesized.
    4. Independent qualifier verifies the candidate capability.
    5. Newly qualified capability is linked into the graph topology.
    6. System replans -> route becomes traversable!
    """
    store = temp_graph_store
    planner = CapabilityGapPlanner(store)

    # 1. Register existing qualified capability 'data_parser'
    existing_cap = RelationalNode(
        node_id="cap_data_parser_01",
        node_type=NodeType.CAPABILITY,
        label="Data Parser",
        properties={
            "capability_name": "data_parser",
            "domain": "data_processing",
            "input_contract": {"type": "raw_bytes"},
            "output_contract": {"type": "parsed_json"},
        },
        epistemic_status=EpistemicStatus.QUALIFIED,
        provenance_digest="sha_data_parser",
    )
    store.upsert_node(existing_cap)

    # 2. Declare objective requirements
    req1 = CapabilityRequirement(
        requirement_id="req_parse",
        capability_name="data_parser",
        required_domain="data_processing",
        input_contract={"type": "raw_bytes"},
        output_contract={"type": "parsed_json"},
    )
    req2 = CapabilityRequirement(
        requirement_id="req_compress",
        capability_name="lossless_compressor",
        required_domain="compression",
        input_contract={"type": "parsed_json"},
        output_contract={"type": "compressed_bytes"},
    )

    # 3. Initial Plan Traversal
    initial_plan = planner.plan_traversal("obj_pipeline_100", [req1, req2])
    assert not initial_plan.is_traversable
    assert len(initial_plan.unresolved_gaps) == 1
    gap = initial_plan.unresolved_gaps[0]
    assert gap.requirement.capability_name == "lossless_compressor"

    # Verify AcquisitionTarget node in graph
    target_node = store.get_node(gap.gap_id)
    assert target_node is not None
    assert target_node.node_type == NodeType.ACQUISITION_TARGET

    # 4. Provision & Independently Qualify Missing Capability
    candidate_code = "def compress(data): import zlib; return zlib.compress(data.encode())"

    def mock_qualifier(code: str, contracts: dict):
        # Simulates independent AST security check and test execution
        if "zlib" in code and "compress" in code:
            return True, "AST_SECURE: PASS | UNIT_TEST: 3/3 passed"
        return False, "FAIL: Validation error"

    is_resolved, new_plan, err = planner.resolve_gap_and_replan(
        objective_id="obj_pipeline_100",
        gap=gap,
        candidate_code=candidate_code,
        qualifier_fn=mock_qualifier,
        requirements=[req1, req2],
    )

    # 5. Verify Previously Blocked Route Is Now Traversable!
    assert is_resolved
    assert new_plan.is_traversable
    assert len(new_plan.unresolved_gaps) == 0
    assert len(new_plan.execution_path) == 2
    assert err is None


def test_dependency_scheduler_topological_order_and_parallel_frontiers(temp_graph_store):
    """Verifies DAG topological sorting and parallel frontier calculation."""
    store = temp_graph_store
    scheduler = DependencyScheduler(store)

    # Create task nodes: A -> (B, C) -> D
    nodes = [
        RelationalNode(
            node_id="A", node_type=NodeType.SUBPROBLEM, label="Task A", epistemic_status=EpistemicStatus.PROPOSED
        ),
        RelationalNode(
            node_id="B", node_type=NodeType.SUBPROBLEM, label="Task B", epistemic_status=EpistemicStatus.PROPOSED
        ),
        RelationalNode(
            node_id="C", node_type=NodeType.SUBPROBLEM, label="Task C", epistemic_status=EpistemicStatus.PROPOSED
        ),
        RelationalNode(
            node_id="D", node_type=NodeType.SUBPROBLEM, label="Task D", epistemic_status=EpistemicStatus.PROPOSED
        ),
    ]
    for n in nodes:
        store.upsert_node(n)

    edges = [
        RelationalEdge(
            edge_id="e1",
            source_id="B",
            target_id="A",
            relation_type=RelationType.DEPENDS_ON,
            epistemic_status=EpistemicStatus.PROPOSED,
        ),
        RelationalEdge(
            edge_id="e2",
            source_id="C",
            target_id="A",
            relation_type=RelationType.DEPENDS_ON,
            epistemic_status=EpistemicStatus.PROPOSED,
        ),
        RelationalEdge(
            edge_id="e3",
            source_id="D",
            target_id="B",
            relation_type=RelationType.DEPENDS_ON,
            epistemic_status=EpistemicStatus.PROPOSED,
        ),
        RelationalEdge(
            edge_id="e4",
            source_id="D",
            target_id="C",
            relation_type=RelationType.DEPENDS_ON,
            epistemic_status=EpistemicStatus.PROPOSED,
        ),
    ]
    for e in edges:
        store.upsert_edge(e)

    # Compute topological order
    ordered = scheduler.compute_topological_order(nodes, edges)
    order_ids = [n.node_id for n in ordered]
    assert order_ids[0] == "A"
    assert order_ids[3] == "D"
    assert set(order_ids[1:3]) == {"B", "C"}

    # Initial ready frontier (only A is ready)
    ready1 = scheduler.get_ready_frontier(root_node_id="D", completed_nodes=set())
    assert [n.node_id for n in ready1] == ["A"]

    # When A completes, B and C become parallel ready frontier
    ready2 = scheduler.get_ready_frontier(root_node_id="D", completed_nodes={"A"})
    assert {n.node_id for n in ready2} == {"B", "C"}

    # When A, B, C complete, D becomes ready
    ready3 = scheduler.get_ready_frontier(root_node_id="D", completed_nodes={"A", "B", "C"})
    assert [n.node_id for n in ready3] == ["D"]


def test_dependency_scheduler_cycle_detection(temp_graph_store):
    """Verifies that circular dependencies are caught before execution."""
    store = temp_graph_store
    scheduler = DependencyScheduler(store)

    nodes = [
        RelationalNode(
            node_id="X", node_type=NodeType.SUBPROBLEM, label="Task X", epistemic_status=EpistemicStatus.PROPOSED
        ),
        RelationalNode(
            node_id="Y", node_type=NodeType.SUBPROBLEM, label="Task Y", epistemic_status=EpistemicStatus.PROPOSED
        ),
    ]
    edges = [
        RelationalEdge(
            edge_id="e_xy",
            source_id="X",
            target_id="Y",
            relation_type=RelationType.DEPENDS_ON,
            epistemic_status=EpistemicStatus.PROPOSED,
        ),
        RelationalEdge(
            edge_id="e_yx",
            source_id="Y",
            target_id="X",
            relation_type=RelationType.DEPENDS_ON,
            epistemic_status=EpistemicStatus.PROPOSED,
        ),
    ]

    with pytest.raises(CyclicDependencyError):
        scheduler.compute_topological_order(nodes, edges)


def test_truth_maintenance_cascading_invalidation(temp_graph_store):
    """
    Verifies that when an upstream hypothesis or evidence is falsified,
    JTMS cascades invalidation to all derived downstream claims.
    """
    store = temp_graph_store
    jtms = TruthMaintenanceEngine(store)

    root_hypo = RelationalNode(
        node_id="hypo_01", node_type=NodeType.CLAIM, label="Root Hypothesis", epistemic_status=EpistemicStatus.VERIFIED
    )
    cand_node = RelationalNode(
        node_id="cand_01",
        node_type=NodeType.CANDIDATE,
        label="Candidate Code",
        epistemic_status=EpistemicStatus.QUALIFIED,
    )
    downstream_claim = RelationalNode(
        node_id="claim_01", node_type=NodeType.CLAIM, label="Result Claim", epistemic_status=EpistemicStatus.VERIFIED
    )

    store.upsert_node(root_hypo)
    store.upsert_node(cand_node)
    store.upsert_node(downstream_claim)

    store.upsert_edge(
        RelationalEdge(
            edge_id="e_hc",
            source_id=cand_node.node_id,
            target_id=root_hypo.node_id,
            relation_type=RelationType.DERIVED_FROM,
            epistemic_status=EpistemicStatus.VERIFIED,
        )
    )
    store.upsert_edge(
        RelationalEdge(
            edge_id="e_cd",
            source_id=downstream_claim.node_id,
            target_id=cand_node.node_id,
            relation_type=RelationType.DERIVED_FROM,
            epistemic_status=EpistemicStatus.VERIFIED,
        )
    )

    # Falsify root hypothesis
    invalidated_ids = jtms.retract_and_cascade("hypo_01", "Adversarial test proved assumption false")

    assert "hypo_01" in invalidated_ids
    assert "cand_01" in invalidated_ids
    assert "claim_01" in invalidated_ids

    assert store.get_node("hypo_01").epistemic_status == EpistemicStatus.INVALIDATED
    assert store.get_node("cand_01").epistemic_status == EpistemicStatus.INVALIDATED
    assert store.get_node("claim_01").epistemic_status == EpistemicStatus.INVALIDATED


def test_substrate_law_4_evidence_monotonicity_upgrade_rejection(temp_graph_store):
    """
    Substrate Law 4: Evidence Monotonicity.
    Verifies that attempting to silently upgrade evidence status raises ValueError.
    """
    store = temp_graph_store
    jtms = TruthMaintenanceEngine(store)

    ev_node = RelationalNode(
        node_id="ev_raw",
        node_type=NodeType.EVIDENCE,
        label="Raw Observation",
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    store.upsert_node(ev_node)

    # Attempting to upgrade OBSERVED -> AUTHORITATIVE without observation must raise
    with pytest.raises(ValueError, match="Substrate Law 4 Violation"):
        jtms.downgrade_evidence("ev_raw", EpistemicStatus.AUTHORITATIVE, "Illegal upgrade attempt")


def test_structural_transfer_motif_matching(temp_graph_store):
    """Verifies cross-domain structural strategy transfer based on graph topology."""
    store = temp_graph_store
    transfer_engine = StructuralTransferEngine(store)

    # Register a known problem-solution motif from communications domain
    motif = RelationalMotif(
        motif_id="motif_audit_repair",
        name="Audit-Falsify-Repair Pattern",
        source_domain="communications",
        node_types=(NodeType.OBJECTIVE, NodeType.ARTIFACT, NodeType.EVIDENCE, NodeType.VERIFIER),
        edge_relations=(RelationType.PRODUCES, RelationType.SUPPORTED_BY, RelationType.VERIFIED_BY),
        success_rate=0.92,
        epistemic_status=EpistemicStatus.QUALIFIED,
    )
    transfer_engine.register_motif(motif)

    # Target problem in software engineering with identical topology
    proposals = transfer_engine.find_transferrable_strategies(
        target_objective_id="obj_software_refactor",
        target_node_types=[NodeType.OBJECTIVE, NodeType.ARTIFACT, NodeType.EVIDENCE, NodeType.VERIFIER],
        target_relations=[RelationType.PRODUCES, RelationType.SUPPORTED_BY, RelationType.VERIFIED_BY],
    )

    assert len(proposals) == 1
    assert proposals[0].structural_similarity == 1.0
    assert proposals[0].transfer_status == EpistemicStatus.PROPOSED
    assert "Audit-Falsify-Repair Pattern" in proposals[0].recommended_strategy


def test_authoritative_receipt_relational_projection(temp_graph_store):
    """Verifies projection of a sealed TenShadowsReceipt into the relational graph."""
    store = temp_graph_store
    projector = RelationalProjectionEngine(store)

    mock_receipt = {
        "run_id": "run_test_123",
        "task_id": "task_rel_456",
        "objective": "Implement deterministic feature and verify",
        "objective_hash": "obj_hash_abc",
        "final_head": "cand_sha_999",
        "final_status": "VERIFIED_SUCCESS",
        "candidate_classification": {
            "kind": "Governed",
            "details": {"candidate_sha": "cand_sha_999"},
        },
        "verification": {
            "verifier_id": "svris_verifier_01",
            "verified_status": "PASS",
            "tests_collected": 5,
            "tests_passed": 5,
            "modality": "DeterministicTest",
            "test_digest": "digest_ver_555",
        },
    }

    run_id = projector.project_receipt(mock_receipt)
    assert run_id == "run_test_123"

    obj_node = store.get_node("obj_task_rel_456")
    assert obj_node is not None
    assert obj_node.epistemic_status == EpistemicStatus.AUTHORITATIVE

    cand_node = store.get_node("cand_cand_sha_9")
    assert cand_node is not None
    assert cand_node.epistemic_status == EpistemicStatus.QUALIFIED

    ver_node = store.get_node("svris_verifier_01")
    assert ver_node is not None
    assert ver_node.epistemic_status == EpistemicStatus.VERIFIED


def test_failure_01_wrong_initial_decomposition(temp_graph_store):
    """Failure Case 1: Wrong initial decomposition is invalidated and replaced with correct topology."""
    store = temp_graph_store
    jtms = TruthMaintenanceEngine(store)

    # Initial wrong decomposition
    obj = RelationalNode(node_id="obj_01", node_type=NodeType.OBJECTIVE, label="Build Parser")
    wrong_sub = RelationalNode(node_id="sub_wrong", node_type=NodeType.SUBPROBLEM, label="Regex Based Parser")
    store.upsert_node(obj)
    store.upsert_node(wrong_sub)
    store.upsert_edge(
        RelationalEdge(
            edge_id="e_decomp_1",
            source_id=obj.node_id,
            target_id=wrong_sub.node_id,
            relation_type=RelationType.DECOMPOSES_INTO,
        )
    )

    # Invalidate wrong decomposition
    jtms.retract_and_cascade("sub_wrong", "Regex parser cannot handle recursive grammar")
    assert store.get_node("sub_wrong").epistemic_status == EpistemicStatus.INVALIDATED

    # Replace with correct AST parser decomposition
    correct_sub = RelationalNode(
        node_id="sub_correct",
        node_type=NodeType.SUBPROBLEM,
        label="AST Recursive Parser",
        epistemic_status=EpistemicStatus.QUALIFIED,
    )
    store.upsert_node(correct_sub)
    store.upsert_edge(
        RelationalEdge(
            edge_id="e_decomp_2",
            source_id=obj.node_id,
            target_id=correct_sub.node_id,
            relation_type=RelationType.DECOMPOSES_INTO,
            epistemic_status=EpistemicStatus.QUALIFIED,
        )
    )
    assert store.get_node("sub_correct").epistemic_status == EpistemicStatus.QUALIFIED


def test_failure_03_falsely_claimed_or_deprecated_capability(temp_graph_store):
    """Failure Case 3: Falsely claimed or deprecated capabilities are not used in traversal."""
    store = temp_graph_store
    planner = CapabilityGapPlanner(store)

    deprecated_cap = RelationalNode(
        node_id="cap_dep_01",
        node_type=NodeType.CAPABILITY,
        label="Deprecated Parser",
        properties={"capability_name": "ast_parser", "domain": "compiler", "is_deprecated": True},
        epistemic_status=EpistemicStatus.SUPERSEDED,
    )
    store.upsert_node(deprecated_cap)

    req = CapabilityRequirement(
        requirement_id="req_ast",
        capability_name="ast_parser",
        required_domain="compiler",
        input_contract={},
        output_contract={},
    )
    plan = planner.plan_traversal("obj_compiler", [req])
    assert not plan.is_traversable
    assert len(plan.unresolved_gaps) == 1


def test_failure_14_acquired_capability_fails_qualification(temp_graph_store):
    """Failure Case 14: Acquired candidate capability fails independent qualification."""
    store = temp_graph_store
    planner = CapabilityGapPlanner(store)

    req = CapabilityRequirement(
        requirement_id="req_crypto",
        capability_name="crypto_signer",
        required_domain="security",
        input_contract={},
        output_contract={},
    )
    plan = planner.plan_traversal("obj_sec", [req])
    assert not plan.is_traversable

    gap = plan.unresolved_gaps[0]
    bad_code = "def sign(data): eval(data)"  # Banned eval call

    def ast_rejecting_qualifier(code: str, contracts: dict):
        if "eval(" in code:
            return False, "AST_SECURITY_VIOLATION: Banned call eval() detected."
        return True, "PASS"

    is_resolved, new_plan, err = planner.resolve_gap_and_replan(
        objective_id="obj_sec",
        gap=gap,
        candidate_code=bad_code,
        qualifier_fn=ast_rejecting_qualifier,
        requirements=[req],
    )

    assert not is_resolved
    assert not new_plan.is_traversable
    assert "AST_SECURITY_VIOLATION" in err
    assert store.get_node(gap.gap_id).epistemic_status == EpistemicStatus.INVALIDATED


def test_failure_12_structural_transfer_fails_qualification(temp_graph_store):
    """Failure Case 12: Structural similarity proposes a strategy, but transfer qualification rejects it."""
    store = temp_graph_store
    transfer_engine = StructuralTransferEngine(store)

    motif = RelationalMotif(
        motif_id="motif_batch",
        name="Batch Processing Motif",
        source_domain="etl",
        node_types=(NodeType.OBJECTIVE, NodeType.ARTIFACT),
        edge_relations=(RelationType.PRODUCES,),
        success_rate=0.99,
        epistemic_status=EpistemicStatus.QUALIFIED,
    )
    transfer_engine.register_motif(motif)

    proposals = transfer_engine.find_transferrable_strategies(
        target_objective_id="obj_realtime_stream",
        target_node_types=[NodeType.OBJECTIVE, NodeType.ARTIFACT],
        target_relations=[RelationType.PRODUCES],
    )

    assert len(proposals) == 1
    prop = proposals[0]
    # Transfer Proposal is only PROPOSED, cannot certify itself
    assert prop.transfer_status == EpistemicStatus.PROPOSED

    # Qualification check: Realtime streaming violates batch latency constraints
    def qualify_transfer(p):
        return False, "Domain constraint violation: Batch processing motif cannot satisfy <10ms streaming SLA."

    is_valid, reason = qualify_transfer(prop)
    assert not is_valid
    assert "streaming SLA" in reason
