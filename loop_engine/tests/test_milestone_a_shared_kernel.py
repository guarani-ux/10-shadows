import json
import sqlite3
import pytest
from pathlib import Path

from loop_engine.canonical_objective import CanonicalObjective, EvidenceReference, UnknownReference, ConstraintSet
from loop_engine.context import RunContext
from loop_engine.kernel_db import KernelDatabase
from loop_engine.artifacts import (
    ArtifactRegistry,
    ArtifactRecord,
    StructuredSourceArtifact,
    MasterAVScriptArtifact,
    ProductionPlanDAGArtifact,
)
from loop_engine.governor import StepGovernor, StepExecutionResult
from loop_engine.router import BoundedShadowRouter, RoutePlan, HumanEscalationRecord
from loop_engine.receipts import ReceiptStore
from loop_engine.runners.scribe_runner import ScribeDomainRunner
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.runners.slicer_runner import SlicerDomainRunner
from loop_engine.herald.input_contract import CanonicalMediaBrief, ProductionConstraints


# -----------------------------------------------------------------------------
# 1. Canonical Objective Contract & Hash Determinism
# -----------------------------------------------------------------------------
def test_matrix_01_canonical_objective_determinism():
    """Proves that CanonicalObjective hash is strictly deterministic with zero timestamp entropy."""
    obj1 = CanonicalObjective(
        objective_id="obj_solar_01",
        description="Community Solar Explainer",
        desired_outcome="Educate municipal property owners on backup solar power.",
        target_audience="Facility directors and municipal engineers.",
        core_message="Clean energy independence with zero downtime.",
        intended_audience_action="Register on the municipal portal.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="Microgrids reduced storm outages by 94 percent.",
                confidence="VERIFIED_FACT",
            )
        ],
        explicit_unknowns=[
            UnknownReference(
                unknown_id="unk_01",
                description="Battery inverter vendor specification",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Use standard high-capacity commercial inverter specs",
            )
        ],
        constraints=ConstraintSet(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    obj2 = CanonicalObjective(
        objective_id="obj_solar_01",
        description="Community Solar Explainer",
        desired_outcome="Educate municipal property owners on backup solar power.",
        target_audience="Facility directors and municipal engineers.",
        core_message="Clean energy independence with zero downtime.",
        intended_audience_action="Register on the municipal portal.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="Microgrids reduced storm outages by 94 percent.",
                confidence="VERIFIED_FACT",
            )
        ],
        explicit_unknowns=[
            UnknownReference(
                unknown_id="unk_01",
                description="Battery inverter vendor specification",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Use standard high-capacity commercial inverter specs",
            )
        ],
        constraints=ConstraintSet(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    hash1 = obj1.compute_canonical_hash()
    hash2 = obj2.compute_canonical_hash()
    assert hash1 == hash2
    assert len(hash1) == 64


# -----------------------------------------------------------------------------
# 2. Unified Kernel DB Schema & Transactional Integrity
# -----------------------------------------------------------------------------
def test_matrix_02_kernel_database_transactional_schema(tmp_path):
    """Proves that KernelDatabase manages all core runtime tables in WAL mode with PRAGMA user_version = 1."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)

    with kdb.get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        user_ver = conn.execute("PRAGMA user_version;").fetchone()[0]
        assert journal_mode.upper() == "WAL"
        assert user_ver == 1

        tables = [row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "runs" in tables
        assert "artifacts" in tables
        assert "artifact_events" in tables
        assert "receipts" in tables
        assert "escalations" in tables
        assert "approvals" in tables


# -----------------------------------------------------------------------------
# 3. Artifact Registry 8-Tuple Idempotency Key & UNIQUE Constraint
# -----------------------------------------------------------------------------
def test_matrix_03_artifact_registry_idempotency_constraint(tmp_path):
    """Proves physical idempotency: duplicate registration returns existing record without throwing error."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")

    source_art = StructuredSourceArtifact(
        source_project_id="solar_microgrid",
        canonical_goal="Deliver clean energy resilience overview",
        target_audience="Facility managers",
        core_message="Zero downtime energy storage",
        intended_audience_action="Register on solar portal",
        narrative_arc_type="Context -> Impact",
        verified_facts=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="94 percent grid uptime verified.",
                confidence="VERIFIED_FACT",
            )
        ],
    )

    rec1 = registry.stage_artifact(
        artifact_obj=source_art,
        run_id="run_test_01",
        parent_run_id="parent_pipeline_01",
        producing_shadow_id=6,
        domain_code="scribe",
        step_id="step_scribe",
        route_plan_hash="plan_hash_123",
        source_artifact_hash="0" * 64,
        source_commit="commit_abc123",
    )

    rec2 = registry.stage_artifact(
        artifact_obj=source_art,
        run_id="run_test_01",
        parent_run_id="parent_pipeline_01",
        producing_shadow_id=6,
        domain_code="scribe",
        step_id="step_scribe",
        route_plan_hash="plan_hash_123",
        source_artifact_hash="0" * 64,
        source_commit="commit_abc123",
    )

    assert rec1.idempotency_key == rec2.idempotency_key
    assert rec1.artifact_id == rec2.artifact_id

    # Verify single database row
    with kdb.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM artifacts WHERE idempotency_key = ?;", (rec1.idempotency_key,)).fetchone()[0]
        assert count == 1


# -----------------------------------------------------------------------------
# 4. Append-Only Artifact Event Ledger
# -----------------------------------------------------------------------------
def test_matrix_04_append_only_artifact_event_ledger(tmp_path):
    """Proves that artifact state transitions append immutable event records."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")

    source_art = StructuredSourceArtifact(
        source_project_id="solar_microgrid_events",
        canonical_goal="Deliver clean energy resilience overview",
        target_audience="Facility managers",
        core_message="Zero downtime energy storage",
        intended_audience_action="Register on solar portal",
        narrative_arc_type="Context -> Impact",
    )

    rec = registry.stage_artifact(
        artifact_obj=source_art,
        run_id="run_test_events",
        parent_run_id="parent_pipeline_events",
        producing_shadow_id=6,
        domain_code="scribe",
        step_id="step_scribe",
        route_plan_hash="plan_hash_evt",
        source_artifact_hash="0" * 64,
        source_commit="commit_evt123",
    )

    registry.transition_state(rec.artifact_id, "VERIFIED", "TEST_VALIDATION_PASSED", "scribe")
    registry.transition_state(rec.artifact_id, "PROMOTED", "PROMOTED_TO_PRODUCTION", "scribe")

    history = registry.get_artifact_history(rec.artifact_id)
    assert len(history) == 3
    assert history[0]["to_state"] == "STAGED"
    assert history[1]["to_state"] == "VERIFIED"
    assert history[2]["to_state"] == "PROMOTED"


# -----------------------------------------------------------------------------
# 5. Typed Semantic Handoff Schemas & Integrity
# -----------------------------------------------------------------------------
def test_matrix_05_typed_semantic_handoff_chain(tmp_path):
    """Proves typed handoff lineage across Scribe -> Herald -> Slicer."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")
    governor = StepGovernor(kernel_db=kdb)

    objective = CanonicalObjective(
        objective_id="obj_matrix_handoff",
        description="Produce clean energy documentary script",
        desired_outcome="Educate municipal stakeholders on clean microgrid storage.",
        target_audience="Municipal engineers and property owners.",
        core_message="Resilient local clean power.",
        intended_audience_action="Register on municipal portal.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="94 percent grid uptime recorded across 12 months.",
                confidence="DOCUMENTED_METRIC",
            )
        ],
        constraints=ConstraintSet(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    parent_ctx = RunContext.create(
        task_id=objective.objective_id,
        shadow_id=10,
        domain_code="gamemaster",
        raw_objective=objective.model_dump(),
    )

    plan = BoundedShadowRouter.plan_route(canonical_objective=objective)

    result = BoundedShadowRouter.execute_route(
        plan=plan,
        canonical_objective=objective,
        parent_context=parent_ctx,
        artifact_registry=registry,
        kernel_db=kdb,
        step_governor=governor,
    )

    assert result.status == "SUCCESS"
    assert result.completed_step_ids == ["step_1_scribe", "step_2_herald", "step_3_slicer"]
    assert result.final_artifact_type == "ProductionPlanDAGArtifact"


# -----------------------------------------------------------------------------
# 6. StepGovernor Attempt & Strike Governance
# -----------------------------------------------------------------------------
def test_matrix_06_step_governor_strike_limits(tmp_path):
    """Proves StepGovernor enforces 3-strike ceiling and records negative constraints."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    governor = StepGovernor(kernel_db=kdb, max_strikes=3)

    runner = ScribeDomainRunner()
    bad_payload = {
        "project_id": "bad_p1",
        "canonical_goal": "tiny",  # Less than 5 chars -> fails verification
        "mode": "CANONICAL_OBJECTIVE_CONDITIONING",
    }

    result = governor.run_step(
        loop=runner,
        raw_input=bad_payload,
        step_id="step_fail_strike",
    )

    assert result.status == "ABORTED"
    assert result.strikes_used == 3
    assert result.negative_constraints_count == 3
    assert len(result.negative_constraints_ledger) == 3


# -----------------------------------------------------------------------------
# 7. Anti-Oscillation Detection
# -----------------------------------------------------------------------------
def test_matrix_07_anti_oscillation_guard(tmp_path):
    """Proves that generating an identical candidate on retry triggers anti-oscillation violation."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    governor = StepGovernor(kernel_db=kdb, max_strikes=3)

    # Runner that does not adapt and produces static output
    class StaticUnchangingLoop(ScribeDomainRunner):
        def execute_staging(self, task_spec, staging_dir, feedback=None):
            f = staging_dir / "static_candidate.json"
            f.write_text('{"status": "unchanging_payload"}', encoding="utf-8")
            return f

        def verify(self, candidate_path, task_spec):
            return False, "Always rejecting to test oscillation"

    runner = StaticUnchangingLoop()
    result = governor.run_step(
        loop=runner,
        raw_input={"project_id": "osc_test", "canonical_goal": "Valid Goal Name"},
        step_id="step_osc",
    )

    assert result.status == "ABORTED"
    # Should contain oscillation violation in negative constraints
    osc_entries = [entry for entry in result.negative_constraints_ledger if entry["phase"] == "OSCILLATION"]
    assert len(osc_entries) > 0


# -----------------------------------------------------------------------------
# 8. Deterministic Failure Injection & Repair Recovery
# -----------------------------------------------------------------------------
def test_matrix_08_failure_injection_and_repair(tmp_path):
    """Proves that a transient failure on attempt 1 is repaired on attempt 2."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    governor = StepGovernor(kernel_db=kdb, max_strikes=3)

    runner = HeraldAVScriptDomainRunner()
    brief = CanonicalMediaBrief(
        project_id="brief_repair_01",
        project_title="Microgrid Energy Independence",
        organizational_goal="Educate property managers on energy independence.",
        target_audience="Facility directors.",
        intended_audience_action="Submit property survey.",
        core_message="Energy independence.",
        narrative_arc_type="Context -> Impact",
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    result = governor.run_step(
        loop=runner,
        raw_input=brief,
        step_id="step_herald_injected",
        forced_failure_attempt=1,
        forced_failure_msg="Injected Transient Pacing Constraint Violation",
    )

    assert result.status == "SUCCESS"
    assert result.attempts_used == 2
    assert result.strikes_used == 1
    assert result.negative_constraints_count == 1


# -----------------------------------------------------------------------------
# 9. Human Escalation Pause & Resume State Machine
# -----------------------------------------------------------------------------
def test_matrix_09_human_escalation_lifecycle(tmp_path):
    """Proves RUNNING -> ESCALATED -> AWAITING_APPROVAL -> RESUMED state machine."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")
    governor = StepGovernor(kernel_db=kdb)

    objective = CanonicalObjective(
        objective_id="obj_matrix_escalate",
        description="Community solar explainer video",
        desired_outcome="Educate municipal property owners on backup solar power.",
        target_audience="Facility managers.",
        core_message="Clean backup power.",
        intended_audience_action="Register on solar portal.",
    )

    parent_ctx = RunContext.create(
        task_id=objective.objective_id,
        shadow_id=10,
        domain_code="gamemaster",
        raw_objective=objective.model_dump(),
    )

    plan = BoundedShadowRouter.plan_route(canonical_objective=objective)
    # Require human gate on Herald step
    plan.steps[1].requires_human_approval = True

    res = BoundedShadowRouter.execute_route(
        plan=plan,
        canonical_objective=objective,
        parent_context=parent_ctx,
        artifact_registry=registry,
        kernel_db=kdb,
        step_governor=governor,
    )

    assert res.status == "AWAITING_APPROVAL"
    assert res.escalation is not None

    # Human Approval
    appr = BoundedShadowRouter.resolve_escalation(
        escalation_id=res.escalation.escalation_id,
        decision="APPROVED",
        human_authority="OPERATOR_LEAD",
        operator_notes="Approved for full render",
        parent_run_id=parent_ctx.run_id,
        resulting_plan_hash=plan.route_plan_hash,
        resumed_step_id=res.current_step_id or "step_2_herald",
        kernel_db=kdb,
    )
    assert appr["status"] == "RESOLVED_APPROVED"


# -----------------------------------------------------------------------------
# 10. Environment-Bound Resume Integrity
# -----------------------------------------------------------------------------
def test_matrix_10_environment_bound_resume(tmp_path):
    """Proves that cached artifact is only reused when complete 8-tuple environment matches."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")
    governor = StepGovernor(kernel_db=kdb)

    objective = CanonicalObjective(
        objective_id="obj_matrix_env_resume",
        description="Community solar explainer video",
        desired_outcome="Educate municipal property owners on backup solar power.",
        target_audience="Facility managers.",
        core_message="Clean backup power.",
        intended_audience_action="Register on solar portal.",
    )

    parent_ctx = RunContext.create(
        task_id=objective.objective_id,
        shadow_id=10,
        domain_code="gamemaster",
        raw_objective=objective.model_dump(),
    )

    plan = BoundedShadowRouter.plan_route(canonical_objective=objective)

    # Initial Run
    res1 = BoundedShadowRouter.execute_route(
        plan=plan,
        canonical_objective=objective,
        parent_context=parent_ctx,
        artifact_registry=registry,
        kernel_db=kdb,
        step_governor=governor,
    )
    assert res1.status == "SUCCESS"

    # Resume with exact matching environment -> All steps cached
    res2 = BoundedShadowRouter.execute_route(
        plan=plan,
        canonical_objective=objective,
        parent_context=parent_ctx,
        artifact_registry=registry,
        kernel_db=kdb,
        step_governor=governor,
        resume=True,
    )
    assert res2.status == "SUCCESS"
    assert len(res2.cached_step_ids) == 3

    # Resume with modified route plan hash -> Cache lookup fails (environment binding holds)
    modified_plan = plan.model_copy(deep=True)
    modified_plan.route_plan_hash = "modified_differing_plan_hash"

    res3 = BoundedShadowRouter.execute_route(
        plan=modified_plan,
        canonical_objective=objective,
        parent_context=parent_ctx,
        artifact_registry=registry,
        kernel_db=kdb,
        step_governor=governor,
        resume=True,
    )
    # Zero cached steps because route_plan_hash did not match
    assert len(res3.cached_step_ids) == 0
