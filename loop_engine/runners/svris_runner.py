import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loop_engine.base import BaseLoop, PROJECT_ROOT
from loop_engine.receipts import ReceiptStore
from loop_engine.verifiers.ast_gate import inspect_file_ast, validate_ast_security


class SvrisDomainRunner(BaseLoop):
    """
    Shadow 2: svris Domain Runner (Verification & Custody Engine).
    Ingests artifacts, extracts AST properties, verifies contradiction/security invariants,
    and writes cryptographically sealed verification receipts.
    """

    def __init__(
        self,
        receipt_store: Optional[ReceiptStore] = None,
        max_strikes: int = 3,
    ):
        super().__init__(name="svrisDomainRunner", max_strikes=max_strikes)
        self.receipt_store = receipt_store or ReceiptStore()

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        """
        Normalizes verification request into a structured AuditSpec.
        """
        if isinstance(raw_input, dict):
            task_id = raw_input.get("task_id", f"svris_{uuid.uuid4().hex[:8]}")
            target_path = raw_input.get("target_path")
            content = raw_input.get("content", "")
            required_rules = raw_input.get("required_rules", ["ast_security"])
        else:
            task_id = f"svris_{uuid.uuid4().hex[:8]}"
            target_path = None
            content = str(raw_input)
            required_rules = ["ast_security"]

        return {
            "task_id": task_id,
            "target_path": str(target_path) if target_path else None,
            "content": content,
            "required_rules": required_rules,
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        """
        Extracts and stages artifact for audit.
        """
        candidate_path = staging_dir / "audit_candidate.py"
        if task_spec["target_path"] and Path(task_spec["target_path"]).exists():
            content = Path(task_spec["target_path"]).read_text(encoding="utf-8")
        else:
            content = task_spec["content"]

        candidate_path.write_text(content, encoding="utf-8")
        return candidate_path

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Runs comprehensive svris security & syntax gate.
        """
        passed, violations = inspect_file_ast(candidate_path)
        if not passed:
            return False, f"svris Invariant Failure: {'; '.join(violations)}"
        return True, ""

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Stamps verified audit receipt into SQLite WAL and emits sealed receipt JSON.
        """
        content = candidate_path.read_text(encoding="utf-8")
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

        receipt_id = self.receipt_store.record_receipt(
            task_id=task_spec["task_id"],
            run_id=f"run_{task_spec['task_id']}",
            spec_hash=content_sha[:16],
            status="VERIFIED",
            strikes_used=1,
            target_file=task_spec["target_path"] or "inline_content",
            artifact_sha256=content_sha,
            extra_data={"rules_checked": task_spec["required_rules"]},
        )

        receipt_data = {
            "receipt_id": receipt_id,
            "task_id": task_spec["task_id"],
            "status": "VERIFIED",
            "sha256": content_sha,
            "timestamp": str(Path(__file__).stat().st_mtime),
        }

        receipt_file = PROJECT_ROOT / "scratch" / f"svris_{task_spec['task_id']}.receipt.json"
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        receipt_file.write_text(json.dumps(receipt_data, indent=2), encoding="utf-8")

        return receipt_data
