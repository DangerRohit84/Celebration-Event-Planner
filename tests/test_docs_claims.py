"""Documentation-claim tests.

Every claim a reviewer can check is checked here: the file paths quoted in
the README and the docs must exist, the environment variables must be the
ones the code actually reads, and the test count quoted in the prose must
be the number of tests the suite really collects.

A number written in prose that a command can produce is a testable
assertion about the code - so it is tested.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
NARRATIVE = ROOT / "docs" / "NARRATIVE.md"
DEPLOYMENT = ROOT / "docs" / "DEPLOYMENT.md"
VIDEO_SCRIPT = ROOT / "docs" / "VIDEO_SCRIPT.md"
DOCS = (README, NARRATIVE, DEPLOYMENT, VIDEO_SCRIPT)

# Paths that are produced at runtime rather than tracked in the repository.
RUNTIME_ONLY = {"data/events.db", "data/", ".env"}

# Host-specific files a deployment guide may mention but the repo does not ship.
OPTIONAL_FILES = {"vercel.json"}

# Backticked tokens that look like a repository path.
PATH_TOKEN = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-][A-Za-z0-9_./-]*")

PATH_EXTENSIONS = (
    ".py",
    ".json",
    ".toml",
    ".txt",
    ".md",
    ".js",
    ".css",
    ".html",
    ".yml",
    ".yaml",
    ".cfg",
    ".ini",
    ".example",
)

# Directories a bare filename may live in.
SEARCH_DIRS = ("", "tests", "backend/app", "backend/app/llm", "docs", "frontend")


def _collected_test_count() -> int:
    """Return the number of tests pytest really collects.

    Returns:
        The collected test count.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    match = re.search(r"(\d+) tests? collected", completed.stdout)
    assert match, f"could not read the collected test count:\n{completed.stdout}"
    return int(match.group(1))


def _quoted_paths(document: Path) -> set[str]:
    """Return the repository paths quoted in a markdown document.

    Args:
        document: The markdown file to scan.

    Returns:
        The distinct path-like tokens quoted with backticks.
    """
    text = document.read_text(encoding="utf-8")
    found: set[str] = set()
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip()
        if not token or "{" in token or " " in token:
            continue
        if token.startswith("/"):
            # A URL path such as /openapi.json, not a repository file.
            continue
        if token.endswith("/") and "/" in token:
            found.add(token)
            continue
        if token.endswith(PATH_EXTENSIONS) or token in {"Dockerfile", "pyproject.toml"}:
            found.add(token)
    return found


def _resolve(path: str) -> bool:
    """Report whether a documented path exists in the repository.

    Args:
        path: The documented path.

    Returns:
        True when the path (or the same file name inside a known source
        directory) exists.
    """
    if path in OPTIONAL_FILES:
        return True
    if (ROOT / path.rstrip("/")).exists():
        return True
    if "/" not in path:
        for folder in SEARCH_DIRS:
            candidate = ROOT / folder / path if folder else ROOT / path
            if candidate.exists():
                return True
    return False


def test_every_documented_path_exists() -> None:
    """Every file path quoted in the documentation must exist on disk."""
    missing: list[str] = []
    for document in DOCS:
        for path in sorted(_quoted_paths(document)):
            if path in RUNTIME_ONLY:
                continue
            if not _resolve(path):
                missing.append(f"{document.name}: {path}")
    assert not missing, f"documented paths that do not exist: {missing}"


def test_readme_lists_every_backend_module() -> None:
    """The project-layout map must not omit a shipped module."""
    readme = README.read_text(encoding="utf-8")
    missing = [
        path.name
        for path in sorted((ROOT / "backend" / "app").rglob("*.py"))
        if path.name != "__init__.py" and path.name not in readme
    ]
    assert not missing, f"backend modules missing from README.md: {missing}"


def test_readme_lists_every_test_module() -> None:
    """Every test module must be accounted for in the README."""
    readme = README.read_text(encoding="utf-8")
    missing = [
        path.name
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name not in readme
    ]
    assert not missing, f"test modules missing from README.md: {missing}"


def test_corpus_path_in_readme_is_correct() -> None:
    """The corpus path quoted in the README must be the real one."""
    text = README.read_text(encoding="utf-8")
    assert "backend/data/ideas_corpus.json" in text
    assert "backend/app/data/ideas_corpus.json" not in text
    assert (ROOT / "backend" / "data" / "ideas_corpus.json").exists()


def test_documented_env_vars_are_read_by_the_code() -> None:
    """Every environment variable in the deployment table must be real."""
    config_source = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    table = DEPLOYMENT.read_text(encoding="utf-8")
    quoted = set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", table))
    quoted.discard("MAX_STORE_EVENTS")
    unknown = sorted(name for name in quoted if f'"{name}"' not in config_source)
    assert not unknown, f"documented env vars that config.py never reads: {unknown}"


def test_every_config_env_var_is_documented() -> None:
    """Every environment variable the code reads must appear in the docs."""
    config_source = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    table = DEPLOYMENT.read_text(encoding="utf-8")
    read = set(re.findall(r'os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"', config_source))
    read |= set(re.findall(r'_int\(\s*"([A-Z][A-Z0-9_]+)"', config_source))
    undocumented = sorted(name for name in read if f"`{name}`" not in table)
    assert not undocumented, f"env vars missing from DEPLOYMENT.md: {undocumented}"


def test_quoted_test_count_is_the_real_one() -> None:
    """The test count in the prose must match what pytest collects."""
    actual = _collected_test_count()
    readme = README.read_text(encoding="utf-8")
    narrative = NARRATIVE.read_text(encoding="utf-8")
    assert f"{actual} tests" in readme, f"README does not say '{actual} tests'"
    assert f"{actual} green" in readme, f"README does not say '{actual} green'"
    assert f"{actual} green tests" in narrative, (
        f"NARRATIVE does not say '{actual} green tests'"
    )
    # No stale counts may survive anywhere in the docs.
    stale = {
        count
        for count in re.findall(r"\b(\d{2,3}) (?:green )?tests\b", readme + narrative)
        if int(count) != actual
    }
    assert not stale, f"stale test counts in the documentation: {sorted(stale)}"


def test_quoted_coverage_gate_matches_the_configured_floor() -> None:
    """The coverage gate quoted in the README must be the enforced floor."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"fail_under\s*=\s*([0-9]+)", pyproject)
    assert match
    floor = match.group(1)
    readme = README.read_text(encoding="utf-8").replace("≥", ">=")
    assert f"TOTAL >= {floor}%" in readme


def test_plain_language_toggle_is_documented_and_real() -> None:
    """The toggle is marketed in the docs, so every link must exist."""
    readme = README.read_text(encoding="utf-8")
    assert "plain-language toggle" in readme
    assert "plain_language" in readme
    assert 'id="plain"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    schemas = (ROOT / "backend" / "app" / "schemas.py").read_text(encoding="utf-8")
    assert "plain_language" in schemas


def test_no_stale_project_paths_in_the_docs() -> None:
    """Guard against the specific drift the review found."""
    for document in DOCS:
        text = document.read_text(encoding="utf-8")
        assert "ALLOWED_ORIGINS" not in text, f"{document.name} mentions a fake env var"
        assert "doc_ids" not in text, f"{document.name} mentions a removed symbol"
        assert "DEMO_MODE" not in text, f"{document.name} mentions a removed setting"


# --------------------------------------------------------------------------
# Behavioural claims: the docs promise behaviour, so the behaviour is pinned
# here. A claim that has a test behind it cannot drift.
# --------------------------------------------------------------------------


def test_the_quoted_disclaimer_matches_the_code() -> None:
    """The docs must quote the disclaimer exactly as the code defines it."""
    from backend.app.prompting import DISCLAIMER

    for document in (README, NARRATIVE):
        assert DISCLAIMER in document.read_text(encoding="utf-8"), (
            f"{document.name} does not quote the disclaimer verbatim"
        )


def test_the_banner_carries_the_same_disclaimer() -> None:
    """Every surface must show the same disclaimer text."""
    from backend.app.prompting import DISCLAIMER

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert DISCLAIMER in html


def test_the_prompt_carries_the_disclaimer() -> None:
    """The prompt is a disclaimer surface, so it must contain the text."""
    from backend.app.prompting import DISCLAIMER, build_ideas_prompt

    prompt = build_ideas_prompt("ideas", [{"id": "w1", "text": "garden"}], "wedding")
    assert DISCLAIMER in prompt


def test_max_documents_is_read_by_the_application() -> None:
    """A documented setting that nothing reads is a dead knob."""
    readers = [
        path
        for path in (ROOT / "backend" / "app").rglob("*.py")
        if path.name != "config.py" and "max_documents" in path.read_text(encoding="utf-8")
    ]
    assert readers, "MAX_DOCUMENTS is parsed but never used by the application"


def test_every_provider_pins_temperature_zero() -> None:
    """The "temperature 0" claim must hold for every remote provider."""
    for module in ("gemini.py", "openai_compat.py"):
        source = (ROOT / "backend" / "app" / "llm" / module).read_text(encoding="utf-8")
        assert "temperature" in source, f"{module} does not set a temperature"
        pins_zero = re.search(r"temperature[\"']?\s*[:=]\s*0\b", source) or (
            re.search(r"TEMPERATURE\s*=\s*0\b", source)
        )
        assert pins_zero, f"{module} does not pin the temperature to 0"


def test_the_plain_rendering_is_shorter_than_the_standard_one() -> None:
    """The "shorter answer" claim must hold on the shipped echo provider."""
    from backend.app.llm.base import EchoProvider
    from backend.app.prompting import build_ideas_prompt

    hits = [{"id": "w1", "text": "Outdoor garden ceremony with string lights."}]
    prompt = build_ideas_prompt("outdoor ceremony", hits, "wedding")
    standard = EchoProvider().answer(prompt)
    plain = EchoProvider().answer(prompt, plain_language=True)
    assert len(plain) < len(standard)
