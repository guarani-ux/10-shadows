import pytest
import sqlite3
from pathlib import Path
from loop_engine.gamemaster.state_projector import SovereignStateProjector
from loop_engine.gamemaster.hud_view import TerminalHUDView
from loop_engine.receipts import ReceiptStore


def test_truthful_state_projector_dynamic_receipts(tmp_path):
    """Proves that Game Master HUD reflects real SQLite receipts dynamically."""
    db_path = tmp_path / "scratch" / "receipts.db"
    store = ReceiptStore(db_path=db_path)
    
    # Initially zero receipts
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud_0 = projector.project_hud()
    assert hud_0.total_wal_receipts == 0
    assert hud_0.receipts_by_status == {}

    # Insert 2 committed receipts and 1 aborted receipt
    store.record_receipt(task_id="t1", run_id="r1", spec_hash="h1", status="COMMITTED", strikes_used=1)
    store.record_receipt(task_id="t2", run_id="r2", spec_hash="h2", status="COMMITTED", strikes_used=1)
    store.record_receipt(task_id="t3", run_id="r3", spec_hash="h3", status="ABORTED", strikes_used=3)

    hud_1 = projector.project_hud()
    assert hud_1.total_wal_receipts == 3
    assert hud_1.receipts_by_status.get("COMMITTED") == 2
    assert hud_1.receipts_by_status.get("ABORTED") == 1

    # Render HUD and verify status breakdown appears in table (alphabetical: ABORTED:1, COMMITTED:2)
    rendered = TerminalHUDView.render(hud_1)
    assert "WAL Receipts: 3 (ABORTED:1, COMMITTED:2)" in rendered


def test_truthful_state_projector_domain_status_detection(tmp_path):
    """Proves that domain status marks ABSENT if module and runner are missing."""
    projector = SovereignStateProjector(root_dir=tmp_path)
    hud = projector.project_hud()
    
    # An empty directory must have 0 discovered test files and ABSENT domains
    assert hud.discovered_test_files == 0
    for d in hud.domains:
        assert d.status == "ABSENT"
        assert d.has_module is False
        assert d.has_runner is False
