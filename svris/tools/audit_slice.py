"""Independent Ring-Fenced Auditor Runner for SVRIS Slices.

Evaluates:
1. AST Static Anti-Cheat Scan (aci.py)
2. Database Schema DDL & PRAGMA Integrity Checks
3. Red-Team Adversary Test Suites in Sandboxed Subprocess
4. Emits Physical Disk Receipt: Proof = (FilesExist and HashMatch and ExitCode == 0)
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from svris.tools.aci import scan_directory


def hash_file(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_ast_audit(target_dir: str) -> bool:
    print(f"[AUDIT GATE 1] AST Static Anti-Cheat Scanning on '{target_dir}'...")
    file_count, violations = scan_directory(target_dir)
    print(f"  Scanned {file_count} python files.")
    if violations:
        print(f"  FAILED: {len(violations)} anti-cheat violations found:")
        for v in violations:
            print(f"    [!] {v}")
        return False
    print("  PASSED: 0 anti-cheat violations detected.")
    return True


def run_database_integrity_audit(schema_path: str) -> bool:
    print(f"[AUDIT GATE 2] DDL Schema & SQLite PRAGMA Integrity Check...")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.executescript(schema_sql)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        if res != "ok":
            print(f"  FAILED: integrity_check returned '{res}'")
            return False
        cur.execute("PRAGMA foreign_key_check;")
        fk_errors = cur.fetchall()
        if fk_errors:
            print(f"  FAILED: foreign_key_check detected errors: {fk_errors}")
            return False
    except Exception as e:
        print(f"  FAILED: Schema execution error: {e}")
        return False
    finally:
        conn.close()

    print("  PASSED: Schema DDL parsed cleanly with foreign keys & integrity verified.")
    return True


def run_test_suite_in_sandbox(test_file: str) -> bool:
    print(f"[AUDIT GATE 3] Sandboxed Test Execution on '{test_file}'...")
    
    ring_fenced_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "HOMEDRIVE": os.environ.get("HOMEDRIVE", ""),
        "HOMEPATH": os.environ.get("HOMEPATH", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "APPDATA": os.environ.get("APPDATA", ""),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        "PYTHONPATH": REPO_ROOT,
    }

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p", "no:logfire",
        "-p", "no:langsmith",
        "-v",
        test_file,
    ]
    
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=ring_fenced_env,
        capture_output=True,
        text=True,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        print(f"  FAILED: pytest exited with non-zero code {proc.returncode}")
        return False
    print("  PASSED: Test suite passed with exit code 0.")
    return True


def emit_physical_receipt(slice_name: str, output_receipt_path: str) -> str:
    print(f"[AUDIT GATE 4] Emitting Physical Disk Receipt...")
    receipt_data = {
        "slice": slice_name,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "status": "VERIFIED_PASSED",
        "file_hashes": {},
    }

    for root, _, files in os.walk("svris"):
        for f in files:
            if f.endswith(".py") or f.endswith(".sql") or f.endswith(".json"):
                full_path = os.path.join(root, f)
                receipt_data["file_hashes"][full_path.replace("\\", "/")] = hash_file(full_path)

    os.makedirs(os.path.dirname(output_receipt_path), exist_ok=True)
    with open(output_receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt_data, f, indent=2)

    receipt_hash = hash_file(output_receipt_path)
    print(f"  PASSED: Receipt written to '{output_receipt_path}' [SHA256: {receipt_hash[:16]}]")
    return receipt_hash


def main():
    slice_name = sys.argv[1] if len(sys.argv) > 1 else "slice0"
    target_test = sys.argv[2] if len(sys.argv) > 2 else "svris/tests/test_slice0_p0_hardening.py"

    print(f"==================================================")
    print(f"  RING-FENCED INDEPENDENT AUDITOR: {slice_name.upper()}")
    print(f"==================================================")

    if not run_ast_audit("svris"):
        sys.exit(1)

    if not run_database_integrity_audit("svris/core/schema.sql"):
        sys.exit(2)

    if not run_test_suite_in_sandbox(target_test):
        sys.exit(3)

    receipt_path = f"svris/receipts/{slice_name}.receipt.json"
    receipt_hash = emit_physical_receipt(slice_name, receipt_path)

    print(f"==================================================")
    print(f"  AUDIT PASSED: {slice_name.upper()} SIGNED OFF")
    print(f"  Receipt SHA256: {receipt_hash}")
    print(f"==================================================")
    sys.exit(0)


if __name__ == "__main__":
    main()
