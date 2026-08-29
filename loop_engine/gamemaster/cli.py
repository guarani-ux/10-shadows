import argparse
import sys
from pathlib import Path

from loop_engine.base import PROJECT_ROOT
from loop_engine.gamemaster.hud_view import TerminalHUDView
from loop_engine.gamemaster.state_projector import SovereignStateProjector


def run_cli():
    """
    Shadow 10 (The Game Master) CLI Entrypoint.
    Executes master system projections and domain status queries.
    """
    parser = argparse.ArgumentParser(
        prog="10shadows",
        description="10 SHADOWS: Zero-Trust Autonomous Execution Operating System",
    )

    parser.add_argument(
        "--hud",
        action="store_true",
        help="Project real-time system health and domain matrix HUD.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="10 SHADOWS v3.0.0-SOVEREIGN",
    )

    args = parser.parse_args()

    projector = SovereignStateProjector(root_dir=PROJECT_ROOT)
    hud = projector.project_hud()
    print(TerminalHUDView.render(hud))


if __name__ == "__main__":
    run_cli()
