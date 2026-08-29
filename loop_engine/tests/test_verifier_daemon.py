import json
from pathlib import Path

import pytest

from loop_engine.verifier_daemon import (
    CHANNEL_DIR,
    INTENT_FILE,
    RECEIPT_FILE,
    ensure_channel_dirs,
    process_intent,
)


def test_verifier_daemon_channel_lifecycle(tmp_path, monkeypatch):
    test_channel = tmp_path / "channel"
    test_archive = test_channel / "archive"
    monkeypatch.setattr("loop_engine.verifier_daemon.CHANNEL_DIR", test_channel)
    monkeypatch.setattr("loop_engine.verifier_daemon.INTENT_FILE", test_channel / "intent.json")
    monkeypatch.setattr("loop_engine.verifier_daemon.RECEIPT_FILE", test_channel / "receipt.json")
    monkeypatch.setattr("loop_engine.verifier_daemon.ARCHIVE_DIR", test_archive)

    ensure_channel_dirs()
    assert test_channel.exists()
    assert test_archive.exists()

    # 1. Test valid intent execution (running python -c "print('hello')")
    intent_data = {
        "task_id": "test_ping",
        "spec_hash": "abc12345",
        "test_command": "python -c \"print('DAEMON_ALIVE')\"",
    }
    intent_path = test_channel / "intent.json"
    intent_path.write_text(json.dumps(intent_data), encoding="utf-8")

    receipt = process_intent(intent_path)
    assert receipt["status"] in ("PASS", "VERIFIED")
    assert receipt["exit_code"] == 0
    assert "DAEMON_ALIVE" in receipt["output_summary"]
    assert receipt["task_id"] == "test_ping"
    assert (test_channel / "receipt.json").exists()

    # Ensure intent was archived
    assert not intent_path.exists()
    archives = list(test_archive.glob("*.json"))
    assert len(archives) == 1


def test_verifier_daemon_failing_command(tmp_path, monkeypatch):
    test_channel = tmp_path / "channel"
    test_archive = test_channel / "archive"
    monkeypatch.setattr("loop_engine.verifier_daemon.CHANNEL_DIR", test_channel)
    monkeypatch.setattr("loop_engine.verifier_daemon.INTENT_FILE", test_channel / "intent.json")
    monkeypatch.setattr("loop_engine.verifier_daemon.RECEIPT_FILE", test_channel / "receipt.json")
    monkeypatch.setattr("loop_engine.verifier_daemon.ARCHIVE_DIR", test_archive)

    ensure_channel_dirs()

    import time

    from loop_engine.kernel_db import KernelDatabase

    test_db = KernelDatabase(tmp_path / "test_kernel.db")

    # Test failing command
    intent_data = {
        "task_id": f"test_failure_{int(time.time() * 1000)}",
        "spec_hash": "deadbeef",
        "test_command": "python -c \"raise RuntimeError('Intentional crash')\"",
    }
    intent_path = test_channel / "intent.json"
    intent_path.write_text(json.dumps(intent_data), encoding="utf-8")

    receipt = process_intent(intent_path, kernel_db=test_db)
    assert receipt["status"] in ("FAIL", "REJECTED")
    assert receipt["exit_code"] != 0
    assert "RuntimeError: Intentional crash" in receipt["output_summary"]
