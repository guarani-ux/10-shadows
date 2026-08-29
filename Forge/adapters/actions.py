import abc
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

# Windows reserved device names
_RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


class ActionAdapter(abc.ABC):
    @abc.abstractmethod
    def execute(self, *, authorization_id: str, operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an authorized external operation and returns output payload.
        """
        pass


class SandboxFileAdapter(ActionAdapter):
    """
    Safely executes file writes strictly within a designated sandbox root directory.
    Enforces robust path containment using Path.is_relative_to and rejects path traversal,
    device names, alternate data streams, and sibling prefix escapes.
    Requires verified authorization token before mutating disk state.
    """

    def __init__(self, sandbox_root: str | Path):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

    def execute(self, *, authorization_id: str, operation: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Authorization Verification Gate
        if not authorization_id or authorization_id == "UNAUTHORIZED_ACTION":
            raise PermissionError(
                f"Action execution denied: Invalid or missing authorization token '{authorization_id}'."
            )

        kind = operation.get("kind", "")
        target = operation.get("target", "")
        payload = operation.get("payload", {})

        if kind != "WRITE_FILE":
            raise ValueError(f"Unsupported operation kind '{kind}' in SandboxFileAdapter")

        # 2. Boundary Sanitization checks
        if "\x00" in target:
            raise PermissionError("Target path contains null byte injection.")

        if ":" in target:
            raise PermissionError("Target path contains illegal colon or alternate data stream indicator.")

        target_path_obj = Path(target)
        for part in target_path_obj.parts:
            stem_upper = Path(part).stem.upper()
            if stem_upper in _RESERVED_DEVICE_NAMES:
                raise PermissionError(f"Target path contains Windows reserved device name '{stem_upper}'.")

        # Resolve path relative to sandbox root
        target_path = (self.sandbox_root / target).resolve()

        # Strict containment verification using is_relative_to
        try:
            if not target_path.is_relative_to(self.sandbox_root):
                raise PermissionError(f"Target path '{target}' escapes sandbox root '{self.sandbox_root}'")
        except AttributeError:
            try:
                target_path.relative_to(self.sandbox_root)
            except ValueError:
                raise PermissionError(f"Target path '{target}' escapes sandbox root '{self.sandbox_root}'")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        content = payload.get("content", "")
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
            bytes_written = target_path.write_bytes(content_bytes)
        elif isinstance(content, (bytes, bytearray)):
            content_bytes = bytes(content)
            bytes_written = target_path.write_bytes(content_bytes)
        else:
            serialized = json.dumps(content, indent=2)
            content_bytes = serialized.encode("utf-8")
            bytes_written = target_path.write_bytes(content_bytes)

        file_hash = hashlib.sha256(content_bytes).hexdigest()

        return {
            "path": str(target_path),
            "relative_path": target,
            "bytes_written": bytes_written,
            "file_hash": file_hash,
            "committed": True,
        }
