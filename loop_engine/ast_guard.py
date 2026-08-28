"""
loop_engine/ast_guard.py
AST Static Anti-Cheat & Security Inspector for 10 SHADOWS.

Deep Module enforcing static AST inspection on candidate Python source code
prior to sterile subprocess test execution. Detects and rejects:
1. Dynamic code evaluation (eval, exec, compile).
2. Dynamic module loading (__import__, dynamic importlib bypassing).
3. Global namespace manipulation (globals().clear(), globals().update(), locals().update()).
4. Test harness and runtime monkey-patching (sys.modules mutation, pytest hooks tampering).
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
from typing import List, Optional, Set


class ASTViolationType(str, Enum):
    DYNAMIC_EVAL = "DYNAMIC_EVAL"
    DYNAMIC_EXEC = "DYNAMIC_EXEC"
    DYNAMIC_COMPILE = "DYNAMIC_COMPILE"
    DYNAMIC_IMPORT = "DYNAMIC_IMPORT"
    GLOBAL_MUTATION = "GLOBAL_MUTATION"
    HARNESS_TAMPERING = "HARNESS_TAMPERING"
    SYNTAX_ERROR = "SYNTAX_ERROR"


@dataclass
class ASTFinding:
    filename: str
    line_number: int
    violation_type: ASTViolationType
    rule_id: str
    details: str

    def render(self) -> str:
        return f"[{self.violation_type.value}:{self.rule_id}] {self.filename}:{self.line_number} — {self.details}"


@dataclass
class ASTAuditResult:
    is_clean: bool
    findings: List[ASTFinding] = field(default_factory=list)
    file_count: int = 1


class SecurityASTVisitor(ast.NodeVisitor):
    """
    Adversarial AST Visitor detecting dangerous execution evasion and tampering patterns.
    """

    BANNED_CALL_NAMES = {
        "eval": (ASTViolationType.DYNAMIC_EVAL, "AST-SEC-001", "Direct invocation of eval() is strictly forbidden."),
        "exec": (ASTViolationType.DYNAMIC_EXEC, "AST-SEC-002", "Direct invocation of exec() is strictly forbidden."),
        "compile": (ASTViolationType.DYNAMIC_COMPILE, "AST-SEC-003", "Dynamic compilation via compile() is forbidden."),
        "__import__": (ASTViolationType.DYNAMIC_IMPORT, "AST-SEC-004", "Dynamic import via __import__() is forbidden."),
    }

    def __init__(self, filename: str):
        self.filename = filename
        self.findings: List[ASTFinding] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct function calls: eval(), exec(), compile(), __import__()
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.BANNED_CALL_NAMES:
                vtype, rule, msg = self.BANNED_CALL_NAMES[func_name]
                self.findings.append(
                    ASTFinding(
                        filename=self.filename,
                        line_number=node.lineno,
                        violation_type=vtype,
                        rule_id=rule,
                        details=msg,
                    )
                )

        # Check method calls on globals() / locals(): globals().clear(), globals().update()
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if isinstance(node.func.value, ast.Call) and isinstance(node.func.value.func, ast.Name):
                inner_name = node.func.value.func.id
                if inner_name in ("globals", "locals") and attr_name in ("clear", "update", "pop", "setdefault"):
                    self.findings.append(
                        ASTFinding(
                            filename=self.filename,
                            line_number=node.lineno,
                            violation_type=ASTViolationType.GLOBAL_MUTATION,
                            rule_id="AST-SEC-005",
                            details=f"Namespace mutation via {inner_name}().{attr_name}() is strictly forbidden.",
                        )
                    )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Check mutations targeting sys.modules (e.g., sys.modules['pytest'] = ...)
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                if isinstance(target.value, ast.Attribute):
                    if isinstance(target.value.value, ast.Name) and target.value.value.id == "sys":
                        if target.value.attr == "modules":
                            self.findings.append(
                                ASTFinding(
                                    filename=self.filename,
                                    line_number=node.lineno,
                                    violation_type=ASTViolationType.HARNESS_TAMPERING,
                                    rule_id="AST-SEC-006",
                                    details="Mutation of sys.modules is strictly forbidden.",
                                )
                            )
            elif isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name) and target.value.id in ("pytest", "_pytest"):
                    self.findings.append(
                        ASTFinding(
                            filename=self.filename,
                            line_number=node.lineno,
                            violation_type=ASTViolationType.HARNESS_TAMPERING,
                            rule_id="AST-SEC-007",
                            details=f"Direct monkey-patching of {target.value.id}.{target.attr} is forbidden.",
                        )
                    )
        self.generic_visit(node)


def scan_ast(source_text: str, filename: str = "<string>") -> ASTAuditResult:
    """
    Parses and scans Python source code against static anti-cheat security invariants.
    """
    try:
        tree = ast.parse(source_text, filename=filename)
    except SyntaxError as e:
        finding = ASTFinding(
            filename=filename,
            line_number=e.lineno or 1,
            violation_type=ASTViolationType.SYNTAX_ERROR,
            rule_id="AST-SEC-000",
            details=f"Python syntax error: {str(e)}",
        )
        return ASTAuditResult(is_clean=False, findings=[finding], file_count=1)

    visitor = SecurityASTVisitor(filename=filename)
    visitor.visit(tree)

    return ASTAuditResult(
        is_clean=(len(visitor.findings) == 0),
        findings=visitor.findings,
        file_count=1,
    )


def scan_python_file(file_path: Path) -> ASTAuditResult:
    """
    Scans a single Python file on disk.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        return scan_ast(content, filename=str(file_path))
    except Exception as e:
        finding = ASTFinding(
            filename=str(file_path),
            line_number=1,
            violation_type=ASTViolationType.SYNTAX_ERROR,
            rule_id="AST-SEC-000",
            details=f"Unreadable file error: {str(e)}",
        )
        return ASTAuditResult(is_clean=False, findings=[finding], file_count=1)


def scan_python_worktree(worktree_path: Path) -> List[ASTFinding]:
    """
    Recursively scans all Python source files in a worktree, skipping .git, .pytest_cache, and venvs.
    Returns all detected ASTFindings.
    """
    all_findings: List[ASTFinding] = []
    resolved_wt = worktree_path.resolve()

    if not resolved_wt.exists():
        return all_findings

    ignored_dirs = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "env", "node_modules"}

    for root, dirs, files in os.walk(resolved_wt):
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".tmp")]

        for file_name in files:
            if file_name.endswith(".py"):
                file_path = Path(root) / file_name
                result = scan_python_file(file_path)
                if not result.is_clean:
                    all_findings.extend(result.findings)

    return all_findings
