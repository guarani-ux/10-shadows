"""
tests/test_governance_wiring.py
Adversarial TDD Acceptance Suite for Canonical Governance Wiring.
Enforces:
1. Governance must be mechanically consumed by runtime subsystems.
2. Missing or corrupted governance must FAIL CLOSED immediately.
3. Modifying policy parameters physically changes system behavior.
"""

from pathlib import Path
import pytest
import yaml

from loop_engine.governance import (
    GovernanceConfig,
    GovernanceConfigurationError,
    load_canonical_governance,
)
from loop_engine.governor import StepGovernor
from loop_engine.kernel_db import KernelDatabase


class TestCanonicalGovernanceLoader:
    def test_canonical_governance_loads_successfully(self):
        config = load_canonical_governance(force_reload=True)
        assert config.version == "1.0.0"
        assert config.governor.strike_ceiling == 3
        assert "pytest.py" in config.verifier.banned_shadow_modules
        assert "SYSTEMROOT" in config.environment.allowed_env_vars

    def test_missing_governance_file_fails_closed(self, tmp_path: Path):
        non_existent = tmp_path / "missing_governance.yaml"
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED: Canonical governance file not found"):
            load_canonical_governance(config_path=non_existent, force_reload=True)

    def test_corrupted_yaml_fails_closed(self, tmp_path: Path):
        corrupted = tmp_path / "corrupted_governance.yaml"
        corrupted.write_text("governor:\n  strike_ceiling: [unclosed_list", encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=corrupted, force_reload=True)

    def test_schema_violation_fails_closed(self, tmp_path: Path):
        invalid_schema = tmp_path / "invalid_governance.yaml"
        invalid_schema.write_text("governor:\n  strike_ceiling: 9999\n", encoding="utf-8")  # Exceeds max 10
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED: Governance schema validation failed"):
            load_canonical_governance(config_path=invalid_schema, force_reload=True)


class TestGovernanceBehavioralEnforcement:
    def test_strike_ceiling_behavioral_change(self, tmp_path: Path):
        # Create custom governance with strike_ceiling=1
        custom_yaml = tmp_path / "custom_governance.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": 1,
                "execution_timeout_seconds": 30.0,
            },
            "verifier": {
                "banned_shadow_modules": ["malicious.py"],
            },
            "environment": {
                "allowed_env_vars": ["PATH"],
            },
        }
        custom_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")

        config = load_canonical_governance(config_path=custom_yaml, force_reload=True)
        assert config.governor.strike_ceiling == 1

        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        governor = StepGovernor(
            max_strikes=config.governor.strike_ceiling,
            kernel_db=db,
        )

        class FailingLoop:
            def __init__(self):
                self.name = "FailingTestLoop"
            def normalize(self, raw_input):
                return raw_input
            def execute_staging(self, task_spec, staging_dir, feedback=None):
                out_file = staging_dir / "candidate.txt"
                out_file.write_text("candidate content", encoding="utf-8")
                return out_file

            def verify(self, candidate_path, task_spec):
                return False, "Forced failure for strike test"
            def commit(self, candidate_path, attempts, strikes, candidate_hash):
                return {"status": "COMMITTED"}



        # Run step with forced failure
        result = governor.run_step(
            loop=FailingLoop(),
            raw_input={"task_id": "task_strike_1"},
            step_id="step_01",
        )
        assert result.status == "ABORTED"
        assert result.strikes_used == 1

