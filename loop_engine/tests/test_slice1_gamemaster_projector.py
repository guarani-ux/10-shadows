from loop_engine.gamemaster.hud_view import TerminalHUDView
from loop_engine.gamemaster.state_projector import SovereignStateProjector
from loop_engine.receipts import ReceiptStore


def test_truthful_state_projector_dynamic_receipts(tmp_path):
    """Game Master reports local receipt counts without converting them into capability proof."""
    db_path = tmp_path / "scratch" / "receipts.db"
    store = ReceiptStore(db_path=db_path)

    projector = SovereignStateProjector(root_dir=tmp_path)
    hud_0 = projector.project_hud()
    assert hud_0.total_wal_receipts == 0
    assert hud_0.receipts_by_status == {}

    store.record_receipt(task_id="t1", run_id="r1", spec_hash="h1", status="COMMITTED", strikes_used=1)
    store.record_receipt(task_id="t2", run_id="r2", spec_hash="h2", status="COMMITTED", strikes_used=1)
    store.record_receipt(task_id="t3", run_id="r3", spec_hash="h3", status="ABORTED", strikes_used=3)

    hud_1 = projector.project_hud()
    assert hud_1.total_wal_receipts == 3
    assert hud_1.receipts_by_status.get("COMMITTED") == 2
    assert hud_1.receipts_by_status.get("ABORTED") == 1

    rendered = TerminalHUDView.render(hud_1)
    assert "Local Receipts: 3 (ABORTED:1, COMMITTED:2)" in rendered
    assert "PRESENCE ONLY" in rendered
    assert "OPERATIONALLY PROVEN" not in rendered.upper()


def test_truthful_state_projector_domain_status_detection(tmp_path):
    """An empty repository cannot acquire capability status from names alone."""
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud = projector.project_hud()

    assert hud.discovered_test_files == 0
    for domain in hud.domains:
        assert domain.status == "ABSENT"
        assert domain.has_module is False
        assert domain.has_runner is False
