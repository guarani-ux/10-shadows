from pathlib import Path

import pytest

from loop_engine.artifacts import (
    ArtifactRegistry,
    MasterAVScriptArtifact,
    ProductionPlanDAGArtifact,
    StructuredSourceArtifact,
)
from loop_engine.canonical_objective import CanonicalObjective, ConstraintSet, EvidenceReference, UnknownReference
from loop_engine.context import RunContext
from loop_engine.governor import StepGovernor
from loop_engine.kernel_db import KernelDatabase
from loop_engine.receipts import ReceiptStore
from loop_engine.router import BoundedShadowRouter, HumanEscalationRecord, RoutePlan, RouteStep


def test_plan_route_minimal_shadow_selection_and_deterministic_hash():
    """Proves BoundedShadowRouter plans minimal required Shadows and logs explicit exclusions."""
    objective = CanonicalObjective(
        objective_id="obj_solar_media_01",
        description="Produce an institutional overview of community solar microgrids",
        desired_outcome="Educate commercial building owners on backup solar power.",
        target_audience="Facility directors and municipal engineers.",
        core_message="Clean energy independence with zero downtime.",
        intended_audience_action="Register for the municipal solar audit.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="Facility microgrids reduced storm outages by 94 percent.",
                confidence="VERIFIED_FACT",
            )
        ],
        explicit_unknowns=[
            UnknownReference(
                unknown_id="unk_01",
                description="Exact inverter battery vendor choice",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Use generic high-capacity commercial inverter specs",
            )
        ],
        constraints=ConstraintSet(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    plan = BoundedShadowRouter.plan_route(canonical_objective=objective, requested_pipeline_type="media_production")

    assert plan.selected_shadow_ids == [6, 3, 7]
    assert plan.selected_domain_codes == ["scribe", "herald", "slicer"]
    assert 1 in plan.excluded_shadow_ids
    assert 9 in plan.excluded_shadow_ids
    assert "Shadow 1 not required" in plan.exclusion_reasons[1]
    assert len(plan.steps) == 3
    assert plan.route_plan_hash != ""

    # Hash determinism
    plan2 = BoundedShadowRouter.plan_route(canonical_objective=objective, requested_pipeline_type="media_production")
    assert plan.route_plan_hash == plan2.route_plan_hash


def test_execute_route_end_to_end_success(tmp_path):
    """Proves execute_route runs Scribe -> Herald -> Slicer end-to-end and promotes artifacts."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")
    governor = StepGovernor(kernel_db=kdb)

    objective = CanonicalObjective(
        objective_id="obj_e2e_solar_01",
        description="Explain community solar microgrid benefits",
        desired_outcome="Educate property owners on solar microgrid benefits.",
        target_audience="Property owners and facility managers.",
        core_message="Resilient clean backup power.",
        intended_audience_action="Submit property survey.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="94 percent grid uptime verified during storm tests.",
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
    assert len(result.completed_step_ids) == 3
    assert result.final_artifact_type == "ProductionPlanDAGArtifact"
    assert result.final_artifact_id is not None

    # Verify run state in database
    run_record = kdb.get_run(parent_ctx.run_id)
    assert run_record is not None
    assert run_record["status"] == "COMPLETED"


def test_verification_bound_resume_and_caching(tmp_path):
    """Proves execute_route(resume=True) skips already verified steps."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")
    governor = StepGovernor(kernel_db=kdb)

    objective = CanonicalObjective(
        objective_id="obj_resume_solar_01",
        description="Explain community solar microgrid benefits",
        desired_outcome="Educate property owners on solar microgrid benefits.",
        target_audience="Property owners and facility managers.",
        core_message="Resilient clean backup power.",
        intended_audience_action="Submit property survey.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="94 percent grid uptime verified.",
                confidence="VERIFIED_FACT",
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

    # Resume Run
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


def test_human_escalation_pause_and_approval_resolution(tmp_path):
    """Proves execution pauses on failure, logs escalation, and resolves upon human approval."""
    db_file = tmp_path / "kernel.db"
    kdb = KernelDatabase(db_path=db_file)
    registry = ArtifactRegistry(kernel_db=kdb, storage_dir=tmp_path / "artifacts")
    governor = StepGovernor(kernel_db=kdb)

    objective = CanonicalObjective(
        objective_id="obj_escalate_01",
        description="Explain community solar microgrid benefits",
        desired_outcome="Educate property owners on solar microgrid benefits.",
        target_audience="Property owners and facility managers.",
        core_message="Resilient clean backup power.",
        intended_audience_action="Submit property survey.",
        verified_evidence=[
            EvidenceReference(
                evidence_id="ev_01",
                source_description="94 percent grid uptime verified.",
                confidence="VERIFIED_FACT",
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

    # Force step 2 herald to require approval
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
    assert res.escalation.category == "HUMAN_APPROVAL_REQUIRED"
    assert any(entry["status"] == "AWAITING_APPROVAL" for entry in parent_ctx.status_history)

    # Operator resolves escalation
    approval_res = BoundedShadowRouter.resolve_escalation(
        escalation_id=res.escalation.escalation_id,
        decision="APPROVED",
        human_authority="OPERATOR_LEAD",
        operator_notes="Approved for full media production",
        parent_run_id=parent_ctx.run_id,
        resulting_plan_hash=plan.route_plan_hash,
        resumed_step_id=res.current_step_id or "step_2_herald",
        kernel_db=kdb,
    )
    assert approval_res["status"] == "RESOLVED_APPROVED"
