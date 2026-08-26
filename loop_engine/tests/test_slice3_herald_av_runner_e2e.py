import pytest
from pathlib import Path
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_herald_av_script_domain_runner_e2e(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldAVScriptDomainRunner(receipt_store=store)

    brief = {
        "project_title": "City Solar Microgrid Initiative",
        "organizational_goal": "Educate municipal residents on distributed solar storage benefits.",
        "target_audience_persona": "Homeowners and local community council representatives.",
        "core_brand_alignment": "Clean energy independence and transparent public infrastructure.",
        "narrative_arc_type": "Grid Vulnerability -> Distributed Storage -> Long-term Savings",
        "scenes": [
            {
                "name": "Scene 1: Summer Blackouts",
                "start": 0.0,
                "end": 15.0,
                "audio": "When summer heatwaves push the regional power grid to its limits, neighborhood blackouts disrupt thousands of homes.",
                "video": "Wide Shot (24mm, f/4) of residential neighborhood during sunset. Handheld documentary sway.",
            },
            {
                "name": "Scene 2: Local Resilience",
                "start": 15.0,
                "end": 45.0,
                "audio": "Our municipal solar microgrid stores clean power during peak daylight hours, keeping essential community facilities online without interruption.",
                "video": "Cut to MCU (85mm, f/2.0) on energy technician monitoring battery status inverter. Clean 2:1 lighting ratio.",
            }
        ]
    }

    gov = Governor(max_strikes=3)
    result = gov.run_loop(runner, brief)

    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination_markdown"]).exists()
    assert Path(result["receipt"]["destination_json"]).exists()
