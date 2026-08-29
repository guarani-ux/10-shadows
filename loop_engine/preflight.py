import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class PreflightCheckError(Exception):
    """Raised when environment or module dependencies fail admission checks."""

    pass


class SpecTamperError(Exception):
    """Raised when an attempt is made to mutate sealed task objectives or constraints."""

    pass


def canonical_spec_hash(task_spec: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 hash over the task specification.
    Sorts all dictionary keys and normalizes nested collections.
    """
    serialized = json.dumps(task_spec, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_disk_writable(target_dir: Path) -> bool:
    """
    Validates physical disk write permissions in the target directory by creating
    and removing a temporary probe file.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    probe_file = target_dir / f".probe_{os.getpid()}_{hashlib.sha256(str(target_dir).encode()).hexdigest()[:8]}"
    try:
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink()
        return True
    except (OSError, IOError):
        return False


def probe_required_modules(required_modules: List[str]) -> Tuple[bool, List[str]]:
    """
    Probes Python runtime for required module availability using importlib.util.find_spec.
    Returns (all_available: bool, missing_modules: List[str]).
    """
    missing = []
    for mod_name in required_modules:
        spec = importlib.util.find_spec(mod_name)
        if spec is None:
            missing.append(mod_name)
    return len(missing) == 0, missing


def run_pre_flight(
    task_spec: Dict[str, Any],
    staging_dir: Path,
    required_modules: Optional[List[str]] = None,
) -> str:
    """
    Phase 0 Admission Gate:
    1. Validates disk write access in staging boundary.
    2. Verifies module dependencies via find_spec.
    3. Seals task_spec with canonical SHA-256 hash.

    Returns sealed spec_hash. Raises PreflightCheckError on failure.
    """
    # 1. Disk probe
    if not verify_disk_writable(staging_dir):
        raise PreflightCheckError(f"Staging boundary '{staging_dir}' is not writable.")

    # 2. Dependency probe
    if required_modules:
        ok, missing = probe_required_modules(required_modules)
        if not ok:
            raise PreflightCheckError(f"Missing required Python module dependencies: {missing}")

    # 3. Canonical spec seal
    return canonical_spec_hash(task_spec)


def assert_spec_untampered(original_hash: str, current_spec: Dict[str, Any]) -> None:
    """
    Enforces anti-tamper invariant during iterative loops.
    Raises SpecTamperError if current spec does not match original sealed hash.
    """
    current_hash = canonical_spec_hash(current_spec)
    if current_hash != original_hash:
        raise SpecTamperError(
            f"Spec Tamper Violation: Hash mismatch. Original: '{original_hash}', Current: '{current_hash}'."
        )
