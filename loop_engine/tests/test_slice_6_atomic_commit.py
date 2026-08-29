from pathlib import Path

import pytest

from loop_engine.receipts import (
    AtomicCommitError,
    ReceiptStore,
    atomic_two_phase_commit,
    compute_file_sha256,
)


def test_compute_file_sha256(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Sovereign Physics", encoding="utf-8")

    digest = compute_file_sha256(test_file)
    assert len(digest) == 64
    assert isinstance(digest, str)


def test_atomic_two_phase_commit_new_file(tmp_path):
    candidate = tmp_path / "candidate.py"
    candidate.write_text("print('hello')", encoding="utf-8")

    dest = tmp_path / "out" / "final.py"
    result = atomic_two_phase_commit(candidate, dest)

    assert result["status"] == "COMMITTED"
    assert dest.exists()
    assert not candidate.exists()
    assert dest.read_text(encoding="utf-8") == "print('hello')"


def test_atomic_two_phase_commit_overwrites_cleanly(tmp_path):
    dest = tmp_path / "existing.py"
    dest.write_text("# Old Version\n", encoding="utf-8")

    candidate = tmp_path / "candidate.py"
    candidate.write_text("# New Version\n", encoding="utf-8")

    result = atomic_two_phase_commit(candidate, dest)

    assert result["status"] == "COMMITTED"
    assert dest.read_text(encoding="utf-8") == "# New Version\n"
    # Ensure backup was cleaned up
    assert not (tmp_path / "existing.py.bak").exists()


def test_atomic_commit_missing_candidate_raises(tmp_path):
    missing_candidate = tmp_path / "missing.py"
    dest = tmp_path / "target.py"

    with pytest.raises(AtomicCommitError):
        atomic_two_phase_commit(missing_candidate, dest)


def test_receipt_store_wal_lifecycle(tmp_path):
    db_file = tmp_path / "test_receipts.db"
    store = ReceiptStore(db_path=db_file)

    row_id = store.record_receipt(
        task_id="slice_6_test",
        run_id="run_001",
        spec_hash="abcdef123456",
        status="SUCCESS",
        strikes_used=1,
        target_file="c:/10 SHADOWS/out.py",
        artifact_sha256="999988887777",
        extra_data={"lines": 10, "gate": "ast_passed"},
    )

    assert row_id == 1

    receipt = store.get_receipt(1)
    assert receipt is not None
    assert receipt["task_id"] == "slice_6_test"
    assert receipt["status"] == "SUCCESS"
    assert receipt["artifact_sha256"] == "999988887777"

    # Query task records
    records = store.query_by_task("slice_6_test")
    assert len(records) == 1
    assert records[0]["run_id"] == "run_001"
