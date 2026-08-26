import pytest
from pathlib import Path
from loop_engine.gamemaster.state_projector import SovereignStateProjector


def test_sovereign_state_projector(tmp_path):
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud = projector.project_hud()

    assert hud.system_name == "10 SHADOWS"
    assert hud.runtime_version == "3.0.0-SOVEREIGN"
    assert len(hud.domains) == 10
    assert hud.domains[0].name == "The Forge"
    assert hud.domains[9].name == "The Game Master"
    assert hud.total_passing_tests >= 61
