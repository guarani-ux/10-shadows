import pytest
from pathlib import Path
from loop_engine.router import BoundedShadowRouter, HumanEscalationRecord
from loop_engine.herald.input_contract import CanonicalMediaBrief, EvidenceItem, ProductionConstraints
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.runners.slicer_runner import SlicerDomainRunner
from loop_engine.gamemaster.state_projector import SovereignStateProjector
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_bounded_shadow_router_explicit_decisions():
    """Proves that BoundedShadowRouter outputs explicit inclusion, exclusion, and verification gates."""
    obj = {
        "type": "av_production",
        "description": "Produce 60s Municipal Solar Explainer",
        "task_id": "solar_01",
    }
    decision = BoundedShadowRouter.route_objective(obj)

    assert decision.selected_shadow_ids == [6, 3, 7, 8, 10]
    assert 1 in decision.excluded_shadow_ids
    assert "Shadow 1 not required" in decision.exclusion_reasons[1]
    assert "DeterministicScriptValidator" in decision.verification_gates


def test_routed_multi_shadow_pipeline_execution(tmp_path):
    """
    Executes a routed pipeline across:
    Brief -> Herald AV Generation -> Slicer Task Decomposition -> SQLite WAL Receipt -> Game Master Projection
    """
    db_file = tmp_path / "scratch" / "receipts.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    store = ReceiptStore(db_path=db_file)

    # 1. Step 1: Herald Execution
    herald_runner = HeraldAVScriptDomainRunner(receipt_store=store)
    brief = CanonicalMediaBrief(
        project_id="routed_solar_01",
        project_title="Municipal Solar Microgrid",
        organizational_goal="Educate city residents on local microgrid resilience.",
        target_audience="City residents.",
        intended_audience_action="Visit our city portal to register.",
        core_message="Clean sovereign energy storage.",
        narrative_arc_type="Context -> Solution -> CTA",
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
        ),
    )

    gov = Governor(max_strikes=3)
    herald_res = gov.run_loop(herald_runner, brief)
    assert herald_res["status"] == "SUCCESS"
    assert herald_res["receipt"]["status"] == "COMMITTED"

    # 2. Step 2: Slicer Execution on the Herald output
    slicer_runner = SlicerDomainRunner(receipt_store=store)
    slicer_input = {
        "task_id": "slice_solar_01",
        "goal": "Execute production shoot for Municipal Solar Microgrid",
        "raw_tasks": [
            {"slice_id": "s1", "name": "Film Wide Aisle Shot", "assigned_shadow": "media", "dependencies": []},
            {"slice_id": "s2", "name": "Film Technician MCU", "assigned_shadow": "media", "dependencies": ["s1"]},
            {"slice_id": "s3", "name": "Render Vertical Shorts", "assigned_shadow": "herald", "dependencies": ["s2"]},
        ]
    }
    slicer_res = gov.run_loop(slicer_runner, slicer_input)
    assert slicer_res["status"] == "SUCCESS"

    # 3. Step 3: Game Master Live Projection
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud = projector.project_hud()

    # Must find at least 2 receipts recorded
    assert hud.total_wal_receipts == 2
    herald_domain = next(d for d in hud.domains if d.shadow_id == 3)
    assert herald_domain.receipts_count >= 1
