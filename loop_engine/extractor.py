import re
from pathlib import Path


def strip_markdown_fences(raw_text: str) -> str:
    """
    Deterministically strips markdown code fences (```python ... ``` or ``` ... ```)
    from raw LLM output. Returns raw content.
    """
    if not isinstance(raw_text, str):
        return ""

    text = raw_text.strip()
    # Match markdown code fences: ```python\n<code>\n``` or ```\n<code>\n```
    fence_pattern = re.compile(r"^```(?:[a-zA-Z0-9_\-\+\.]+)?\r?\n([\s\S]*?)\r?\n```$", re.MULTILINE)
    match = fence_pattern.search(text)
    if match:
        return match.group(1).strip()

    # If entire text is enclosed in triple backticks without newline
    if text.startswith("```") and text.endswith("```"):
        inner = text[3:-3].strip()
        # strip leading language tag if single-word prefix
        lines = inner.splitlines()
        if lines and re.match(r"^[a-zA-Z0-9_\-\+\.]+$", lines[0]):
            return "\n".join(lines[1:]).strip()
        return inner

    return text


def safe_extract_target(filename: str, staging_dir: Path) -> Path:
    """
    Ensures that a specified target filename resolves strictly within the staging directory,
    preventing directory traversal attacks (e.g. '../../target.py' or 'C:\\...').
    """
    staging_resolved = staging_dir.resolve()
    # Use only the basename to strictly prevent any traversal characters
    safe_name = Path(filename).name
    if not safe_name:
        safe_name = "candidate_output.txt"

    target_path = (staging_dir / safe_name).resolve()

    # Invariant: Target must reside within staging_dir
    try:
        target_path.relative_to(staging_resolved)
    except ValueError:
        raise ValueError(f"Security Violation: Target path '{filename}' escapes staging boundary '{staging_resolved}'.")

    return target_path
