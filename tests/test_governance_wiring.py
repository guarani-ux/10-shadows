"""
tests/test_governance_wiring.py
Adversarial TDD Acceptance Suite for Sovereign Governance Wiring.
Enforces:
1. Canonical governance.yaml is the single authoritative source of the StepGovernor strike ceiling.
2. Production callers cannot override strike policy via kwargs/defaults.
3. Missing or corrupted governance fails closed immediately.
4. Changing governance physically alters retry and abort behavior.
"""

from pathlib import Path

import pytest
import yaml

from loop_engine.governance import (
    GovernanceConfig,
    GovernanceConfigurationError,
    load_canonical_governance,
)
from loop_engine.governor import (
    GovernanceOverrideProhibitedError,
    StepGovernor,
)
from loop_engine.kernel_db import KernelDatabase


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
        invalid_schema.write_text(
            "version: '1.0.0'\n"
            "governor:\n"
            "  strike_ceiling: 9999\n"  # Exceeds max 10
            "  execution_timeout_seconds: 45.0\n"
            "  rate_limit_refill_rate: 10.0\n"
            "  rate_limit_burst_capacity: 50.0\n"
            "verifier:\n"
            "  banned_shadow_modules: ['pytest.py']\n"
            "environment:\n"
            "  allowed_env_vars: ['PATH']\n",
            encoding="utf-8",
        )
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED: Governance schema validation failed"):
            load_canonical_governance(config_path=invalid_schema, force_reload=True)

    def test_unknown_field_fails_closed(self, tmp_path: Path):
        unknown_field_yaml = tmp_path / "unknown_field.yaml"
        unknown_field_yaml.write_text(
            "version: '1.0.0'\n"
            "disable_governance: true\n"  # Unknown field
            "governor:\n"
            "  strike_ceiling: 3\n"
            "  execution_timeout_seconds: 45.0\n"
            "  rate_limit_refill_rate: 10.0\n"
            "  rate_limit_burst_capacity: 50.0\n"
            "verifier:\n"
            "  banned_shadow_modules: ['pytest.py']\n"
            "environment:\n"
            "  allowed_env_vars: ['PATH']\n",
            encoding="utf-8",
        )
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED: Governance schema validation failed"):
            load_canonical_governance(config_path=unknown_field_yaml, force_reload=True)


class TestSovereignGovernanceBehavior:
    def test_behavioral_strike_ceiling_1(self, tmp_path: Path):
        custom_yaml = tmp_path / "gov_1.yaml"
        custom_yaml.write_text(
            "version: '1.0.0'\n"
            "governor:\n"
            "  strike_ceiling: 1\n"
            "  execution_timeout_seconds: 30.0\n"
            "  rate_limit_refill_rate: 10.0\n"
            "  rate_limit_burst_capacity: 50.0\n"
            "verifier:\n"
            "  banned_shadow_modules: ['pytest.py']\n"
            "environment:\n"
            "  allowed_env_vars: ['PATH']\n",
            encoding="utf-8",
        )
        config = load_canonical_governance(config_path=custom_yaml, force_reload=True)
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        governor = StepGovernor._create_for_test(kernel_db=db, governance_config=config)

        result = governor.run_step(
            loop=FailingLoop(),
            raw_input={"task_id": "task_strike_1"},
            step_id="step_01",
        )
        assert result.status == "ABORTED"
        assert result.strikes_used == 1

    def test_behavioral_strike_ceiling_2(self, tmp_path: Path):
        custom_yaml = tmp_path / "gov_2.yaml"
        custom_yaml.write_text(
            "version: '1.0.0'\n"
            "governor:\n"
            "  strike_ceiling: 2\n"
            "  execution_timeout_seconds: 30.0\n"
            "  rate_limit_refill_rate: 10.0\n"
            "  rate_limit_burst_capacity: 50.0\n"
            "verifier:\n"
            "  banned_shadow_modules: ['pytest.py']\n"
            "environment:\n"
            "  allowed_env_vars: ['PATH']\n",
            encoding="utf-8",
        )
        config = load_canonical_governance(config_path=custom_yaml, force_reload=True)
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        governor = StepGovernor._create_for_test(kernel_db=db, governance_config=config)

        result = governor.run_step(
            loop=FailingLoop(),
            raw_input={"task_id": "task_strike_2"},
            step_id="step_02",
        )
        assert result.status == "ABORTED"
        assert result.strikes_used == 2

    def test_caller_override_attack_prohibited(self, tmp_path: Path):
        db = KernelDatabase(db_path=tmp_path / "kernel.db")
        with pytest.raises(
            GovernanceOverrideProhibitedError, match="Manual strike/governance override 'max_strikes=999' is prohibited"
        ):
            StepGovernor(kernel_db=db, max_strikes=999)

    def test_missing_governance_construction_fails_closed(self, tmp_path: Path, monkeypatch):
        import loop_engine.governance as gov_mod

        # Point canonical path to a non-existent path
        monkeypatch.setattr(gov_mod, "CANONICAL_GOVERNANCE_PATH", tmp_path / "non_existent.yaml")
        monkeypatch.setattr(gov_mod, "_CACHED_GOVERNANCE", None)

        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            StepGovernor()
