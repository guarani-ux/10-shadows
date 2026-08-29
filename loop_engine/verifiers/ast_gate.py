import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ASTSecurityViolation(Exception):
    """Raised when an AST node contains prohibited or dangerous operations."""

    pass


class ASTSecurityVisitor(ast.NodeVisitor):
    """
    Static analysis AST visitor that detects and rejects dangerous dynamic execution,
    shell execution, dynamic imports, and network socket instantiations.
    """

    BANNED_CALL_NAMES = {
        "eval",
        "exec",
        "__import__",
        "compile",
    }

    BANNED_MODULES = {
        "socket",
        "pty",
        "shutil",  # when accessed via dynamic call
    }

    def __init__(self):
        self.violations: List[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        # 1. Direct function calls: eval(...), exec(...)
        if isinstance(node.func, ast.Name):
            if node.func.id in self.BANNED_CALL_NAMES:
                self.violations.append(f"Line {node.lineno}: Banned function call '{node.func.id}()'")

        # 2. Attribute calls: os.system(...), subprocess.Popen(...) without guard, importlib.import_module(...)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                mod_name = node.func.value.id
                attr_name = node.func.attr
                if mod_name == "os" and attr_name in {"system", "popen", "spawnl", "execv"}:
                    self.violations.append(f"Line {node.lineno}: Banned execution call '{mod_name}.{attr_name}()'")
                elif mod_name == "importlib" and attr_name in {"import_module", "__import__"}:
                    self.violations.append(f"Line {node.lineno}: Banned dynamic import '{mod_name}.{attr_name}()'")

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in {"socket", "telnetlib", "ftplib"}:
                self.violations.append(f"Line {node.lineno}: Banned network module import '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in {"socket", "telnetlib", "ftplib"}:
            self.violations.append(f"Line {node.lineno}: Banned network module import from '{node.module}'")
        self.generic_visit(node)


def validate_ast_security(source_code: str) -> Tuple[bool, List[str]]:
    """
    Parses source code into an AST and evaluates static security rules.
    Returns (is_secure: bool, violations: List[str]).
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return False, [f"SyntaxError on line {e.lineno}, col {e.offset}: {e.msg}"]

    visitor = ASTSecurityVisitor()
    visitor.visit(tree)

    if visitor.violations:
        return False, visitor.violations
    return True, []


def inspect_file_ast(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Reads a physical python file and validates its AST security properties.
    """
    if not file_path.exists():
        return False, [f"File '{file_path}' does not exist."]
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"Read error: {str(e)}"]

    return validate_ast_security(content)
