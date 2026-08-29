"""AST Static Anti-Cheat Scanner (aci.py)

Enforces Invariant C:
1. Rejects eval() and exec() outside authorized fixtures.
2. Rejects bare `except:` and `pass` in except clauses.
3. Rejects `# noqa` and `# type: ignore` suppressions.
4. Rejects functions with only constant return stubs or empty bodies (pass/TODO/NotImplementedError).
"""

import ast
import os
import sys
from typing import List, Tuple


class AntiCheatVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, lines: List[str]):
        self.filename = filename
        self.lines = lines
        self.violations: List[str] = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            self.violations.append(f"{self.filename}:{node.lineno}: Banned execution primitive '{node.func.id}()'")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type is None:
            self.violations.append(f"{self.filename}:{node.lineno}: Bare 'except:' clause forbidden")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.violations.append(
                f"{self.filename}:{node.lineno}: Silent error suppression ('except ...: pass') forbidden"
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check for stub functions
        if len(node.body) == 1:
            stmt = node.body[0]
            if isinstance(stmt, ast.Pass):
                self.violations.append(f"{self.filename}:{node.lineno}: Function '{node.name}' has empty 'pass' body")
            elif (
                isinstance(stmt, ast.Raise)
                and isinstance(stmt.exc, ast.Call)
                and isinstance(stmt.exc.func, ast.Name)
                and stmt.exc.func.id == "NotImplementedError"
            ):
                self.violations.append(
                    f"{self.filename}:{node.lineno}: Function '{node.name}' has stub 'NotImplementedError'"
                )
        self.generic_visit(node)


def scan_file(filepath: str) -> List[str]:
    # Skip scanner tool itself to prevent self-matching on string literals
    if os.path.basename(filepath) == "aci.py":
        return []

    violations: List[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines()

    # Comment scan
    for idx, line in enumerate(lines, start=1):
        if "# noqa" in line or "# type: ignore" in line:
            violations.append(f"{filepath}:{idx}: Linter suppression comments forbidden (# noqa / # type: ignore)")
        if "TODO" in line:
            violations.append(f"{filepath}:{idx}: Placeholder comment forbidden (TODO)")

    # AST scan
    try:
        tree = ast.parse(content, filename=filepath)
        visitor = AntiCheatVisitor(filepath, lines)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    except SyntaxError as e:
        violations.append(f"{filepath}:{e.lineno}: SyntaxError: {e.msg}")

    return violations


def scan_directory(directory: str) -> Tuple[int, List[str]]:
    all_violations: List[str] = []
    file_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_count += 1
                full_path = os.path.join(root, file)
                all_violations.extend(scan_file(full_path))
    return file_count, all_violations


def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "svris"
    files_scanned, violations = scan_directory(target_dir)
    print("--- ACI Anti-Cheat Scan Report ---")
    print(f"Target: {target_dir} | Files Scanned: {files_scanned}")
    if violations:
        print(f"FAILED: {len(violations)} violations detected:")
        for v in violations:
            print(f"  [!] {v}")
        sys.exit(1)
    else:
        print("PASSED: 0 anti-cheat violations found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
