from pathlib import Path

import pytest

from loop_engine.gamemaster.state_projector import SovereignStateProjector
from loop_engine.governor import Governor
from loop_engine.herald.input_contract import CanonicalMediaBrief, EvidenceItem, ProductionConstraints, UnknownItem
from loop_engine.receipts import ReceiptStore
from loop_engine.runners.alchemist_runner import RealAlchemistSelfHealingEngine
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner


def test_cross_shadow_closed_loop_vertical_slice(tmp_path):
    """
    Executes and proves the complete integrated multi-Shadow vertical slice:

    1. Shadow 3 (The Herald) synthesizes a multi-constraint AV script from a CanonicalMediaBrief.
    2. Verification Gate validates WPM, anti-AI linguistics, cinematography, and 9:16 vertical cutdowns.
    3. Shadow 2 (svris) & SQLite WAL records structured receipt.
    4. Shadow 9 (The Alchemist) ingests a live crash traceback, repairs syntax, runs isolated pytest, and verifies fix.
    5. Shadow 10 (The Game Master) dynamically projects state directly from physical disk, Git, test files, and receipts.
    """
    db_file = tmp_path / "scratch" / "receipts.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    store = ReceiptStore(db_path=db_file)

    # ----------------------------------------------------
    # STEP 1: Execute Herald AV Script Synthesis Loop
    # ----------------------------------------------------
    herald_runner = HeraldAVScriptDomainRunner(receipt_store=store)
    brief = CanonicalMediaBrief(
        project_id="vertical_slice_energy_01",
        project_title="Community Grid Resilience",
        organizational_goal="Educate commercial property owners on clean microgrid storage.",
        target_audience="Facility Managers and Sustainability Directors.",
        intended_audience_action="Visit our microgrid evaluation portal and submit your facility survey.",
        core_message="Clean energy independence with sovereign battery storage.",
        narrative_arc_type="Vulnerability -> Grid Modernization -> Measurable Savings",
        verified_evidence=[
            EvidenceItem(
                evidence_id="ev_outage_savings",
                source_description="Pilot microgrids reduced peak downtime by 94% over 18 months.",
                confidence="DOCUMENTED_METRIC",
            )
        ],
        explicit_unknowns=[
            UnknownItem(
                unknown_id="unk_substation_b_roll",
                description="Pending utility clearance for high voltage substation B-roll.",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Capture exterior perimeter shots with 85mm lens.",
            )
        ],
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=145.0,
            camera_package=["Sony FX3 (24mm f/4)", "Sony A7IV (85mm f/1.8)"],
            lighting_style="High-contrast 4:1 corporate industrial lighting",
        ),
    )

    gov = Governor()

    herald_res = gov.run_loop(herald_runner, brief)

    assert herald_res["status"] == "SUCCESS"
    assert herald_res["strikes_used"] == 1
    assert herald_res["receipt"]["status"] == "COMMITTED"
    assert Path(herald_res["receipt"]["destination_markdown"]).exists()

    # ----------------------------------------------------
    # STEP 2: Execute Alchemist Active Self-Healing Repair
    # ----------------------------------------------------
    alchemist_runner = RealAlchemistSelfHealingEngine(receipt_store=store)

    broken_file = tmp_path / "energy_calc.py"
    broken_file.write_text(
        "def compute_efficiency(kwh, loss):\n    return (kwh - loss) / kwh\n",
        encoding="utf-8",
    )

    test_file = tmp_path / "test_energy.py"
    test_file.write_text(
        f"import sys\n"
        f"sys.path.insert(0, r'{tmp_path}')\n"
        f"from energy_calc import compute_efficiency\n\n"
        f"def test_efficiency_safe():\n"
        f"    assert compute_efficiency(0, 0) == 0.0\n",
        encoding="utf-8",
    )

    crash_trace = (
        f"Traceback (most recent call last):\n"
        f'  File "{broken_file}", line 2, in compute_efficiency\n'
        f"    return (kwh - loss) / kwh\n"
        f"ZeroDivisionError: division by zero\n"
    )

    alchemist_payload = {
        "task_id": "heal_energy_calc_01",
        "raw_trace": crash_trace,
        "source_file": str(broken_file.as_posix()),
        "target_test_file": str(test_file.as_posix()),
    }

    alchemist_res = gov.run_loop(alchemist_runner, alchemist_payload)
    assert alchemist_res["status"] == "SUCCESS"
    assert alchemist_res["receipt"]["status"] == "COMMITTED"
    assert "return (kwh - loss) / kwh if kwh != 0 else 0.0" in broken_file.read_text(encoding="utf-8")

    # ----------------------------------------------------
    # STEP 3: Verify Game Master Live Telemetry Projection
    # ----------------------------------------------------
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud = projector.project_hud()

    # Telemetry must show exactly 2 WAL receipts dynamically
    assert hud.total_wal_receipts == 2
    assert hud.receipts_by_status.get("COMMITTED") == 2
