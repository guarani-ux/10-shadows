from loop_engine.gamemaster.state_projector import SystemTelemetryHUD


class TerminalHUDView:
    """
    Shadow 10 (The Game Master) Terminal HUD Renderer.
    
    Renders high-density, ASCII-framed sovereign operating system projection.
    """

    @staticmethod
    def render(hud: SystemTelemetryHUD) -> str:
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════════════════════════╗")
        lines.append(f"║ ⚔️  {hud.system_name.center(22)} :: ZERO-TRUST RUNTIME OS [{hud.runtime_version}] ║")
        lines.append("╠════════════════════════════════════════════════════════════════════════════════╣")
        lines.append(f"║ Master Branch: {hud.git_branch.ljust(10)} | Passing Tests: {str(hud.total_passing_tests).ljust(4)} | WAL Receipts: {str(hud.total_wal_receipts).ljust(4)} ║")
        lines.append("╠════════════════════════════════════════════════════════════════════════════════╣")
        lines.append("║ SHADOW DOMAINS : REAL-TIME MATRIX                                              ║")
        lines.append("╟────┬──────────────────┬─────────────────┬──────────┬──────────────┬────────────╢")
        lines.append("║ ID │ DOMAIN NAME      │ CODENAME        │ STATUS   │ TESTS PASSED │ RECEIPTS   ║")
        lines.append("╟────┼──────────────────┼─────────────────┼──────────┼──────────────┼────────────╢")

        for d in hud.domains:
            s_id = str(d.shadow_id).rjust(2)
            name = d.name.ljust(16)
            cname = d.code_name.ljust(15)
            status = f"✅ {d.status}".ljust(8) if d.status == "ONLINE" else f"⏳ {d.status}".ljust(8)
            tcount = f"{d.test_count} tests".ljust(12)
            rcount = f"{d.receipts_count} logs".ljust(10)
            lines.append(f"║ {s_id} │ {name} │ {cname} │ {status} │ {tcount} │ {rcount} ║")

        lines.append("╚════╧══════════════════╧═════════════════╧══════════╧══════════════╧════════════╝")
        return "\n".join(lines)
