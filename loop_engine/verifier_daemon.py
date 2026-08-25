import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Invariant: Explicit root anchoring
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNEL_DIR = PROJECT_ROOT / "scratch" / "channel"
INTENT_FILE = CHANNEL_DIR / "intent.json"
RECEIPT_FILE = CHANNEL_DIR / "receipt.json"
ARCHIVE_DIR = CHANNEL_DIR / "archive"


def ensure_channel_dirs():
    """Ensure channel and archive directories exist."""
    CHANNEL_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def process_intent(intent_path: Path) -> Dict[str, Any]:
    """
    Executes physical verification for an incoming intent payload.
    """
    try:
        raw_data = intent_path.read_text(encoding="utf-8")
        intent = json.loads(raw_data)
    except Exception as e:
        return {
            "status": "ERROR",
            "error": f"Malformed intent payload: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    task_id = intent.get("task_id", "unnamed_task")
    test_command = intent.get("test_command")
    spec_hash = intent.get("spec_hash", "")

    if not test_command:
        return {
            "task_id": task_id,
            "status": "ERROR",
            "error": "No 'test_command' specified in intent payload.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    print(f"\n[DAEMON] >>> Received Intent: task_id='{task_id}' (spec_hash={spec_hash[:8] if spec_hash else 'none'})")
    print(f"[DAEMON] Executing: {test_command}")

    # Prepare environment
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    start_time = time.time()
    try:
        proc = subprocess.run(
            test_command,
            shell=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=env,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
        duration = round(time.time() - start_time, 3)
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
        status = "PASS" if exit_code == 0 else "FAIL"

    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 3)
        exit_code = 124
        stdout = ""
        stderr = "Execution timed out after 30 seconds."
        status = "TIMEOUT"
    except Exception as e:
        duration = round(time.time() - start_time, 3)
        exit_code = 1
        stdout = ""
        stderr = f"Subprocess invocation failure: {str(e)}"
        status = "ERROR"

    # Compact stdout/stderr for token efficiency (last 30 lines)
    output_lines = (stdout + "\n" + stderr).strip().splitlines()
    compacted_output = "\n".join(output_lines[-30:]) if len(output_lines) > 30 else "\n".join(output_lines)

    receipt = {
        "task_id": task_id,
        "spec_hash": spec_hash,
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "output_summary": compacted_output,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Write atomic receipt
    tmp_receipt = CHANNEL_DIR / f"receipt_{task_id}.tmp"
    tmp_receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    os.replace(tmp_receipt, RECEIPT_FILE)

    # Archive the intent
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_file = ARCHIVE_DIR / f"intent_{task_id}_{timestamp_str}.json"
    try:
        os.replace(intent_path, archive_file)
    except Exception:
        if intent_path.exists():
            intent_path.unlink()

    status_tag = "[PASS]" if status == "PASS" else f"[{status}]"
    print(f"[DAEMON] <<< Result: {status_tag} (exit={exit_code}, {duration}s)")
    print(f"[DAEMON] Receipt stamped -> {RECEIPT_FILE.name}")
    return receipt


def run_daemon(poll_interval: float = 0.5):
    """
    Main polling loop watching for incoming intent manifests.
    """
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ensure_channel_dirs()
    print("=" * 60)
    print("   10 SHADOWS: VERIFIER DAEMON (CLI HARNESS)")
    print(f"   Listening on: {INTENT_FILE.as_posix()}")
    print("=" * 60)

    try:
        while True:
            if INTENT_FILE.exists():
                time.sleep(0.05)  # brief settle for file write completion
                process_intent(INTENT_FILE)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[DAEMON] Shutting down cleanly.")


if __name__ == "__main__":
    run_daemon()
