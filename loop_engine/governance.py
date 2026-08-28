"""
loop_engine/governance.py
Canonical Declarative Governance Engine & Fail-Closed Loader for 10 SHADOWS.

Deep Module providing the single authoritative access point for all declarative
policies declared in governance.yaml. Enforces fail-closed semantics: if governance.yaml
is missing, corrupted, or invalid, privileged runtime execution immediately halts.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_GOVERNANCE_PATH = PROJECT_ROOT / "governance.yaml"


class GovernanceConfigurationError(Exception):
    """Raised when canonical governance configuration is missing, invalid, or fails validation."""
    pass


class GovernorPolicy(BaseModel):
    strike_ceiling: int = Field(default=3, ge=1, le=10)
    execution_timeout_seconds: float = Field(default=45.0, ge=1.0, le=600.0)
    rate_limit_refill_rate: float = Field(default=10.0, ge=0.1)
    rate_limit_burst_capacity: float = Field(default=50.0, ge=1.0)


class VerifierPolicy(BaseModel):
    banned_shadow_modules: List[str] = Field(
        default_factory=lambda: [
            "pytest.py",
            "pytest.pyc",
            "_pytest",
            "sitecustomize.py",
            "usercustomize.py",
            "unittest.py",
            "subprocess.py",
            "os.py",
            "sys.py",
        ]
    )


class EnvironmentPolicy(BaseModel):
    allowed_env_vars: List[str] = Field(
        default_factory=lambda: [
            "SYSTEMROOT",
            "PATH",
            "PATHEXT",
            "USERPROFILE",
            "TMP",
            "TEMP",
            "HOME",
            "LANG",
            "LC_ALL",
            "HOMEDRIVE",
            "HOMEPATH",
            "APPDATA",
            "LOCALAPPDATA",
            "COMSPEC",
            "WINDIR",
        ]
    )


class GovernanceConfig(BaseModel):
    version: str = "1.0.0"
    governor: GovernorPolicy = Field(default_factory=GovernorPolicy)
    verifier: VerifierPolicy = Field(default_factory=VerifierPolicy)
    environment: EnvironmentPolicy = Field(default_factory=EnvironmentPolicy)
    fail_closed: bool = True


# In-memory singleton cache to prevent redundant disk I/O while ensuring fail-closed integrity
_CACHED_GOVERNANCE: Optional[GovernanceConfig] = None


def load_canonical_governance(
    config_path: Optional[Path] = None, force_reload: bool = False
) -> GovernanceConfig:
    """
    Loads and validates the canonical governance configuration.
    Enforces Fail-Closed invariant: Missing or corrupted configuration raises GovernanceConfigurationError.
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
