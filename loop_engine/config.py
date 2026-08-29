"""
loop_engine/config.py
Centralized Configuration, Path Management, Resource Limits, and Environment Ownership.

Invariants:
1. Deterministic path resolution across platforms (Windows / Linux / macOS).
2. Explicit configuration overrides via environment variables with safe defaults.
3. Separation of project root, runtime scratch, receipts, and fixtures.
4. Bounded execution limits (timeouts, max stdout bytes, max retry loops).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _resolve_project_root() -> Path:
    env_root = os.environ.get("TEN_SHADOWS_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if p.exists():
            return p
    return Path(__file__).resolve().parent.parent


# Base Paths
PROJECT_ROOT: Path = _resolve_project_root()
SCRATCH_DIR: Path = Path(os.environ.get("TEN_SHADOWS_SCRATCH", str(PROJECT_ROOT / "scratch"))).resolve()
STAGING_DIR: Path = SCRATCH_DIR / "staging"
SANDBOX_DIR: Path = Path(os.environ.get("TEN_SHADOWS_SANDBOX", str(PROJECT_ROOT / "sandbox"))).resolve()
RECEIPTS_DIR: Path = Path(os.environ.get("TEN_SHADOWS_RECEIPTS_DIR", str(PROJECT_ROOT / ".receipts"))).resolve()
FIXTURES_DIR: Path = PROJECT_ROOT / "tests" / "fixtures"

# Database Locations (All in scratch runtime directory by default)
KERNEL_DB_PATH: Path = SCRATCH_DIR / "kernel.db"
RECEIPTS_DB_PATH: Path = SCRATCH_DIR / "receipts.db"
RELATIONAL_DB_PATH: Path = SCRATCH_DIR / "relational.db"
FORGE_DB_PATH: Path = SCRATCH_DIR / "forge.db"
SVRIS_DB_PATH: Path = SCRATCH_DIR / "svris.db"

# Governance Specification
CANONICAL_GOVERNANCE_PATH: Path = PROJECT_ROOT / "governance.yaml"

# Resource & Concurrency Limits
DEFAULT_TIMEOUT_SECONDS: int = int(os.environ.get("TEN_SHADOWS_TIMEOUT_SECONDS", "300"))
MAX_OUTPUT_BYTES: int = int(os.environ.get("TEN_SHADOWS_MAX_OUTPUT_BYTES", str(10 * 1024 * 1024)))  # 10 MB
MAX_RETRY_ATTEMPTS: int = 3  # Hard invariant from Substrate Law 9: 3-strike governor
DEFAULT_LOG_LEVEL: str = os.environ.get("TEN_SHADOWS_LOG_LEVEL", "INFO").upper()

# System Version Identity
SYSTEM_VERSION: str = "3.0.0"
KERNEL_VERSION: str = "TEN_SHADOWS_TRUSTED_KERNEL_RUST_v3"
PROTOCOL_VERSION: str = "3.0.0"
RECEIPT_VERSION: str = "3.0.0"


def ensure_runtime_directories() -> None:
    """Ensures required ephemeral runtime directories exist with appropriate permissions."""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
