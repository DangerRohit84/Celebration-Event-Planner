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

The ``# noqa:`` scan below reads *code tokens*, not raw text. Only
``COMMENT`` tokens are inspected, so a directive mentioned inside a
docstring or a string literal - such as the example in this module's own
docstrings - is never mistaken for a real suppression.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
GATE_SCRIPT = ROOT / "scripts" / "check_quality.py"

NOQA_PATTERN = re.compile(r"#\s*noqa:\s*([A-Z]+[0-9]+)")

# The real suppressions in the tree, file by file. Pinning the whole
# inventory keeps the scan honest in both directions: a directive that has
# disappeared is a failure, and a directive that only exists inside a
# docstring is a failure too. Every code listed here is enabled by the ruff
# configuration and none of them is in the global ignore list.
EXPECTED_NOQA_SITES = {
    "backend/app/ingest.py": {"BLE001": 2},
    "backend/app/llm/factory.py": {"BLE001": 2},
    "backend/app/main.py": {"BLE001": 1},
    "backend/app/models.py": {"UP017": 2},
    "backend/app/retrieval.py": {"BLE001": 3},
    "backend/app/routes.py": {"UP017": 1, "BLE001": 2, "B008": 1},
    "backend/app/security.py": {"D418": 2},
    "tests/test_code_quality.py": {"BLE001": 1},
    "tests/test_docs_claims.py": {"S603": 1},
    "tests/test_quality_gates.py": {"S603": 2},
}


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


def _noqa_sites_in_file(path: Path) -> dict[str, int]:
    """Return the ``# noqa:`` codes present in the *code* of one file.

    The file is tokenised and only ``COMMENT`` tokens are inspected, so a
    directive quoted inside a docstring or a string literal is ignored.

    Args:
        path: The Python file to scan.

    Returns:
        A mapping of noqa code to the number of real directives found.
    """
    counts: dict[str, int] = {}
    try:
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type != tokenize.COMMENT:
                    continue
                for match in NOQA_PATTERN.finditer(token.string):
                    code = match.group(1)
                    counts[code] = counts.get(code, 0) + 1
    except (OSError, SyntaxError, UnicodeDecodeError, tokenize.TokenError):
        return {}
    return counts


def _noqa_sites_in_tree() -> dict[str, dict[str, int]]:
    """Return the ``# noqa:`` inventory of the whole tree.

    Returns:
        A mapping of repository-relative file path to the noqa codes found
        in that file's real code.
    """
    sites: dict[str, dict[str, int]] = {}
    for folder in ("backend", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            counts = _noqa_sites_in_file(path)
            if counts:
                sites[path.relative_to(ROOT).as_posix()] = counts
    return sites


def _noqa_codes_in_tree() -> set[str]:
    """Return every ``# noqa:`` code used in real code across the tree.

    Returns:
        The distinct noqa codes found in ``backend/`` and ``tests/``.
    """
    codes: set[str] = set()
    for counts in _noqa_sites_in_tree().values():
        codes |= set(counts)
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


def test_noqa_scan_finds_exactly_the_real_directives() -> None:
    """The scan must see the real directives and nothing else.

    The per-file inventory is pinned so that the scan cannot silently
    become vacuous (finding nothing), cannot miss a directive, and cannot
    count a directive that only appears inside a docstring.
    """
    found = _noqa_sites_in_tree()
    assert found == EXPECTED_NOQA_SITES, (
        "the noqa inventory changed: "
        f"found={found} expected={EXPECTED_NOQA_SITES}"
    )


def test_noqa_scan_ignores_docstrings_and_string_literals() -> None:
    """A ``# noqa:`` quoted in a docstring is not a real directive.

    This module's own docstrings quote a ``B008`` directive as an example.
    The scan must not count it; the only real directives in this file are
    the two ``S603`` suppressions on the subprocess calls.
    """
    counts = _noqa_sites_in_file(Path(__file__))
    assert "B008" not in counts, (
        "the docstring example was counted as a real directive: "
        f"{counts}"
    )
    assert counts == {"S603": 2}, f"unexpected noqa codes in this file: {counts}"


def test_noqa_scan_ignores_docstring_examples_in_a_synthetic_file(
    tmp_path: Path,
) -> None:
    """A synthetic file proves the scan ignores examples inside strings."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""Module docstring mentioning # noqa: B008 as an example."""\n'
        "\n"
        "TEXT = 'a string literal with # noqa: S603 inside it'\n"
        "\n"
        "\n"
        "def f():\n"
        '    """Function docstring mentioning # noqa: D418."""\n'
        "    return 1  # noqa: S101\n",
        encoding="utf-8",
    )
    counts = _noqa_sites_in_file(sample)
    assert counts == {"S101": 1}, (
        f"the scan counted docstring or string examples: {counts}"
    )


def test_every_noqa_code_is_an_enabled_rule() -> None:
    """A ``# noqa:`` directive is only meaningful if its rule is enabled."""
    selected = _ruff_select_codes()
    found = _noqa_codes_in_tree()
    unknown = {code for code in found if not _matches(code, selected)}
    assert not unknown, f"noqa codes for disabled rules: {sorted(unknown)}"
    assert found, "the noqa scan found nothing; it cannot prove anything"


def test_no_noqa_code_suppresses_an_ignored_rule() -> None:
    """A noqa naming an ignored rule is inert and must not exist."""
    ignored = _ruff_ignore_codes()
    found = _noqa_codes_in_tree()
    inert = {code for code in found if _matches(code, ignored)}
    assert not inert, f"noqa codes that suppress an ignored rule: {sorted(inert)}"
    assert found, "the noqa scan found nothing; it cannot prove anything"


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
