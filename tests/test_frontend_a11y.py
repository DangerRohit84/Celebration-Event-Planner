"""Frontend accessibility tests.

The markup is parsed with the standard-library HTML parser so the assertions
reflect the real DOM rather than a fragile regex, and the stylesheet is
cross-checked for 44px touch targets and documented AA contrast.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

# Anchored to the repository root so collection never depends on the cwd.
ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

FORM_CONTROL_TAGS = ("input", "select", "textarea")
INTERACTIVE_TAGS = ("input", "select", "textarea", "button")
MIN_TOUCH_TARGET_PX = 44


class _DomIndex(HTMLParser):
    """Minimal DOM index: element ids, form controls, and label targets."""

    def __init__(self: "_DomIndex") -> None:
        """Create an empty index.

        Returns:
            None.
        """
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.controls: list[tuple[str, str, dict[str, str]]] = []
        self.labels: set[str] = set()

    def handle_starttag(
        self: "_DomIndex", tag: str, attrs: list[tuple[str, str | None]],
    ) -> None:
        """Record ids, form controls, and label targets.

        Args:
            tag: Lower-case tag name of the element being opened.
            attrs: List of (name, value) attribute pairs.

        Returns:
            None.
        """
        attributes = {k: (v or "") for k, v in attrs}
        element_id = attributes.get("id", "")
        if element_id:
            self.ids.add(element_id)
        if tag in FORM_CONTROL_TAGS:
            self.controls.append((tag, element_id, attributes))
        if tag == "label" and attributes.get("for"):
            self.labels.add(attributes["for"])


DOM = _DomIndex()
DOM.feed(HTML)


def _css_rules(css: str) -> list[tuple[str, str]]:
    """Split a stylesheet into (selector, declarations) pairs.

    Args:
        css: Stylesheet source text.

    Returns:
        A list of selector and declaration-block pairs.
    """
    return [
        (match.group(1).strip(), match.group(2))
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
    ]


def _selector_targets(selector: str, tag: str) -> bool:
    """Report whether a selector list targets the given element tag.

    Args:
        selector: A single selector taken from a selector list.
        tag: Element tag to look for, e.g. "input".

    Returns:
        True when the selector targets that tag.
    """
    pattern = rf"(^|[\s>+~]){re.escape(tag)}($|[\s>+~:.\[])"
    return re.search(pattern, selector) is not None


def _rules_for(tag: str) -> list[str]:
    """Collect the declaration blocks of every rule targeting a tag.

    Args:
        tag: Element tag to look for, e.g. "button".

    Returns:
        The declaration blocks of all matching rules.
    """
    return [
        body
        for selector, body in _css_rules(CSS)
        if any(_selector_targets(part, tag) for part in selector.split(","))
    ]


def test_page_has_form_controls() -> None:
    """The page must actually contain the controls the checks describe."""
    assert DOM.controls, "no form controls found in frontend/index.html"


def test_every_form_control_has_a_matching_label() -> None:
    """Each input, select, and textarea needs a <label for="...">."""
    missing = [
        f"{tag}#{element_id or '(no id)'}"
        for tag, element_id, _ in DOM.controls
        if not element_id or element_id not in DOM.labels
    ]
    assert not missing, f"form controls without a matching label: {missing}"


def test_every_form_control_has_an_id() -> None:
    """Labels can only bind to a control when the control has an id."""
    missing = [tag for tag, element_id, _ in DOM.controls if not element_id]
    assert not missing, f"form controls without an id: {missing}"


def test_aria_describedby_points_at_real_elements() -> None:
    """Every aria-describedby reference must resolve to an existing id."""
    broken = [
        f"{tag}#{element_id} -> {reference}"
        for tag, element_id, attributes in DOM.controls
        for reference in (attributes.get("aria-describedby") or "").split()
        if reference not in DOM.ids
    ]
    assert not broken, f"aria-describedby references a missing id: {broken}"


def test_every_form_control_is_described() -> None:
    """Every form control carries a hint for assistive technology."""
    missing = [
        f"{tag}#{element_id}"
        for tag, element_id, attributes in DOM.controls
        if not (attributes.get("aria-describedby") or "").strip()
    ]
    assert not missing, f"form controls without aria-describedby: {missing}"


def test_interactive_elements_have_44px_touch_targets() -> None:
    """Every interactive element must be at least 44x44 CSS pixels."""
    for tag in INTERACTIVE_TAGS:
        bodies = _rules_for(tag)
        assert bodies, f"no CSS rule targets {tag}"
        assert any(
            re.search(r"min-height\s*:\s*44px", body) for body in bodies
        ), f"{tag} has no min-height: 44px rule"
        assert any(
            re.search(r"min-width\s*:\s*44px", body) for body in bodies
        ), f"{tag} has no min-width: 44px rule"


def test_touch_target_size_constant_is_documented() -> None:
    """The touch-target floor is stated in the stylesheet."""
    assert f"min-height: {MIN_TOUCH_TARGET_PX}px" in CSS
    assert f"min-width: {MIN_TOUCH_TARGET_PX}px" in CSS


def test_contrast_ratios_are_documented() -> None:
    """The stylesheet must document the achieved AA contrast ratios."""
    assert "CONTRAST RATIOS" in CSS
    assert "4.5:1" in CSS
    assert "3:1" in CSS
    assert "--border-strong" in CSS


def test_live_regions_and_roles() -> None:
    """Status, alert, and result regions need the right ARIA roles."""
    assert 'id="status"' in HTML
    assert 'role="status"' in HTML
    assert 'id="errors"' in HTML
    assert 'role="alert"' in HTML
    assert 'id="answer"' in HTML
    assert 'aria-live="polite"' in HTML
    assert 'aria-live="assertive"' in HTML


def _strip_comments(source: str) -> str:
    """Remove line and block comments from a script.

    Args:
        source: Script source text.

    Returns:
        The source with comments removed, so prose about a banned API is not
        mistaken for a use of it.
    """
    without_blocks = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", without_blocks)


def test_no_innerhtml_in_client_script() -> None:
    """The client must never inject markup through innerHTML."""
    code = _strip_comments(JS)
    assert "innerHTML" not in code
    assert "insertAdjacentHTML" not in code
    assert "outerHTML" not in code
    assert "textContent" in code
    assert "createElement" in code


def test_client_keeps_existing_dom_ids() -> None:
    """The client script must keep referencing the documented element ids."""
    for element_id in (
        "create-form",
        "status",
        "errors",
        "answer",
        "answerMode",
        "citations",
        "askBtn",
        "exportBtn",
        "q",
        "plain",
        "docfile",
        "uploadBtn",
        "uploadStatus",
    ):
        assert element_id in JS, f"app.js no longer references #{element_id}"


def test_plain_language_toggle_exists_and_is_labelled() -> None:
    """The simple-language switch must exist and carry a real label."""
    checkboxes = [
        (tag, element_id, attributes)
        for tag, element_id, attributes in DOM.controls
        if attributes.get("type") == "checkbox"
    ]
    assert checkboxes, "no plain-language checkbox found in frontend/index.html"
    ids = {element_id for _tag, element_id, _attributes in checkboxes}
    assert "plain" in ids
    assert "plain" in DOM.labels, "the plain-language checkbox has no <label for>"


def test_plain_language_toggle_is_described() -> None:
    """The plain-language switch must point at a hint that exists."""
    described = [
        attributes.get("aria-describedby")
        for _tag, element_id, attributes in DOM.controls
        if element_id == "plain"
    ]
    assert described and described[0]
    assert described[0] in DOM.ids


def test_plain_language_flag_is_sent_to_the_api() -> None:
    """The client must send the plain_language flag with the question."""
    code = _strip_comments(JS)
    assert "plain_language" in code
    assert "getElementById('plain')" in code


def test_answer_mode_is_announced() -> None:
    """The answer panel reports which language mode was used."""
    assert 'id="answerMode"' in HTML
    assert "plain_language" in JS


def test_skip_link_and_landmarks_survive() -> None:
    """The skip link and landmark roles must remain in place."""
    assert 'class="skip-link"' in HTML
    assert 'href="#main"' in HTML
    assert 'role="banner"' in HTML
    assert 'role="main"' in HTML
    assert 'role="contentinfo"' in HTML
    assert "<noscript>" in HTML


def test_upload_card_has_a_labelled_file_input() -> None:
    """The upload card must have a file input bound to a real label."""
    file_inputs = [
        (element_id, attributes)
        for tag, element_id, attributes in DOM.controls
        if tag == "input" and attributes.get("type") == "file"
    ]
    assert file_inputs, "no file input found in frontend/index.html"
    element_id, attributes = file_inputs[0]
    assert element_id == "docfile"
    assert element_id in DOM.labels, "the file input has no <label for>"
    assert (attributes.get("aria-describedby") or "").strip()
    assert attributes.get("accept") == ".pdf,application/pdf"


def test_file_input_is_keyboard_operable() -> None:
    """The file input must be present and not disabled."""
    attributes = {
        element_id: attrs
        for tag, element_id, attrs in DOM.controls
        if tag == "input" and attrs.get("type") == "file"
    }
    assert "docfile" in attributes
    assert "disabled" not in attributes["docfile"]


def test_upload_button_is_named_and_wired() -> None:
    """The upload button must exist with an accessible name."""
    assert 'id="uploadBtn"' in HTML
    assert ">Upload</button>" in HTML
    assert "getElementById('uploadBtn')" in JS


def test_upload_handler_posts_the_file_to_the_upload_endpoint() -> None:
    """The client must POST the chosen file to /upload as multipart."""
    code = _strip_comments(JS)
    assert "fetch('/upload', { method: 'POST', body })" in code
    assert "new FormData()" in code
    assert "Upload failed: ' + res.status" in code


def test_upload_result_is_announced_in_a_dedicated_region() -> None:
    """Upload feedback must go to its own polite live region."""
    assert 'id="uploadStatus"' in HTML
    assert 'role="status"' in HTML
    assert "getElementById('uploadStatus')" in JS


def test_error_region_is_focusable() -> None:
    """#errors must be focusable so the client can move focus to it."""
    opening_tag = re.search(r'<div id="errors"[^>]*>', HTML)
    assert opening_tag, "errors region missing from frontend/index.html"
    assert 'tabindex="-1"' in opening_tag.group(0)
    assert "setAttribute('tabindex', '-1')" in JS
