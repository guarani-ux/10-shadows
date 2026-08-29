from loop_engine.gamemaster.state_projector import SystemTelemetryHUD


class TerminalHUDView:
    """Render local structural/runtime telemetry without presenting it as certification."""

    @staticmethod
    def render(hud: SystemTelemetryHUD) -> str:
        lines = []
        clean_indicator = "CLEAN" if hud.working_tree_clean else "MODIFIED"
        receipts_items = sorted(hud.receipts_by_status.items())
        receipts_summary = ", ".join(f"{key}:{value}" for key, value in receipts_items) if receipts_items else "0 logs"

        lines.append("+------------------------------------------------------------------------------+")
        lines.append(f"| [10 SHADOWS] :: LOCAL TELEMETRY [{hud.runtime_version}]".ljust(79) + "|")
        lines.append("+------------------------------------------------------------------------------+")
        lines.append(
            f"| Branch: {hud.git_branch} ({hud.git_commit}) [{clean_indicator}] | Test Files: {hud.discovered_test_files} | Local Receipts: {hud.total_wal_receipts} ({receipts_summary})".ljust(
                79
            )
            + "|"
        )
        lines.append("+------------------------------------------------------------------------------+")
        lines.append("| DOMAIN STRUCTURE : PRESENCE ONLY — NOT CAPABILITY CERTIFICATION              |")
        lines.append("+----+------------------+-----------------+----------+--------------+----------+")
        lines.append("| ID | DOMAIN NAME      | CODENAME        | STATUS   | TEST FILES   | RUNNER   |")
        lines.append("+----+------------------+-----------------+----------+--------------+----------+")

        for domain in hud.domains:
            shadow_id = str(domain.shadow_id).rjust(2)
            name = domain.name.ljust(16)
            code_name = domain.code_name.ljust(15)
            status = domain.status.ljust(8)
            test_files = f"{domain.test_files_count} files".ljust(12)
            runner_status = ("PRESENT" if domain.has_runner else "NONE").ljust(8)
            lines.append(f"| {shadow_id} | {name} | {code_name} | {status} | {test_files} | {runner_status} |")

        lines.append("+----+------------------+-----------------+----------+--------------+----------+")
        lines.append(
            "Telemetry reports observed structure/history only. Verification status lives in CAPABILITY_GROUND_TRUTH.md."
        )
        return "\n".join(lines)
