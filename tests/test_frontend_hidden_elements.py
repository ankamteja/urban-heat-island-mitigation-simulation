"""
Every element the dashboard hides with the `hidden` attribute must actually be
hidden.

This exists because of a defect that shipped: `#drop-overlay` was created with
the `hidden` attribute and toggled through `element.hidden`, and the JavaScript
was correct -- `overlay.hidden` really was `true`. But `style.css` also carried

    .drop-overlay { display: grid; ... }

and the browser's own `[hidden] { display: none }` lives in the user-agent
stylesheet, which *any* author rule outranks. So the attribute did nothing and a
full-viewport overlay sat over the entire dashboard from first load, swallowing
every click on the map.

What made it survive review is worth recording: the first browser test asserted
`overlay.hidden === true`, which was true and always had been. Asserting the
property tests the thing that was never broken. The element was hidden in the
DOM and painted on the screen at the same time, and only a computed-style or
pixel check can tell those apart.

This test is the cheap static half of that check: any class that sets a
`display` other than `none` must also carry a `[hidden]` rule turning it off.
The expensive half is looking at `getComputedStyle`, which needs a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
FRONTEND = REPO_DIR / "frontend"
INDEX = FRONTEND / "index.html"
STYLE = FRONTEND / "style.css"


def _hidden_classes() -> set[str]:
    """Classes on elements that index.html renders with the `hidden` attribute."""
    html = INDEX.read_text(encoding="utf-8")
    classes: set[str] = set()
    # Tags carrying `hidden` as a bare boolean attribute, in either attribute
    # order. The lookarounds matter: `\bhidden\b` also matches the `hidden` in
    # `aria-hidden="true"`, which is a different attribute with no effect on
    # `display` -- it reported .compare-rail as broken when it is not.
    for tag in re.findall(r"<(\w+)\b((?:[^>]*?[\s\"])hidden(?![-\w=])[^>]*)>", html):
        attrs = tag[1]
        m = re.search(r'class\s*=\s*"([^"]*)"', attrs)
        if m:
            classes.update(m.group(1).split())
    return classes


def _display_rules() -> dict[str, str]:
    """class name -> the display value its own rule sets, ignoring `none`."""
    css = STYLE.read_text(encoding="utf-8")
    # Strip comments so a commented-out rule is not mistaken for a live one.
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    rules: dict[str, str] = {}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selector = selector.strip()
        # Only bare single-class selectors set the default for an element.
        m = re.fullmatch(r"\.([A-Za-z0-9_-]+)", selector)
        if not m:
            continue
        d = re.search(r"(?<![-\w])display\s*:\s*([^;]+)", body)
        if d and d.group(1).strip() != "none":
            rules[m.group(1)] = d.group(1).strip()
    return rules


def _has_hidden_guard(cls: str) -> bool:
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(encoding="utf-8"), flags=re.S)
    pattern = rf"\.{re.escape(cls)}\[hidden\][^{{]*\{{[^}}]*display\s*:\s*none"
    return re.search(pattern, css) is not None


def test_hidden_elements_are_not_re_shown_by_a_display_rule():
    """An author `display` rule silently defeats the `hidden` attribute.

    If this fails, the named element is in the DOM as hidden and painted on the
    screen at the same time. Fix it by adding

        .that-class[hidden] { display: none; }

    or by defaulting the class to `display: none` and opting in with a modifier
    class, which is what every other panel in this dashboard does.
    """
    hidden = _hidden_classes()
    displays = _display_rules()

    offenders = [
        f".{cls} sets display:{displays[cls]} but is used with the hidden "
        f"attribute and has no `.{cls}[hidden] {{ display: none }}` rule"
        for cls in sorted(hidden & displays.keys())
        if not _has_hidden_guard(cls)
    ]
    assert not offenders, "\n".join(offenders)


def test_the_drop_overlay_specifically_is_guarded():
    """Pinned by name: this is the one that shipped broken."""
    assert 'class="drop-overlay"' in INDEX.read_text(encoding="utf-8")
    assert _has_hidden_guard("drop-overlay"), (
        "The drop overlay covers the whole viewport. Without a [hidden] rule it "
        "is painted over the dashboard from first load and swallows every click.")
