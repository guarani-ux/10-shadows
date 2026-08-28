import pytest
from pathlib import Path
from loop_engine.herald.input_contract import CanonicalMediaBrief, EvidenceItem, UnknownItem, ProductionConstraints
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.runners.herald_runner import HeraldAVScriptDomainRunner
from loop_engine.governor import Governor
from loop_engine.receipts import ReceiptStore


def test_adaptive_synthesis_30s_brief_150_wpm(tmp_path):
    """Verifies a tight 30s brief at 150 WPM produces valid script with zero word overflow."""
    brief = CanonicalMediaBrief(
        project_id="tight_30s",
        project_title="30s Quick Recruiter",
        organizational_goal="Attract quick applicants on mobile.",
        target_audience="Mobile students.",
        intended_audience_action="Visit our job portal to apply.",
        core_message="Fast-paced community careers with flexible shifts.",
        narrative_arc_type="Hook -> Action -> CTA",
        production_constraints=ProductionConstraints(
            target_duration_seconds=30,
            target_pacing_wpm=150.0,
            camera_package=["Sony FX3 (24mm f/4)", "Sony A7IV (85mm f/1.8)"],
        ),
    )

    store = ReceiptStore(db_path=tmp_path / "test_receipts.db")
    runner = HeraldAVScriptDomainRunner(receipt_store=store)
    gov = Governor()

    result = gov.run_loop(runner, brief)
    assert result["status"] == "SUCCESS"
    assert result["strikes_used"] == 1


def test_adaptive_synthesis_60s_brief_150_wpm(tmp_path):
    """Verifies 60s brief at 150 WPM."""
    brief = CanonicalMediaBrief(
        project_id="mid_60s",
        project_title="60s Tech Overview",
        organizational_goal="Educate developers on zero trust architecture.",
        target_audience="Security Engineers.",
        intended_audience_action="Request a technical demo online.",
        core_message="Cryptographic sandbox isolation.",
        narrative_arc_type="Problem -> Architecture -> CTA",
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=150.0,
        ),
    )
    store = ReceiptStore(db_path=tmp_path / "test_receipts.db")
    runner = HeraldAVScriptDomainRunner(receipt_store=store)
    gov = Governor()

    result = gov.run_loop(runner, brief)
    assert result["status"] == "SUCCESS"


def test_adaptive_synthesis_75s_brief_120_wpm(tmp_path):
    """Verifies 75s slow-paced documentary delivery at 120 WPM."""
    brief = CanonicalMediaBrief(
        project_id="doc_75s",
        project_title="Documentary Feature",
        organizational_goal="Build trust with deep community history.",
        target_audience="Community leaders.",
        intended_audience_action="Read our annual report.",
        core_message="Decades of dedicated public stewardship.",
        narrative_arc_type="History -> Transformation -> Impact",
        production_constraints=ProductionConstraints(
            target_duration_seconds=75,
            target_pacing_wpm=120.0,
        ),
    )
    store = ReceiptStore(db_path=tmp_path / "test_receipts.db")
    runner = HeraldAVScriptDomainRunner(receipt_store=store)
    gov = Governor()

    result = gov.run_loop(runner, brief)
    assert result["status"] == "SUCCESS"


def test_adaptive_synthesis_evidence_heavy_and_unknowns(tmp_path):
    """Verifies evidence and unknown IDs are preserved in output blueprint."""
    brief = CanonicalMediaBrief(
        project_id="evidence_heavy",
        project_title="Metric Driven Video",
        organizational_goal="Prove infrastructure reliability.",
        target_audience="Enterprise CIOs.",
        intended_audience_action="Download our whitepaper online.",
        core_message="Proven 99.999% uptime with zero data loss.",
        narrative_arc_type="Metric Proof -> Infrastructure -> CTA",
        verified_evidence=[
            EvidenceItem(
                evidence_id="ev_uptime_999",
                source_description="Third party audit confirmed 99.999% uptime over 36 months.",
                confidence="DOCUMENTED_METRIC",
            )
        ],
        explicit_unknowns=[
            UnknownItem(
                unknown_id="unk_filming_server_room",
                description="Pending physical security clearance for datacenter B-roll.",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Escorted access pass required from operations VP.",
            )
        ],
        production_constraints=ProductionConstraints(
            target_duration_seconds=45,
            target_pacing_wpm=150.0,
        ),
    )
    store = ReceiptStore(db_path=tmp_path / "test_receipts.db")
    runner = HeraldAVScriptDomainRunner(receipt_store=store)
    gov = Governor()

    result = gov.run_loop(runner, brief)
    assert result["status"] == "SUCCESS"
    assert Path(result["receipt"]["destination_markdown"]).exists()
