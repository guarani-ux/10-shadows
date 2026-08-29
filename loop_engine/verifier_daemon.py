"""
loop_engine/verifier_daemon.py
Autonomous Verification Daemon & Claim Ledger Engine for Ten Shadows.

Enforces:
1. Sterile Ring-Fenced Execution: Subprocesses receive only explicitly safe environment variables.
2. Strike Ceiling Governance: Enforces hard stop at 3 consecutive failed attempts via KernelDatabase.
3. Atomic Promotion: Promotes candidate staging files via os.replace ONLY upon verified 0 exit.
4. Cryptographic Receipt Ledger: Writes immutable receipts to .receipts/<task_id>_receipt.json.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loop_engine.kernel_db import KernelDatabase
from loop_engine.schema import FailureClassification

# Invariant: Explicit root anchoring
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNEL_DIR = PROJECT_ROOT / "scratch" / "channel"
INTENT_FILE = CHANNEL_DIR / "intent.json"
RECEIPT_FILE = CHANNEL_DIR / "receipt.json"
ARCHIVE_DIR = CHANNEL_DIR / "archive"
RECEIPTS_LEDGER_DIR = PROJECT_ROOT / ".receipts"

from loop_engine.sterile_env import ALLOWED_ENV_VARS, build_sterile_environment


def ensure_directories():
    """Ensure channel, archive, and receipts ledger directories exist."""
    CHANNEL_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_LEDGER_DIR.mkdir(parents=True, exist_ok=True)


# Backward compatibility alias
ensure_channel_dirs = ensure_directories


def compute_sha256(content: str) -> str:
    """Computes deterministic SHA-256 hash of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def process_intent(
    intent_path: Path,
    kernel_db: Optional[KernelDatabase] = None,
) -> Dict[str, Any]:
    """
    Executes mechanical verification for an incoming intent payload under sterile isolation.
    """
    ensure_directories()
    db = kernel_db or KernelDatabase()

    try:
        raw_data = intent_path.read_text(encoding="utf-8")
        intent = json.loads(raw_data)
    except Exception as e:
        return {
            "status": "ERROR",
            "error": f"Malformed intent payload: {str(e)}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    task_id = intent.get("task_id", f"task_{int(time.time())}")
    test_command = intent.get("test_command", "python -m pytest -q")
    plan_hash = intent.get("plan_hash") or intent.get("spec_hash") or ""
    candidate_path_str = intent.get("candidate_path")
    target_path_str = intent.get("target_path")
    git_diff_hash = intent.get("git_diff_hash", "")

    # 1. Strike Governor Ceiling Check
    strikes = db.get_strikes(task_id)
    if strikes >= 3:
        receipt = {
            "task_id": task_id,
            "plan_hash": plan_hash,
            "git_diff_hash": git_diff_hash,
            "test_digest": "STRIKE_CEILING_BLOCKED",
            "status": "BLOCKED",
            "strikes_used": strikes,
            "error": f"Task '{task_id}' has reached the 3-strike failure ceiling and is forcefully halted.",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        _persist_receipts(task_id, receipt, intent_path)
        return receipt

    print(
        f"\n[DAEMON] >>> Received Intent: task_id='{task_id}' (strikes={strikes}/3, plan_hash={plan_hash[:8] if plan_hash else 'none'})"
    )
    print(f"[DAEMON] Executing sterile command: {test_command}")

    sterile_env = build_sterile_environment()
    start_time = time.time()

    try:
        proc = subprocess.run(
            test_command,
            shell=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=sterile_env,
            stdin=subprocess.DEVNULL,
            timeout=45,
        )
        duration = round(time.time() - start_time, 3)
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
        passed = exit_code == 0

    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 3)
        exit_code = 124
        stdout = ""
        stderr = "Execution timed out after 45 seconds."
        passed = False
    except Exception as e:
        duration = round(time.time() - start_time, 3)
        exit_code = 1
        stdout = ""
        stderr = f"Subprocess invocation failure: {str(e)}"
        passed = False

    test_digest = compute_sha256(stdout + stderr)
    status = "VERIFIED" if passed else "REJECTED"

    # 2. Strike Ledger Update on Failure
    if not passed:
        classification = (
            FailureClassification.ENVIRONMENT_FAILURE if exit_code == 124 else FailureClassification.CANDIDATE_FAILURE
        )
        db.record_strike(
            task_id=task_id,
            classification=classification,
            signature=f"exit_code_{exit_code}_{test_digest[:12]}",
        )

    # 3. Atomic Promotion on PASS
    promotion_info = None
    if passed and candidate_path_str and target_path_str:
        candidate_file = Path(candidate_path_str)
        target_file = Path(target_path_str)
        if candidate_file.exists():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            temp_target = target_file.parent / f".tmp_{target_file.name}_{int(time.time() * 1000)}"
            candidate_file.replace(temp_target)
            os.replace(temp_target, target_file)
            promotion_info = {
                "promoted_target": str(target_file),
                "promoted_at": datetime.now(timezone.utc).isoformat(),
            }
            print(f"[DAEMON] Atomic Promotion SUCCESS: {candidate_file.name} -> {target_file}")

    # Compact output summary
    output_lines = (stdout + "\n" + stderr).strip().splitlines()
    compacted_output = "\n".join(output_lines[-30:]) if len(output_lines) > 30 else "\n".join(output_lines)

    receipt = {
        "task_id": task_id,
        "plan_hash": plan_hash,
        "git_diff_hash": git_diff_hash,
        "test_digest": test_digest,
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "promotion": promotion_info,
        "output_summary": compacted_output,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    _persist_receipts(task_id, receipt, intent_path)

    status_tag = "[VERIFIED]" if status == "VERIFIED" else f"[{status}]"
    print(f"[DAEMON] <<< Result: {status_tag} (exit={exit_code}, {duration}s)")
    return receipt


def _persist_receipts(task_id: str, receipt: Dict[str, Any], intent_path: Path) -> None:
    """Writes atomic receipts to both channel receipt and permanent ledger."""
    # 1. Channel Receipt (atomic)
    tmp_receipt = CHANNEL_DIR / f"receipt_{task_id}.tmp"
    tmp_receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    os.replace(tmp_receipt, RECEIPT_FILE)

    # 2. Immutable Ledger Receipt (.receipts/<task_id>_receipt.json)
    ledger_receipt_path = RECEIPTS_LEDGER_DIR / f"{task_id}_receipt.json"
    ledger_tmp = RECEIPTS_LEDGER_DIR / f".tmp_{task_id}_receipt.json"
    ledger_tmp.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    os.replace(ledger_tmp, ledger_receipt_path)

    # 3. Archive Intent
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_file = ARCHIVE_DIR / f"intent_{task_id}_{timestamp_str}.json"
    try:
        os.replace(intent_path, archive_file)
    except Exception:
        if intent_path.exists():
            try:
                intent_path.unlink()
            except Exception:
                pass


def run_daemon(poll_interval: float = 0.5):
    """Main polling loop watching for incoming intent manifests."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ensure_directories()
    print("=" * 60)
    print("   10 SHADOWS: VERIFIER DAEMON (CLI HARNESS & CLAIM LEDGER)")
    print(f"   Listening on: {INTENT_FILE.as_posix()}")
    print(f"   Ledger at:    {RECEIPTS_LEDGER_DIR.as_posix()}")
    print("=" * 60)

    try:
        while True:
            if INTENT_FILE.exists():
                time.sleep(0.05)  # settle time
                process_intent(INTENT_FILE)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[DAEMON] Shutting down cleanly.")


if __name__ == "__main__":
    run_daemon()
