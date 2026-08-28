"""Allowlist sanitiser for HTML returned by the Mind.

The Mind replies in HTML (paragraphs, emphasis, links). Escaping it renders
literal `<p>` tags in the console; injecting it raw would run whatever the
model was persuaded to emit. So: parse it, keep a small formatting subset,
drop everything else, and keep the text of dropped tags.

Model output is untrusted input. A prompt-injected comment could ask the Mind
to emit a script tag or a javascript: link, and this is the boundary that has
to refuse it.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser
from typing import List

ALLOWED_TAGS = frozenset(
    {
        "p", "br", "b", "strong", "i", "em", "u", "s",
        "ul", "ol", "li", "code", "pre", "blockquote",
        "h3", "h4", "h5", "span", "div", "a",
    }
)

VOID_TAGS = frozenset({"br"})

# Tags whose *content* is dropped too -- unwrapping a <script> body would paste
# the source into the page as visible text.
DROP_CONTENT_TAGS = frozenset({"script", "style", "iframe", "object", "embed", "svg", "template"})

SAFE_URL_SCHEMES = ("http://", "https://", "mailto:")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self._open: List[str] = []
        self._suppress_depth = 0

    # -- helpers ---------------------------------------------------------
    def _safe_href(self, value: str) -> str | None:
        url = (value or "").strip()
        if not url.lower().startswith(SAFE_URL_SCHEMES):
            return None
        return html.escape(url, quote=True)

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT_TAGS:
            self._suppress_depth += 1
            return
        if self._suppress_depth or tag not in ALLOWED_TAGS:
            return  # unwrap: drop the tag, keep its text

        if tag == "a":
            href = next((self._safe_href(v) for k, v in attrs if k.lower() == "href"), None)
            if not href:
                return  # unwrap links we will not follow
            self.out.append(f'<a href="{href}" target="_blank" rel="noopener noreferrer">')
            self._open.append(tag)
            return

        self.out.append(f"<{tag}>")
        if tag not in VOID_TAGS:
            self._open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if not self._suppress_depth and tag in ALLOWED_TAGS and tag in VOID_TAGS:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT_TAGS:
            self._suppress_depth = max(0, self._suppress_depth - 1)
            return
        if self._suppress_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag in self._open:
            # Close everything opened inside the tag being closed.
            while self._open:
                open_tag = self._open.pop()
                self.out.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data):
        if not self._suppress_depth:
            self.out.append(html.escape(data, quote=False))

    def close_all(self) -> str:
        while self._open:
            self.out.append(f"</{self._open.pop()}>")
        return "".join(self.out)


def sanitize_html(raw: str) -> str:
    """Return `raw` reduced to a safe formatting subset."""
    if not raw:
        return ""
    parser = _Sanitizer()
    parser.feed(raw)
    parser.close()
    return parser.close_all().strip()


def to_plain_text(raw: str) -> str:
    """Strip markup entirely, preserving paragraph and list breaks."""
    if not raw:
        return ""

    collected: List[str] = []

    class _Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self._suppress = 0

        def handle_starttag(self, tag, attrs):
            if tag in DROP_CONTENT_TAGS:
                self._suppress += 1
            elif tag in ("p", "br", "li", "div", "h3", "h4", "h5"):
                collected.append("\n")

        def handle_endtag(self, tag):
            if tag in DROP_CONTENT_TAGS:
                self._suppress = max(0, self._suppress - 1)
            elif tag == "p":
                collected.append("\n")

        def handle_data(self, data):
            if not self._suppress:
                collected.append(data)

    parser = _Text()
    parser.feed(raw)
    parser.close()

    lines = [line.strip() for line in "".join(collected).splitlines()]
    return "\n".join(line for line in lines if line).strip()
