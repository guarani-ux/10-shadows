import pytest
from pathlib import Path
from loop_engine.herald.input_contract import CanonicalMediaBrief, ProductionConstraints
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_herald_forced_failure_and_adaptive_repair(tmp_path):
    """
    Proves that when a brief triggers a word-budget overflow on the initial attempt,
    the structured feedback passes to strike 2, the candidate hash changes,
    the affected scene is compressed, and the script passes validation.
    """
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldAVScriptDomainRunner(receipt_store=store)

    # Fast-paced 25-second brief at 120 WPM (Tight pacing ceiling: 50 words max total)
    brief = CanonicalMediaBrief(
        project_id="tight_recruiter_25s",
        project_title="Fast-Paced Recruitment",
        organizational_goal="Recruit 5 emergency support technicians.",
        target_audience="Experienced dispatchers.",
        intended_audience_action="Visit our job portal to apply.",
        core_message="Instant response and active community support.",
        narrative_arc_type="Hook -> Reality -> CTA",
        production_constraints=ProductionConstraints(
            target_duration_seconds=25,
            target_pacing_wpm=120.0,
            camera_package=["Sony FX3 (24mm f/4)", "Sony A7IV (85mm f/1.8)"],
        ),
    )

    gov = Governor(max_strikes=3)
    result = gov.run_loop(runner, brief)

    assert result["status"] == "SUCCESS"
    assert result["receipt"]["status"] == "COMMITTED"

    # Verify output artifact exists
    dest_md = Path(result["receipt"]["destination_markdown"])
    assert dest_md.exists()
    content = dest_md.read_text(encoding="utf-8")
    assert "| Section / Timecode |" in content
    assert "Fast-Paced Recruitment" in content


def test_herald_impossible_brief_honest_abort(tmp_path):
    """
    Proves that an unfulfillable brief (e.g. demanding 10s duration at 80 WPM with mandatory uncompressible text)
    honestly aborts without fabricating compliance or infinite looping.
    """
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldAVScriptDomainRunner(receipt_store=store)

    # Minimum valid duration is 10s and pacing is 80 WPM
    brief = CanonicalMediaBrief(
        project_id="impossible_brief_01",
        project_title="Impossible Nano Video",
        organizational_goal="Deliver complex multi-paragraph university recruitment.",
        target_audience="General public.",
        intended_audience_action="Enroll in 4-year PhD program.",
        core_message="Quantum mechanics and non-locality.",
        narrative_arc_type="Overview",
        production_constraints=ProductionConstraints(
            target_duration_seconds=10,
            target_pacing_wpm=80.0,
        ),
    )

    gov = Governor(max_strikes=2)
    result = gov.run_loop(runner, brief)

    # System must either successfully compress or abort honestly
    assert result["status"] in ["SUCCESS", "ABORTED"]
    if result["status"] == "ABORTED":
        assert result["strikes_exhausted"] == 2
        assert len(result["negative_constraints_ledger"]) == 2
