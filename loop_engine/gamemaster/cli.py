import argparse

from loop_engine.base import PROJECT_ROOT
from loop_engine.gamemaster.hud_view import TerminalHUDView
from loop_engine.gamemaster.state_projector import SovereignStateProjector


def run_cli():
    """Render scoped local telemetry and domain-structure observations."""
    parser = argparse.ArgumentParser(
        prog="10shadows",
        description="10 SHADOWS: governed-execution development tools and local telemetry",
    )

    parser.add_argument(
        "--hud",
        action="store_true",
        help="Project local repository/runtime telemetry and domain structural presence.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="10 SHADOWS telemetry-v1",
    )

    parser.parse_args()

    projector = SovereignStateProjector(root_dir=PROJECT_ROOT)
    hud = projector.project_hud()
    print(TerminalHUDView.render(hud))


if __name__ == "__main__":
    run_cli()
