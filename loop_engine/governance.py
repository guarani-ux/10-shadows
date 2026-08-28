"""
loop_engine/governance.py
Canonical Declarative Governance Engine & Fail-Closed Loader for 10 SHADOWS.

Deep Module providing the single authoritative access point for all declarative
policies declared in governance.yaml. Enforces fail-closed semantics: if governance.yaml
is missing, corrupted, invalid, or contains unknown fields, privileged runtime execution
immediately halts.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_GOVERNANCE_PATH = PROJECT_ROOT / "governance.yaml"


class GovernanceConfigurationError(Exception):
    """Raised when canonical governance configuration is missing, invalid, or fails validation."""
    pass


class GovernorPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    strike_ceiling: int = Field(..., ge=1, le=10)
    execution_timeout_seconds: float = Field(..., ge=1.0, le=600.0)
    rate_limit_refill_rate: float = Field(..., ge=0.1)
    rate_limit_burst_capacity: float = Field(..., ge=1.0)


class VerifierPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    banned_shadow_modules: List[str] = Field(..., min_length=1)


class EnvironmentPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    allowed_env_vars: List[str] = Field(..., min_length=1)


class GovernanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str = Field(...)
    governor: GovernorPolicy = Field(...)
    verifier: VerifierPolicy = Field(...)
    environment: EnvironmentPolicy = Field(...)


# In-memory singleton cache to prevent redundant disk I/O while ensuring fail-closed integrity
_CACHED_GOVERNANCE: Optional[GovernanceConfig] = None


def load_canonical_governance(
    config_path: Optional[Path] = None, force_reload: bool = False
) -> GovernanceConfig:
    """
    Loads and validates the canonical governance configuration.
    Enforces Fail-Closed invariant: Missing, corrupted, or invalid configuration raises GovernanceConfigurationError.
    """
    global _CACHED_GOVERNANCE
    if _CACHED_GOVERNANCE is not None and not force_reload and config_path is None:
        return _CACHED_GOVERNANCE

    target_path = config_path or CANONICAL_GOVERNANCE_PATH

    if not target_path.exists():
        raise GovernanceConfigurationError(
            f"FAIL-CLOSED: Canonical governance file not found at '{target_path}'. "
            "Privileged execution cannot proceed without authoritative governance."
        )

    try:
        raw_text = target_path.read_text(encoding="utf-8")
        raw_dict = yaml.safe_load(raw_text)
        if not isinstance(raw_dict, dict):
            raise GovernanceConfigurationError(
                f"FAIL-CLOSED: Governance file at '{target_path}' did not parse to a valid dictionary."
            )

        config = GovernanceConfig.model_validate(raw_dict)
        if config_path is None:
            _CACHED_GOVERNANCE = config
        return config

    except ValidationError as ve:
        raise GovernanceConfigurationError(
            f"FAIL-CLOSED: Governance schema validation failed for '{target_path}':\n{ve}"
        ) from ve
    except Exception as e:
        if isinstance(e, GovernanceConfigurationError):
            raise
        raise GovernanceConfigurationError(
            f"FAIL-CLOSED: Unexpected failure loading governance configuration from '{target_path}': {e}"
        ) from e
