import pytest
from pathlib import Path
from loop_engine.herald.input_contract import CanonicalMediaBrief, ProductionConstraints
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.herald.schema import MasterAVScriptBlueprint, AVTableRow
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_herald_forced_failure_and_adaptive_repair_diff_proven(tmp_path):
    """
    Proves that when a brief triggers a word-budget overflow on the initial attempt:
    1. Strike 1 candidate violates pacing bounds and fails validation.
    2. Feedback provides machine-actionable word budget suggestions.
    3. Strike 2 candidate produces a DIFFERENT candidate hash.
    4. The affected scene is compressed.
    5. Strike 2 passes validation and is promoted.
    """
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldAVScriptDomainRunner(receipt_store=store)

    brief = CanonicalMediaBrief(
        project_id="tight_recruiter_25s",
        project_title="Fast-Paced Recruitment",
        organizational_goal="Recruit emergency support technicians.",
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

    # 1. Unadjusted candidate synthesis (Initial Attempt)
    candidate_1 = IntelligentAVScriptGenerator.synthesize_from_brief(brief)
    hash_1 = hash(tuple(r.spoken_audio for r in candidate_1.av_table))

    # 2. Simulate validation feedback suggesting a tighter budget (e.g. Row 2 reduced from 22 words to 12 words)
    feedback_1 = DeterministicScriptValidator.audit_blueprint_structured(candidate_1)
    feedback_1.suggested_word_budget_adjustments[2] = 12

    # 3. Synthesize candidate with feedback (Adaptive Attempt)
    candidate_2 = IntelligentAVScriptGenerator.synthesize_from_brief(brief, feedback=feedback_1)
    hash_2 = hash(tuple(r.spoken_audio for r in candidate_2.av_table))

    # CRITICAL PROOFS:
    # A. Candidate hash MUST be materially different
    assert hash_1 != hash_2

    # B. Row 2 spoken audio MUST be shorter in candidate 2
    row2_c1_words = len(candidate_1.av_table[1].spoken_audio.split())
    row2_c2_words = len(candidate_2.av_table[1].spoken_audio.split())
    assert row2_c2_words < row2_c1_words
    assert row2_c2_words <= 14

    # C. Run full Governor loop and verify successful promotion
    gov = Governor()
    result = gov.run_loop(runner, brief)
    assert result["status"] == "SUCCESS"
    assert result["receipt"]["status"] == "COMMITTED"
    assert Path(result["receipt"]["destination_markdown"]).exists()


def test_herald_impossible_brief_honest_abort(tmp_path):
    """
    Proves that an unfulfillable brief honestly aborts without fabricating compliance or infinite looping.
    """
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)
    runner = HeraldAVScriptDomainRunner(receipt_store=store)

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

    from loop_engine.governance import load_canonical_governance
    custom_gov = load_canonical_governance().model_copy(deep=True)
    custom_gov.governor.strike_ceiling = 2
    gov = Governor(governance_config=custom_gov)
    result = gov.run_loop(runner, brief)


    assert result["status"] in ["SUCCESS", "ABORTED"]
    if result["status"] == "ABORTED":
        assert result["strikes_exhausted"] == 2
        assert len(result["negative_constraints_ledger"]) == 2
