"""
tests/test_governance_mutations.py
Mutation Testing Suite for 10 SHADOWS Declarative Governance.
Verifies that corrupting, deleting, or weakening governance declarations causes
immediate fail-closed rejection rather than permissive execution.
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
                "strike_ceiling": -5,  # Invalid: must be >= 1
            },
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_string_strike_ceiling_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_02.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "strike_ceiling": "UNLIMITED_ATTEMPTS",  # Attacker attempts type confusion
            },
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_invalid_timeout_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_03.yaml"
        data = {
            "version": "1.0.0",
            "governor": {
                "execution_timeout_seconds": -10.0,  # Invalid timeout
            },
        }
        mutant_yaml.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)

    def test_mutant_empty_governance_file_fails_closed(self, tmp_path: Path):
        mutant_yaml = tmp_path / "mutant_gov_04.yaml"
        mutant_yaml.write_text("", encoding="utf-8")  # Empty file
        with pytest.raises(GovernanceConfigurationError, match="FAIL-CLOSED"):
            load_canonical_governance(config_path=mutant_yaml, force_reload=True)
