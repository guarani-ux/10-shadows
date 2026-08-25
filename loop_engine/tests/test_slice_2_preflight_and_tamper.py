import pytest
from pathlib import Path
from loop_engine.preflight import (
    canonical_spec_hash,
    verify_disk_writable,
    probe_required_modules,
    run_pre_flight,
    assert_spec_untampered,
    PreflightCheckError,
    SpecTamperError,
)


def test_canonical_spec_hash_determinism():
    spec_a = {"task_id": "t1", "prompt": "build tool", "constraints": ["ast_safe", "no_eval"]}
    spec_b = {"constraints": ["ast_safe", "no_eval"], "prompt": "build tool", "task_id": "t1"}

    # Different dict insertion order must produce identical canonical hash
    assert canonical_spec_hash(spec_a) == canonical_spec_hash(spec_b)


def test_verify_disk_writable(tmp_path):
    valid_dir = tmp_path / "writable_staging"
    assert verify_disk_writable(valid_dir) is True


def test_probe_required_modules():
    # Built-in modules must pass
    ok, missing = probe_required_modules(["os", "sys", "json"])
    assert ok is True
    assert missing == []

    # Non-existent module must be flagged
    ok, missing = probe_required_modules(["non_existent_shadow_module_xyz_999"])
    assert ok is False
    assert "non_existent_shadow_module_xyz_999" in missing


def test_run_pre_flight_success(tmp_path):
    staging_dir = tmp_path / "staging_run"
    spec = {"task_id": "slice_2_spec", "goal": "admission gate"}

    spec_hash = run_pre_flight(spec, staging_dir, required_modules=["hashlib", "pathlib"])
    assert isinstance(spec_hash, str)
    assert len(spec_hash) == 64


def test_run_pre_flight_missing_module_raises(tmp_path):
    staging_dir = tmp_path / "staging_run"
    spec = {"task_id": "slice_2_spec"}

    with pytest.raises(PreflightCheckError) as excinfo:
        run_pre_flight(spec, staging_dir, required_modules=["fake_module_that_does_not_exist_404"])

    assert "Missing required Python module dependencies" in str(excinfo.value)


def test_anti_tamper_validation():
    original_spec = {"task_id": "task_100", "criteria": "deterministic physics"}
    sealed_hash = canonical_spec_hash(original_spec)

    # Identical spec must pass untampered check
    assert_spec_untampered(sealed_hash, original_spec)

    # Mutated spec must raise SpecTamperError
    tampered_spec = {"task_id": "task_100", "criteria": "mutated goal"}
    with pytest.raises(SpecTamperError) as excinfo:
        assert_spec_untampered(sealed_hash, tampered_spec)

    assert "Spec Tamper Violation" in str(excinfo.value)
