import pathlib
import sys

root_dir = pathlib.Path(__file__).resolve().parent.parent.parent
root_script = root_dir / "scripts" / "verify_plan_audit.py"
sys.path.insert(0, str(root_dir))
if root_script.exists():
    exec(root_script.read_text(encoding="utf-8"))
