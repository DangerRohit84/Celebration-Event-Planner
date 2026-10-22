"""Quality-gate tests.

The README claims that lint, type, test and coverage gates are enforced.
These tests make sure the configuration that enforces them exists, that the
``# noqa:`` directives in the code map to rules that are actually enabled,
and that the coverage floor quoted in the documentation matches the one the
gate script reads.

A suppression is only meaningful when the rule it suppresses is enabled:
ruff applies ``ignore`` after ``select``, so a code that appears in the
``ignore`` list is off no matter what ``select`` says. These tests
therefore read the two lists separately instead of scraping the whole
``[tool.ruff.lint]`` block.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

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


def _ruff_code_list(option: str) -> set[str]:
    """Return the rule codes listed in one ruff lint option.

    Args:
        option: The name of the option to read, ``select`` or ``ignore``.

    Returns:
        The codes and rule families listed in that option.
    """
    text = _pyproject_text()
    block = re.search(
        r"^\[tool\.ruff\.lint\]\s*$(.*?)(?=^\[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert block, "pyproject.toml has no [tool.ruff.lint] section"
    match = re.search(
        rf"^{option}\s*=\s*\[(.*?)\]",
        block.group(1),
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"pyproject.toml has no ruff {option} list"
    return set(re.findall(r'"([A-Z]+[0-9]*)"', match.group(1)))


def _ruff_select_codes() -> set[str]:
    """Return the rule codes enabled by the ruff configuration.

    Returns:
        The selected codes and rule families.
    """
    return _ruff_code_list("select")


def _ruff_ignore_codes() -> set[str]:
    """Return the rule codes disabled by the ruff configuration.

    Returns:
        The ignored codes and rule families.
    """
    return _ruff_code_list("ignore")


def _matches(code: str, families: set[str]) -> bool:
    """Report whether a code belongs to one of the given rule families.

    Args:
        code: A single rule code, e.g. ``S110``.
        families: Rule codes or families, e.g. ``{"S", "D418"}``.

    Returns:
        True when the code is the family itself or a member of it.
    """
    return any(code == family or code.startswith(family) for family in families)


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
        code for code in _noqa_codes_in_tree() if not _matches(code, selected)
    }
    assert not unknown, f"noqa codes for disabled rules: {sorted(unknown)}"


def test_no_noqa_code_suppresses_an_ignored_rule() -> None:
    """A noqa naming an ignored rule is inert and must not exist."""
    ignored = _ruff_ignore_codes()
    inert = {
        code for code in _noqa_codes_in_tree() if _matches(code, ignored)
    }
    assert not inert, f"noqa codes that suppress an ignored rule: {sorted(inert)}"


def test_b008_rule_is_active_and_the_noqa_is_load_bearing() -> None:
    """The upload route's ``# noqa: B008`` must suppress a rule that fires."""
    fired = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--ignore-noqa",
            "--select",
            "B008",
            "backend",
            "tests",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    output = (fired.stdout or "") + (fired.stderr or "")
    if "No module named ruff" in output:
        pytest.skip("ruff is not installed in this environment")
    assert fired.returncode != 0, "B008 does not fire, so the noqa is inert"
    assert "B008" in output
    clean = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [sys.executable, "-m", "ruff", "check", "--no-cache", "backend", "tests"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr


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
