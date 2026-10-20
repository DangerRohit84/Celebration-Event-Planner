"""Accessibility tests."""
from pathlib import Path
import re

HTML = Path("frontend/index.html").read_text(encoding="utf-8")
CSS = Path("frontend/styles.css").read_text(encoding="utf-8")
JS = Path("frontend/app.js").read_text(encoding="utf-8")


def test_html_lang_and_meta():
    assert 'lang="en"' in HTML
    assert 'name="viewport"' in HTML
    assert "<title>" in HTML
    assert 'name="description"' in HTML


def test_skip_link_and_landmarks():
    assert 'class="skip-link"' in HTML and 'href="#main"' in HTML
    assert "<header" in HTML and "<main" in HTML and "<footer" in HTML
    assert 'id="main"' in HTML


def test_live_regions_and_alert():
    assert HTML.count('aria-live="polite"') >= 1
    assert 'role="alert"' in HTML
    assert 'id="errors"' in HTML
    code_lines = [ln for ln in JS.splitlines() if ln.strip() and not ln.strip().startswith(("//", "/*", "*", "#"))]
    calls = [ln for ln in code_lines if re.search(r"(^|[^A-Za-z_.])alert\s*\(", ln)]
    assert not calls


def test_focus_and_keyboard():
    assert 'tabindex="-1"' in HTML
    assert ".focus()" in JS
    assert ":focus-visible" in CSS or "focus-visible" in CSS


def test_contrast_and_motion():
    assert "prefers-reduced-motion" in CSS
    assert "outline" in CSS
    assert "44px" in CSS


def test_noscript_and_disclaimer():
    assert "<noscript>" in HTML
    assert "General information only" in HTML


def test_xss_safe():
    assert "escapeHtml" in JS
    assert "textContent" in JS


def test_inputs_labels():
    assert 'for="name"' in HTML
    assert 'for="event_date"' in HTML
