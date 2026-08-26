import pytest
from loop_engine.herald.input_contract import (
    CanonicalMediaBrief,
    EvidenceItem,
    UnknownItem,
    ProductionConstraints,
)
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.validators import DeterministicScriptValidator
from loop_engine.herald.renderer import MasterAVMarkdownRenderer


def test_calgary_public_library_fixture():
    """Real Calgary Public Library style production brief."""
    brief = CanonicalMediaBrief(
        project_id="cpl_recruiting_2026",
        project_title="Day in the Life of a Library Service Assistant",
        organizational_goal="Attract 25 qualified community-focused candidates for frontline service roles.",
        target_audience="Recent college graduates and community members seeking active service careers.",
        intended_audience_action="Visit the library career portal and submit an application for assistant roles.",
        core_message="Library service assistants connect patrons with technology, community resources, and welcoming spaces.",
        narrative_arc_type="Morning Setup -> Patron Technology Support -> Team Community Impact",
        verified_evidence=[
            EvidenceItem(
                evidence_id="ev_01",
                source_description="Over 40 percent of daily shift time is spent assisting patrons with digital tech and printing.",
                confidence="DOCUMENTED_METRIC",
            )
        ],
        explicit_unknowns=[
            UnknownItem(
                unknown_id="unk_01",
                description="Specific branch location to film (Central Library vs Memorial Park).",
                classification="ASSUMPTION_REQUIRING_APPROVAL",
                mitigation_or_approval_decision="Requires location manager sign-off prior to shoot day.",
            )
        ],
        production_constraints=ProductionConstraints(
            target_duration_seconds=75,
            target_pacing_wpm=145.0,
            primary_platform="YouTube",
            camera_package=["Sony FX3 (24mm f/4)", "Sony A7IV (85mm f/1.8)"],
            lighting_style="2:1 Corporate Natural Key with 5600K Rim",
        ),
    )

    assert brief.project_id == "cpl_recruiting_2026"
    assert len(brief.verified_evidence) == 1
    assert len(brief.explicit_unknowns) == 1

    # Synthesize script from canonical brief
    script = IntelligentAVScriptGenerator.synthesize_from_brief(brief)

    # Validate deterministic physics
    valid, violations = DeterministicScriptValidator.validate_blueprint(script)
    assert valid is True, f"Validation failed with: {violations}"

    # Render production markdown
    md_output = MasterAVMarkdownRenderer.render(script)
    assert "Production AV Script" in md_output
    assert "Section 1: Strategic Intent" in md_output
    assert "Section 3: Master 3-Column AV Production Script Table" in md_output
    assert "Section 4: Grounded Evidence & Explicit Unknowns" in md_output
