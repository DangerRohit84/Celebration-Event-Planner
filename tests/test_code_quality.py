"""Code quality tests."""
from pathlib import Path
import re

BACKEND = list((Path("backend/app")).rglob("*.py"))


def test_no_todo_in_app():
    bad = []
    for p in BACKEND + [Path("frontend/app.js")]:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for marker in ("TODO", "FIXME", "HACK"):
            if marker in text:
                bad.append(f"{p}:{marker}")
    assert not bad, f"markers found: {bad}"


def test_no_hardcoded_secrets():
    for p in BACKEND:
        text = p.read_text(encoding="utf-8")
        for pat in (r"AIza[A-Za-z0-9_-]{10,}", r"sk-[A-Za-z0-9]{10,}", r"AKIA[0-9A-Z]{10,}"):
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
