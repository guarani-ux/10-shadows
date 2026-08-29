"""
loop_engine/sterile_env.py
Canonical Sterile Ring-Fenced Subprocess Environment Engine for 10 SHADOWS.

Deep Module ensuring all subprocess executions (verifier gate, verifier daemon, runner harnesses)
execute inside an isolated, scrubbed environment with zero host secret leakage and strict
runtime isolation.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from loop_engine.governance import load_canonical_governance


def get_allowed_env_vars() -> List[str]:
    """Retrieves authoritative allowlist from canonical governance.yaml."""
    try:
        return load_canonical_governance().environment.allowed_env_vars
    except Exception:
        return [
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


# Canonical allowlist of OS variables permitted to cross subprocess boundaries
ALLOWED_ENV_VARS: List[str] = get_allowed_env_vars()


# Sensitive keyword pattern to scrub even if accidentally matched
SECRET_PATTERN = re.compile(r"(?i)(key|secret|token|pass|auth|credential|cert|private|session|bearer|cookie)")


def is_secret_env_var(var_name: str) -> bool:
    """
    Returns True if the variable name contains sensitive secret or credential keywords.
    """
    return bool(SECRET_PATTERN.search(var_name))


def build_sterile_environment(
    worktree_path: Optional[Path] = None,
    extra_pythonpath: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Constructs a sterile, ring-fenced subprocess environment dictionary.

    Invariants:
    1. Only allowlisted OS environment variables are included.
    2. Any variable name matching SECRET_PATTERN is proactively scrubbed.
    3. User-site Python packages are disabled (PYTHONNOUSERSITE=1).
    4. Bytecode writing is disabled (PYTHONDONTWRITEBYTECODE=1).
    5. Subprocess output is unbuffered (PYTHONUNBUFFERED=1).
    6. PYTHONPATH is explicitly anchored to worktree_path (or PROJECT_ROOT).
    """
    clean_env: Dict[str, str] = {}

    # Filter host environment
    for var in ALLOWED_ENV_VARS:
        if is_secret_env_var(var):
            continue

        if var in os.environ:
            clean_env[var] = os.environ[var]
        elif var.lower() in os.environ:
            clean_env[var] = os.environ[var.lower()]

    # Anchor PYTHONPATH
    pythonpath_entries: List[str] = []
    if worktree_path:
        pythonpath_entries.append(str(worktree_path.resolve()))
    else:
        project_root = Path(__file__).resolve().parent.parent
        pythonpath_entries.append(str(project_root))

    if extra_pythonpath:
        pythonpath_entries.extend(extra_pythonpath)

    clean_env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    clean_env["PYTHONNOUSERSITE"] = "1"
    clean_env["PYTHONUNBUFFERED"] = "1"

    return clean_env
