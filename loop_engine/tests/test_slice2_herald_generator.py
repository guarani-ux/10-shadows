import pytest
from loop_engine.herald.input_contract import CanonicalMediaBrief, ProductionConstraints
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.renderer import MasterAVMarkdownRenderer


def test_intelligent_av_script_generator_synthesis():
    brief = CanonicalMediaBrief(
        project_id="cloud_arch_01",
        project_title="Enterprise Cloud Architecture Explainer",
        organizational_goal="Educate enterprise buyers on zero-trust cloud infrastructure.",
        target_audience="Chief Information Security Officers and Lead Architects.",
        intended_audience_action="Request a technical demo on our cloud architecture portal.",
        core_message="Zero-trust verification and sovereign cryptographic custody.",
        narrative_arc_type="Risk Exposure -> Architectural Solution -> Measurable ROI",
        production_constraints=ProductionConstraints(
            target_duration_seconds=60,
            target_pacing_wpm=150.0,
            camera_package=["Sony FX3 (24mm f/4)", "Sony A7IV (85mm f/1.8)"],
        ),
    )

    script = IntelligentAVScriptGenerator.synthesize_from_brief(brief)

    assert script.strategic_intent.project_title == "Enterprise Cloud Architecture Explainer"
    assert len(script.av_table) == 3
    assert script.technical_scope.target_runtime_seconds == 60
    assert len(script.technical_scope.modular_cutdowns) >= 1

    # Test Markdown rendering
    md_output = MasterAVMarkdownRenderer.render(script)
    assert "# Production AV Script: Enterprise Cloud Architecture Explainer" in md_output
    assert "## Section 1: Strategic Intent & Goal Alignment" in md_output
    assert "## Section 3: Master 3-Column AV Production Script Table" in md_output
    assert "Scene 1: The Hook" in md_output
