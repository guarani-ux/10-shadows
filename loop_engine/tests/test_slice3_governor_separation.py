import pytest
from pathlib import Path
from loop_engine.governor import StepGovernor, StepExecutionResult
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.runners.scribe_runner import ScribeDomainRunner
from loop_engine.runners.slicer_runner import SlicerDomainRunner
from loop_engine.herald.input_contract import CanonicalMediaBrief, ProductionConstraints
from loop_engine.canonical_objective import CanonicalObjective
from loop_engine.context import RunContext
from loop_engine.receipts import ReceiptStore


def test_step_governor_execution_and_metrics_injection(tmp_path):
    """Proves StepGovernor executes runner, measures strikes, and injects parent context."""
    db_file = tmp_path / "scratch" / "receipts.db"
    store = ReceiptStore(db_path=db_file)
    governor = StepGovernor(max_strikes=3)

    parent_ctx = RunContext.create(
        task_id="parent_pipeline_01",
        shadow_id=10,
        domain_code="gamemaster",
        raw_objective={"goal": "Execute Media Production Pipeline"},
    )

    runner = HeraldAVScriptDomainRunner(receipt_store=store)
    brief = CanonicalMediaBrief(
        project_id="solar_explainer_01",
        project_title="Community Solar Microgrid",
        organizational_goal="Educate residents on solar microgrids and resilience.",
        target_audience="Homeowners and facility managers.",
        intended_audience_action="Register on municipal portal.",
        core_message="Clean sovereign energy storage.",
        narrative_arc_type="Context -> Solution -> CTA",
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    result = governor.run_step(
        loop=runner,
        raw_input=brief,
        parent_context=parent_ctx,
        step_id="step_herald",
    )

    assert result.status == "SUCCESS"
    assert result.attempts_used == 1
    assert result.strikes_used == 0
    assert result.parent_run_id == parent_ctx.run_id
    assert result.shadow_id == 3
    assert result.domain_code == "herald"
    assert result.receipt is not None
    assert result.receipt["attempts_used"] == 1
    assert result.receipt["strikes_used"] == 0
    assert result.receipt["parent_run_id"] == parent_ctx.run_id


def test_step_governor_forced_failure_and_retry_recovery(tmp_path):
    """Proves StepGovernor handles forced failure on attempt 1 and recovers on attempt 2."""
    db_file = tmp_path / "scratch" / "receipts.db"
    store = ReceiptStore(db_path=db_file)
    governor = StepGovernor(max_strikes=3)

    parent_ctx = RunContext.create(
        task_id="parent_pipeline_retry",
        shadow_id=10,
        domain_code="gamemaster",
        raw_objective={"goal": "Test Retry Flow"},
    )

    runner = HeraldAVScriptDomainRunner(receipt_store=store)
    brief = CanonicalMediaBrief(
        project_id="retry_brief_01",
        project_title="Microgrid Energy Storage",
        organizational_goal="Educate commercial property owners.",
        target_audience="Facility directors.",
        intended_audience_action="Submit facility survey.",
        core_message="Energy independence.",
        narrative_arc_type="Context -> Impact",
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    # Invalidate attempt 1 via forced failure seam
    result = governor.run_step(
        loop=runner,
        raw_input=brief,
        parent_context=parent_ctx,
        step_id="step_herald_retry",
        forced_failure_attempt=1,
        forced_failure_msg="Injected Transient Pacing Constraint Violation",
    )

    if result.status != "SUCCESS":
        print("DEBUG RESULT:", result.model_dump_json(indent=2))

    assert result.status == "SUCCESS"
    assert result.attempts_used == 2
    assert result.strikes_used == 1
    assert result.negative_constraints_count == 1
    assert "Injected Transient Pacing Constraint Violation" in result.negative_constraints_ledger[0]["error"]
    assert result.receipt["attempts_used"] == 2
    assert result.receipt["strikes_used"] == 1


def test_step_governor_three_strikes_hard_abort(tmp_path):
    """Proves StepGovernor exhausts 3 strikes and aborts cleanly."""
    db_file = tmp_path / "scratch" / "receipts.db"
    store = ReceiptStore(db_path=db_file)
    governor = StepGovernor(max_strikes=3)

    runner = ScribeDomainRunner(receipt_store=store)
    # Malformed payload that fails verification
    bad_payload = {
        "project_id": "proj_p1",
        "canonical_goal": "tiny",  # Less than 5 characters -> verification fails
        "mode": "CANONICAL_OBJECTIVE_CONDITIONING",
    }

    result = governor.run_step(
        loop=runner,
        raw_input=bad_payload,
        step_id="step_scribe_fail",
    )

    assert result.status == "ABORTED"
    assert result.strikes_used == 3
    assert result.negative_constraints_count == 3
    assert result.receipt is None
    assert "Strike 3" in (result.last_error or "")
