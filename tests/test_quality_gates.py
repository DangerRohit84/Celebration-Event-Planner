"""Quality-gate tests.

The README claims that lint, type, test and coverage gates are enforced.
These tests make sure the configuration that enforces them exists, that the
``# noqa:`` directives in the code map to rules that are actually enabled,
and that the coverage floor quoted in the documentation matches the one the
gate script reads.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
GATE_SCRIPT = ROOT / "scripts" / "check_quality.py"

NOQA_PATTERN = re.compile(r"#\s*noqa:\s*([A-Z]+[0-9]+)")


def _pyproject_text() -> str:
    """Return the project configuration file.

    Returns:
        The contents of ``pyproject.toml``.
    """
    return PYPROJECT.read_text(encoding="utf-8")


def _ruff_select_codes() -> set[str]:
    """Return the rule codes enabled by the ruff configuration.

    Returns:
        The selected codes and rule families.
    """
    text = _pyproject_text()
    block = re.search(
        r"^\[tool\.ruff\.lint\]\s*$(.*?)(?=^\[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert block, "pyproject.toml has no [tool.ruff.lint] section"
    return set(re.findall(r'"([A-Z]+[0-9]*)"', block.group(1)))


def _noqa_codes_in_tree() -> set[str]:
    """Return every ``# noqa:`` code used in the source tree.

    Returns:
        The distinct noqa codes found in ``backend/`` and ``tests/``.
    """
    codes: set[str] = set()
    for folder in ("backend", "tests"):
        for path in (ROOT / folder).rglob("*.py"):
            for match in NOQA_PATTERN.finditer(path.read_text(encoding="utf-8")):
                codes.add(match.group(1))
    return codes


def test_pyproject_declares_every_gate() -> None:
    """The project configuration must declare lint, type, test and coverage."""
    text = _pyproject_text()
    for section in (
        "[tool.pytest.ini_options]",
        "[tool.coverage.run]",
        "[tool.coverage.report]",
        "[tool.ruff]",
        "[tool.ruff.lint]",
        "[tool.mypy]",
    ):
        assert section in text, f"pyproject.toml is missing {section}"


def test_coverage_floor_is_declared() -> None:
    """A coverage floor must be declared so the gate can fail the build."""
    text = _pyproject_text()
    assert re.search(r"fail_under\s*=\s*[0-9]+", text)


def test_every_noqa_code_is_an_enabled_rule() -> None:
    """A ``# noqa:`` directive is only meaningful if its rule is enabled."""
    selected = _ruff_select_codes()
    unknown = {
        code
        for code in _noqa_codes_in_tree()
        if not any(code == sel or code.startswith(sel) for sel in selected)
    }
    assert not unknown, f"noqa codes for disabled rules: {sorted(unknown)}"


def test_quality_gate_script_exists_and_runs_every_gate() -> None:
    """The gate script must run ruff, mypy and pytest with coverage."""
    assert GATE_SCRIPT.exists(), "scripts/check_quality.py is missing"
    source = GATE_SCRIPT.read_text(encoding="utf-8")
    assert "ruff" in source
    assert "mypy" in source
    assert "pytest" in source
    assert "--cov" in source
    assert "fail_under" in source or "read_coverage_floor" in source


def test_gate_script_floor_matches_pyproject() -> None:
    """The floor baked into the script must match the configured floor."""
    assert GATE_SCRIPT.exists()
    source = GATE_SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        r"DEFAULT_COVERAGE_FLOOR\s*=\s*([0-9]+(?:\.[0-9]+)?)",
        source,
    )
    assert match, "scripts/check_quality.py has no DEFAULT_COVERAGE_FLOOR"
    configured = re.search(
        r"fail_under\s*=\s*([0-9]+(?:\.[0-9]+)?)",
        _pyproject_text(),
    )
    assert configured, "pyproject.toml has no fail_under"
    assert float(match.group(1)) == float(configured.group(1))


def test_ruff_line_length_is_declared() -> None:
    """The formatter width must be declared, not left to the default."""
    assert re.search(r"line-length\s*=\s*\d+", _pyproject_text())
