"""Code quality tests."""

import ast
import re
from pathlib import Path

BACKEND = list((Path("backend/app")).rglob("*.py"))


def test_no_todo_in_app():
    bad = []
    for p in BACKEND + [Path("frontend/app.js")]:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001, S112
            continue
        for marker in ("TODO", "FIXME", "HACK"):
            if marker in text:
                bad.append(f"{p}:{marker}")
    assert not bad, f"markers found: {bad}"


def test_no_hardcoded_secrets():
    for p in BACKEND:
        text = p.read_text(encoding="utf-8")
        for pat in (
            r"AIza[A-Za-z0-9_-]{10,}",
            r"sk-[A-Za-z0-9]{10,}",
            r"AKIA[0-9A-Z]{10,}",
        ):
            assert not re.search(pat, text), f"secret in {p}"


def test_modules_have_docstrings():
    for p in BACKEND:
        if p.name == "__init__.py":
            continue
        text = p.read_text(encoding="utf-8")
        assert text.lstrip().startswith('"""'), f"{p} missing docstring"


def test_main_size():
    lines = Path("backend/app/main.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 400


def test_no_prints():
    for p in BACKEND:
        text = p.read_text(encoding="utf-8")
        assert "print(" not in text, f"print in {p}"


def test_dip_port():
    base = Path("backend/app/llm/base.py").read_text(encoding="utf-8")
    assert "class LLMProvider" in base
    factory = Path("backend/app/llm/factory.py").read_text(encoding="utf-8")
    assert "def build_provider" in factory


def _iter_functions(tree):
    """Yield every function and method definition in a parsed module."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _docstring_sections(docstring):
    """Return the set of Google-style section names present in a docstring."""
    return {
        line.strip().rstrip(":")
        for line in docstring.splitlines()
        if line.strip().endswith(":")
    }


def _has_parameters(node):
    """Report whether a function declares a user-facing parameter.

    The implicit ``self``/``cls`` receiver is not a user-facing parameter, so
    it does not by itself require an ``Args:`` section.
    """
    args = node.args
    named = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    receivers = {"self", "cls"}
    named = [a for a in named if a.arg not in receivers]
    return bool(named or args.vararg or args.kwarg)


def _returns_value(node):
    """Report whether a function declares a non-None return type.

    ``__init__``/``__new__`` implicitly return None and therefore never need a
    ``Returns:`` section.
    """
    if node.name in {"__init__", "__new__"}:
        return False
    annotation = node.returns
    if annotation is None:
        return True
    return not (isinstance(annotation, ast.Constant) and annotation.value is None)


def _raises_explicitly(node):
    """Report whether a function body contains an explicit ``raise``."""
    return any(
        isinstance(child, ast.Raise) and child.exc is not None
        for child in ast.walk(node)
    )


def test_every_function_has_a_docstring():
    """Every function/method in backend/app must carry a docstring."""
    missing = []
    for path in BACKEND:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _iter_functions(tree):
            if ast.get_docstring(node) is None:
                missing.append(f"{path}:{node.lineno}:{node.name}")
    assert not missing, f"functions missing docstrings: {missing}"


def test_docstrings_follow_pep257_structure():
    """Docstrings must have a period-terminated summary plus Args/Returns/Raises."""
    problems = []
    for path in BACKEND:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in _iter_functions(tree):
            doc = ast.get_docstring(node)
            if doc is None:
                continue
            where = f"{path}:{node.lineno}:{node.name}"
            summary = doc.strip().splitlines()[0]
            if not summary.endswith("."):
                problems.append(f"{where} summary not period-terminated")
            sections = _docstring_sections(doc)
            if _has_parameters(node) and "Args" not in sections:
                problems.append(f"{where} missing Args section")
            if _returns_value(node) and "Returns" not in sections:
                problems.append(f"{where} missing Returns section")
            if _raises_explicitly(node) and "Raises" not in sections:
                problems.append(f"{where} missing Raises section")
    assert not problems, f"docstring structure problems: {problems}"
