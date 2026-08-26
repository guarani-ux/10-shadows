import pytest
from pathlib import Path
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.herald.input_contract import CanonicalMediaBrief, ProductionConstraints
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_herald_av_script_domain_runner_e2e(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldAVScriptDomainRunner(receipt_store=store)

    brief = CanonicalMediaBrief(
        project_id="solar_microgrid_01",
        project_title="City Solar Microgrid Initiative",
        organizational_goal="Educate municipal residents on distributed solar storage benefits.",
        target_audience="Homeowners and local community council representatives.",
        intended_audience_action="Visit our city solar rebate portal and register your household online.",
        core_message="Clean energy independence and transparent public infrastructure.",
        narrative_arc_type="Grid Vulnerability -> Distributed Storage -> Long-term Savings",
        production_constraints=ProductionConstraints(
            target_duration_seconds=75,
            target_pacing_wpm=145.0,
            camera_package=["Sony FX3 (24mm f/4)", "Sony A7IV (85mm f/1.8)"],
        ),
    )

    gov = Governor(max_strikes=3)
    result = gov.run_loop(runner, brief)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination_markdown"]).exists()
    assert Path(result["receipt"]["destination_json"]).exists()
