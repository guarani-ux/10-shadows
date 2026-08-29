import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from loop_engine.base import PROJECT_ROOT, BaseLoop
from loop_engine.extractor import safe_extract_target, strip_markdown_fences


# -------------------------------------------------------------
# 1. TEST MARKDOWN STRIPPER & PATH SECURITY
# -------------------------------------------------------------
def test_strip_markdown_fences():
    # Standard python fence
    fenced_py = "```python\ndef foo():\n    return 42\n```"
    assert strip_markdown_fences(fenced_py) == "def foo():\n    return 42"

    # Generic fence
    fenced_generic = "```\nhello world\n```"
    assert strip_markdown_fences(fenced_generic) == "hello world"

    # Raw unfenced string
    raw_str = "print('hello')"
    assert strip_markdown_fences(raw_str) == "print('hello')"


def test_safe_extract_target(tmp_path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    # Valid relative filename
    target = safe_extract_target("valid_script.py", staging_dir)
    assert target == (staging_dir / "valid_script.py").resolve()

    # Path traversal attack should be neutralized (only basename used)
    traversal_target = safe_extract_target("../../etc/passwd", staging_dir)
    assert traversal_target == (staging_dir / "passwd").resolve()
    assert str(traversal_target).startswith(str(staging_dir.resolve()))


# -------------------------------------------------------------
# 2. CONCRETE MOCK IMPLEMENTATION OF BASELOOP (SLICE 1)
# -------------------------------------------------------------
class HollowTestLoop(BaseLoop):
    def __init__(self, should_pass: bool = True, output_dest: Optional[Path] = None):
        super().__init__(name="HollowTestLoop")
        self.should_pass = should_pass
        self.output_dest = output_dest

    def normalize(self, raw_input: Any) -> Dict[str, Any]:
        return {
            "task_id": "test_hollow_01",
            "content": strip_markdown_fences(str(raw_input)),
        }

    def execute_staging(
        self,
        task_spec: Dict[str, Any],
        staging_dir: Path,
        feedback: Optional[str] = None,
    ) -> Path:
        candidate_file = staging_dir / "candidate.txt"
        with open(candidate_file, "w", encoding="utf-8") as f:
            f.write(task_spec["content"])
        return candidate_file

    def verify(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Tuple[bool, str]:
        if not self.should_pass:
            return False, "Simulated verification failure"
        return True, ""

    def commit(
        self,
        candidate_path: Path,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        target = self.output_dest or (PROJECT_ROOT / "scratch" / "hollow_out.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace from staging to destination
        os.replace(candidate_path, target)
        return {
            "target_file": str(target.as_posix()),
            "bytes_written": target.stat().st_size,
        }


# -------------------------------------------------------------
# 3. TEST HOLLOW PIPE EXECUTION LIFECYCLE
# -------------------------------------------------------------
def test_hollow_pipe_success(tmp_path):
    dest_file = tmp_path / "final_output.txt"
    loop = HollowTestLoop(should_pass=True, output_dest=dest_file)

    input_payload = "```text\nSovereign Hollow Pipe Payload\n```"
    result = loop.run(input_payload)

    assert result["status"] == "SUCCESS"
    assert result["task_id"] == "test_hollow_01"
    assert dest_file.exists()
    assert dest_file.read_text(encoding="utf-8") == "Sovereign Hollow Pipe Payload"


def test_hollow_pipe_verification_failure(tmp_path):
    dest_file = tmp_path / "should_not_exist.txt"
    loop = HollowTestLoop(should_pass=False, output_dest=dest_file)

    result = loop.run("Fail payload")

    assert result["status"] == "FAILED"
    assert "Simulated verification failure" in result["error"]
    assert not dest_file.exists()
