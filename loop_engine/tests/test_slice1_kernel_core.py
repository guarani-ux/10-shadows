import time
from pathlib import Path

import pytest

from loop_engine.canonical_objective import (
    CanonicalObjective,
    ConstraintSet,
    EvidenceReference,
    UnknownReference,
)
from loop_engine.context import RunContext, resolve_physical_commit_sha
from loop_engine.kernel_db import KernelDatabase


def test_canonical_objective_determinism_and_normalization():
    """Proves CanonicalObjective computes deterministic hash and normalizes raw input."""
    raw = {
        "objective_id": "obj_solar_explainer",
        "description": "Produce 60s explainer on community microgrids",
        "desired_outcome": "Drive citizen engagement on portal",
        "verified_evidence": [
            {
                "evidence_id": "ev_01",
                "source_description": "Microgrid reduced peak outages by 94%",
                "confidence": "DOCUMENTED_METRIC",
            }
        ],
        "explicit_unknowns": [
            {
                "unknown_id": "unk_01",
                "description": "Substation clearance pending",
                "classification": "ASSUMPTION_REQUIRING_APPROVAL",
            }
        ],
    }

    obj1 = CanonicalObjective.normalize_raw_input(raw)
    obj2 = CanonicalObjective.normalize_raw_input(raw)

    hash1 = obj1.compute_canonical_hash()
    hash2 = obj2.compute_canonical_hash()

    assert hash1 == hash2
    assert len(hash1) == 64
    assert obj1.constraints.target_duration_seconds == 60
    assert obj1.verified_evidence[0].evidence_id == "ev_01"


def test_run_context_deterministic_hashing_and_physical_commit():
    """Proves RunContext produces deterministic input hashes and resolves physical Git SHA."""
    raw_payload = {"task": "verify_core_physics", "budget": 100}

    ctx1 = RunContext.create(
        task_id="task_test_01",
        shadow_id=3,
        domain_code="herald",
        raw_objective=raw_payload,
        run_id_suffix="fixed_suffix",
    )

    # Simulate delay to guarantee time has elapsed
    time.sleep(0.01)

    ctx2 = RunContext.create(
        task_id="task_test_01",
        shadow_id=3,
        domain_code="herald",
        raw_objective=raw_payload,
        run_id_suffix="fixed_suffix",
    )

    # Invariant: canonical_input_hash must be identical regardless of invocation time
    assert ctx1.canonical_input_hash == ctx2.canonical_input_hash
    assert ctx1.objective_hash == ctx2.objective_hash

    # Invariant: source_commit must be a 40-character hexadecimal string
    assert len(ctx1.source_commit) == 40
    assert ctx1.source_commit != "HEAD"
    assert ctx1.source_commit != "UNKNOWN_COMMIT"


def test_run_context_child_inheritance_and_status_transitions():
    """Proves child RunContext inherits parent metadata and records transition history."""
    parent = RunContext.create(
        task_id="parent_media_pipeline",
        shadow_id=10,
        domain_code="gamemaster",
        raw_objective={"goal": "Multi-Shadow Media Pipeline"},
        authority_level="HUMAN_REQUIRED",
    )

    child = parent.create_child(
        shadow_id=3,
        domain_code="herald",
        step_id="step_script_gen",
        step_input={"brief": "Draft Script"},
    )

    assert child.parent_run_id == parent.run_id
    assert child.source_commit == parent.source_commit
    assert child.authority_level == "HUMAN_REQUIRED"
    assert child.shadow_id == 3
    assert child.domain_code == "herald"

    # Status transition verification
    child.transition_status("ESCALATED", reason="UNRESOLVED_FACTUAL_CONFLICT")
    assert child.status == "ESCALATED"
    assert len(child.status_history) == 2
    assert child.status_history[1]["status"] == "ESCALATED"
    assert child.status_history[1]["reason"] == "UNRESOLVED_FACTUAL_CONFLICT"


def test_kernel_database_transactional_operations(tmp_path):
    """Proves KernelDatabase executes unified transactional records for runs, escalations, and approvals."""
    db_file = tmp_path / "scratch" / "test_kernel.db"
    db = KernelDatabase(db_path=db_file)

    # 1. Record Run State
    db.record_run_state(
        run_id="run_root_001",
        task_id="task_001",
        shadow_id=10,
        domain_code="gamemaster",
        source_commit="cac1a8053abf80880bf32b54f05c0c001b5a4af9",
        objective_hash="a1b2c3d4e5f6",
        canonical_input_hash="112233445566",
        status="RUNNING",
        authority_level="HUMAN_REQUIRED",
        status_history=[{"status": "RUNNING", "timestamp": "2026-08-26T00:00:00Z"}],
    )

    run_record = db.get_run("run_root_001")
    assert run_record is not None
    assert run_record["task_id"] == "task_001"
    assert run_record["status"] == "RUNNING"
    assert run_record["status_history"][0]["status"] == "RUNNING"

    # 2. Record Escalation
    db.record_escalation(
        escalation_id="esc_001",
        run_id="child_run_002",
        parent_run_id="run_root_001",
        task_id="task_001_step_herald",
        shadow_id=3,
        category="UNRESOLVED_FACTUAL_CONFLICT",
        reason="Conflicting energy capacity numbers between source doc A and B.",
        details={"doc_a": "500 kWh", "doc_b": "750 kWh"},
        remediation_options=["Use 500 kWh conservative metric", "Escalate to operator"],
    )

    # 3. Record Approval & Verify Resolution Transition
    db.record_approval(
        approval_id="appr_001",
        escalation_id="esc_001",
        parent_run_id="run_root_001",
        human_authority="Operator_Primary",
        decision="APPROVED",
        decision_payload={"selected_metric": "500 kWh"},
        resulting_plan_hash="plan_hash_9999",
        resumed_step_id="step_herald",
    )

    with db.get_connection() as conn:
        esc_row = conn.execute("SELECT * FROM escalations WHERE escalation_id = 'esc_001'").fetchone()
        assert esc_row["status"] == "RESOLVED_APPROVED"

        appr_row = conn.execute("SELECT * FROM approvals WHERE approval_id = 'appr_001'").fetchone()
        assert appr_row["human_authority"] == "Operator_Primary"
        assert appr_row["resumed_step_id"] == "step_herald"
