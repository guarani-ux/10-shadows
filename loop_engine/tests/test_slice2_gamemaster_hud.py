import pytest
from loop_engine.gamemaster.state_projector import SovereignStateProjector
from loop_engine.gamemaster.hud_view import TerminalHUDView


def test_terminal_hud_view_render(tmp_path):
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud = projector.project_hud()
    rendered = TerminalHUDView.render(hud)

    assert "10 SHADOWS" in rendered
    assert "ZERO-TRUST RUNTIME OS" in rendered
    assert "The Forge" in rendered
    assert "The Game Master" in rendered
    assert "╔" in rendered and "╚" in rendered
