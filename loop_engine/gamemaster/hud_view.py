from loop_engine.gamemaster.state_projector import SystemTelemetryHUD


class TerminalHUDView:
    """
    Shadow 10 (The Game Master) Terminal HUD Renderer.

    Renders high-density, ASCII-safe sovereign operating system projection
    strictly sourced from physical telemetry.
    """

    @staticmethod
    def render(hud: SystemTelemetryHUD) -> str:
        lines = []
        clean_indicator = "CLEAN" if hud.working_tree_clean else "MODIFIED"
        receipts_items = sorted(hud.receipts_by_status.items())
        receipts_summary = ", ".join(f"{k}:{v}" for k, v in receipts_items) if receipts_items else "0 logs"

        lines.append("+------------------------------------------------------------------------------+")
        lines.append(f"| [10 SHADOWS] :: ZERO-TRUST RUNTIME OS [{hud.runtime_version}]".ljust(79) + "|")
        lines.append("+------------------------------------------------------------------------------+")
        lines.append(
            f"| Branch: {hud.git_branch} ({hud.git_commit}) [{clean_indicator}] | Test Files: {hud.discovered_test_files} | WAL Receipts: {hud.total_wal_receipts} ({receipts_summary})".ljust(
                79
            )
            + "|"
        )
        lines.append("+------------------------------------------------------------------------------+")
        lines.append("| SHADOW DOMAINS : REAL-TIME MATRIX                                            |")
        lines.append("+----+------------------+-----------------+----------+--------------+----------+")
        lines.append("| ID | DOMAIN NAME      | CODENAME        | STATUS   | TEST SUITES  | RUNNER   |")
        lines.append("+----+------------------+-----------------+----------+--------------+----------+")

        for d in hud.domains:
            s_id = str(d.shadow_id).rjust(2)
            name = d.name.ljust(16)
            cname = d.code_name.ljust(15)
            status = d.status.ljust(8)
            tsuites = f"{d.test_files_count} files".ljust(12)
            runner_status = ("ACTIVE" if d.has_runner else "NONE").ljust(8)
            lines.append(f"| {s_id} | {name} | {cname} | {status} | {tsuites} | {runner_status} |")

        lines.append("+----+------------------+-----------------+----------+--------------+----------+")
        return "\n".join(lines)
