import pytest
from loop_engine.herald.generator import IntelligentAVScriptGenerator
from loop_engine.herald.renderer import MasterAVMarkdownRenderer
from loop_engine.herald.cutdowns import ModularCutDownExtractor


def test_intelligent_av_script_generator_synthesis():
    brief = {
        "project_title": "Enterprise Cloud Architecture Explainer",
        "organizational_goal": "Educate enterprise buyers on zero-trust cloud infrastructure.",
        "target_audience_persona": "Chief Information Security Officers and Lead Architects.",
        "core_brand_alignment": "Zero-trust verification and sovereign cryptographic custody.",
        "narrative_arc_type": "Risk Exposure -> Architectural Solution -> Measurable ROI",
        "scenes": [
            {
                "name": "Scene 1: The Perimeter Myth",
                "start": 0.0,
                "end": 20.0,
                "audio": "Traditional network firewalls are no longer enough. When an attacker gains internal credentials, perimeter defenses fall completely.",
                "video": "Wide Shot (24mm, f/4) looking down a glowing server aisle. 4:1 dramatic lighting ratio with blue kicker light.",
            },
            {
                "name": "Scene 2: Cryptographic Isolation",
                "start": 20.0,
                "end": 50.0,
                "audio": "Our zero-trust microkernel enforces ephemeral sandbox isolation on every single payload. Nothing touches disk without physical verification.",
                "video": "Cut to MCU (85mm, f/1.8) on lead security engineer at workstation. On-screen graphic highlighting Git worktree lifecycle.",
            }
        ]
    }

    script = IntelligentAVScriptGenerator.synthesize_script(brief)

    assert script.strategic_intent.project_title == "Enterprise Cloud Architecture Explainer"
    assert len(script.av_table) == 2
    assert script.technical_scope.target_runtime_seconds == 50
    assert len(script.technical_scope.modular_cutdowns) >= 1

    # Test Markdown rendering
    md_output = MasterAVMarkdownRenderer.render(script)
    assert "# Production AV Script: Enterprise Cloud Architecture Explainer" in md_output
    assert "## Section 1: Strategic Intent & Goal Alignment" in md_output
    assert "## Section 3: Master 3-Column AV Production Script Table" in md_output
    assert "Scene 1: The Perimeter Myth" in md_output
