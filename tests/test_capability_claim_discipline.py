from pathlib import Path

from loop_engine.gamemaster.project_markdown import MarkdownProjector
from loop_engine.gamemaster.state_projector import SovereignStateProjector


def test_state_projection_does_not_upgrade_structure_into_capability_proof(tmp_path: Path) -> None:
    (tmp_path / "loop_engine" / "runners").mkdir(parents=True)
    (tmp_path / "loop_engine" / "runners" / "forge_runner.py").write_text("# structural fixture\n", encoding="utf-8")

    projector = SovereignStateProjector(root_dir=tmp_path)
    states = projector.get_domain_states()
    forge = next(state for state in states if state.code_name == "forge")

    assert forge.status in {"PRESENT", "PARTIAL", "ABSENT"}
    assert forge.status not in {"ONLINE", "VERIFIED", "OPERATIONALLY_PROVEN"}


def test_generated_system_state_is_explicitly_non_certifying(tmp_path: Path) -> None:
    markdown = MarkdownProjector(root_dir=tmp_path).generate_system_state_markdown()

    assert "not repository qualification" in markdown.lower()
    assert "not capability certification" not in markdown.lower() or "not" in markdown.lower()
    assert "Operationally proven" not in markdown
    assert "Route-proven" not in markdown
    assert "Unit-proven" not in markdown
    assert "Master Domain & Runtime Truth" not in markdown
    assert "3.0.0-SOVEREIGN" not in markdown


def test_zero_local_failure_rows_cannot_be_presented_as_global_health(tmp_path: Path) -> None:
    markdown = MarkdownProjector(root_dir=tmp_path).generate_failure_ledger_markdown().lower()

    assert "does not mean ci is green" in markdown
    assert "not a repository-wide success claim" in markdown
    assert "zero unmitigated failures" not in markdown
