#!/usr/bin/env python
"""Run the full quality gate for the Celebration & Event Planner.

Usage::

    python scripts/check_quality.py

The script exits with code 0 only when every gate passes:

1. ``ruff``    - no lint errors in ``backend/`` and ``tests/``.
2. ``mypy``    - no type errors in ``backend/app``.
3. ``pytest``  - the whole suite passes.
4. ``coverage`` - the TOTAL percentage reaches the ``fail_under`` floor
   declared in ``pyproject.toml`` under ``[tool.coverage.report]``.

The gates quoted in ``README.md`` are therefore enforced by a command, not
by prose. The configuration is read with a small regular-expression reader
so the script needs no third-party TOML parser and runs on Python 3.10.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

# The floor the coverage gate must reach. It mirrors the ``fail_under``
# value in pyproject.toml; the test suite asserts the two stay in sync.
DEFAULT_COVERAGE_FLOOR = 76.0

_RESULTS: list[tuple[str, bool, str]] = []


def read_coverage_floor(pyproject: Path = PYPROJECT) -> float:
    """Read the coverage floor declared in ``pyproject.toml``.

    Args:
        pyproject: Path of the project configuration file.

    Returns:
        The declared ``fail_under`` floor, or the built-in default when the
        file does not declare one.
    """
    if not pyproject.exists():
        return DEFAULT_COVERAGE_FLOOR
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*fail_under\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$",
        text,
        re.MULTILINE,
    )
    if not match:
        return DEFAULT_COVERAGE_FLOOR
    return float(match.group(1))


def run(step: str, command: list[str]) -> tuple[bool, str]:
    """Run one gate command and capture its output.

    Args:
        step: Human-readable name of the gate.
        command: The command line to execute.

    Returns:
        A ``(passed, output)`` pair.
    """
    printable = " ".join(command)
    print(f"\n=== {step}: {printable} ===", flush=True)
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    sys.stdout.write(output)
    passed = completed.returncode == 0
    _RESULTS.append((step, passed, printable))
    return passed, output


def parse_total_coverage(output: str) -> float | None:
    """Extract the TOTAL coverage percentage from a coverage report.

    Args:
        output: The captured output of the pytest coverage run.

    Returns:
        The TOTAL percentage, or None when the report has no TOTAL row.
    """
    match = re.search(
        r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%",
        output,
        re.MULTILINE,
    )
    if match:
        return float(match.group(1))
    match = re.search(r"^TOTAL\s+.*?(\d+(?:\.\d+)?)%", output, re.MULTILINE)
    return float(match.group(1)) if match else None


def main() -> int:
    """Run every quality gate and report the outcome.

    Returns:
        0 when every gate passes, 1 otherwise.
    """
    floor = read_coverage_floor()
    print(f"Quality gates: ruff, mypy, pytest, coverage >= {floor}%")

    lint_ok, _ = run("lint", [sys.executable, "-m", "ruff", "check", "backend", "tests"])
    types_ok, _ = run("types", [sys.executable, "-m", "mypy", "backend/app"])
    tests_ok, coverage_output = run(
        "tests + coverage",
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=backend",
            "--cov-report=term",
            "-q",
        ],
    )

    total = parse_total_coverage(coverage_output)
    coverage_ok = total is not None and total >= floor
    _RESULTS.append(
        (
            "coverage",
            coverage_ok,
            f"TOTAL {total:.1f}% >= {floor:.1f}%" if total is not None else "no TOTAL row",
        ),
    )

    print("\n=== summary ===")
    for step, passed, detail in _RESULTS:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {step}: {detail}")

    failed = [step for step, passed, _ in _RESULTS if not passed]
    if failed:
        print(f"\nQUALITY GATE FAILED: {', '.join(failed)}")
        return 1
    print("\nQUALITY GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
