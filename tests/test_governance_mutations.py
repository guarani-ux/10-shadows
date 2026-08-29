"""
tests/test_governance_mutations.py
Mutation Testing Suite for 10 SHADOWS Declarative Governance.
Verifies that corrupting, deleting, weakening, or injecting unknown fields into governance
declarations causes immediate fail-closed rejection rather than permissive execution.
"""

from pathlib import Path

import pytest
import yaml

from loop_engine.governance import (
    GovernanceConfigurationError,
    load_canonical_governance,
)


class TestGovernanceMutations:
    def test_mutant_negative_strike_ceiling_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_01.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": -5,  # Mutant: negative value
                "execution_timeout_seconds": 45.0,
                "rate_limit_refill_rate": 10.0,
                "rate_limit_burst_capacity: float": 50.0,
            },
            "verifier": {"banned_shadow_modules": ["pytest.py"]},
            "environment": {"allowed_env_vars": ["PATH"]},
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_zero_strike_ceiling_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_02.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": 0,  # Mutant: zero value (must be >= 1)
                "execution_timeout_seconds": 45.0,
                "rate_limit_refill_rate": 10.0,
                "rate_limit_burst_capacity": 50.0,
            },
            "verifier": {"banned_shadow_modules": ["pytest.py"]},
            "environment": {"allowed_env_vars": ["PATH"]},
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_string_strike_ceiling_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_03.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": "three",  # Mutant: type confusion
                "execution_timeout_seconds": 45.0,
                "rate_limit_refill_rate": 10.0,
                "rate_limit_burst_capacity": 50.0,
            },
            "verifier": {"banned_shadow_modules": ["pytest.py"]},
            "environment": {"allowed_env_vars": ["PATH"]},
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_missing_section_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_04.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": 3,
                "execution_timeout_seconds": 45.0,
                "rate_limit_refill_rate": 10.0,
                "rate_limit_burst_capacity": 50.0,
            },
            # Mutant: verifier and environment sections completely omitted
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_empty_banned_modules_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_05.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": 3,
                "execution_timeout_seconds": 45.0,
                "rate_limit_refill_rate": 10.0,
                "rate_limit_burst_capacity": 50.0,
            },
            "verifier": {"banned_shadow_modules": []},  # Mutant: empty list (min_length=1)
            "environment": {"allowed_env_vars": ["PATH"]},
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_unknown_field_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_06.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": 3,
                "execution_timeout_seconds": 45.0,
                "rate_limit_refill_rate": 10.0,
                "rate_limit_burst_capacity": 50.0,
                "allow_infinite_retries": True,  # Mutant: unknown field injected
            },
            "verifier": {"banned_shadow_modules": ["pytest.py"]},
            "environment": {"allowed_env_vars": ["PATH"]},
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)
