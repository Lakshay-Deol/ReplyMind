"""The Mind's HTML is untrusted model output and must be reduced, not trusted.

A prompt-injected comment can steer what the Mind emits, so this boundary is
what stands between "the Mind formatted a reply" and "the Mind was talked into
emitting a script tag into the creator's console".
"""

from app.review.sanitize import sanitize_html, to_plain_text

# --- formatting that should survive ---------------------------------------


def test_keeps_basic_formatting():
    out = sanitize_html("<p>Hello <b>there</b> and <i>hi</i></p>")
    assert out == "<p>Hello <b>there</b> and <i>hi</i></p>"


def test_keeps_lists_and_breaks():
    out = sanitize_html("<ul><li>one</li><li>two</li></ul><br>")
    assert out == "<ul><li>one</li><li>two</li></ul><br>"


def test_keeps_http_links_and_hardens_them():
    out = sanitize_html('<a href="https://hellominds.ai/top-up">Top up</a>')
    assert 'href="https://hellominds.ai/top-up"' in out
    assert 'rel="noopener noreferrer"' in out
    assert 'target="_blank"' in out


# --- what must not survive -------------------------------------------------


def test_drops_script_tags_and_their_contents():
    out = sanitize_html('<p>hi</p><script>alert("xss")</script>')
    assert "script" not in out.lower()
    assert "alert" not in out


def test_drops_javascript_urls_but_keeps_the_text():
    out = sanitize_html('<a href="javascript:alert(1)">click me</a>')
    assert "javascript" not in out.lower()
    assert "href" not in out
    assert "click me" in out


def test_drops_event_handler_attributes():
    out = sanitize_html('<p onclick="steal()">text</p>')
    assert "onclick" not in out
    assert "steal" not in out
    assert "text" in out


def test_drops_style_and_iframe_content():
    assert "iframe" not in sanitize_html('<iframe src="https://evil.test"></iframe>').lower()
    assert "body{" not in sanitize_html("<style>body{display:none}</style>")


def test_escapes_bare_text_angle_brackets():
    out = sanitize_html("5 < 7 and 9 > 2")
    assert "&lt;" in out


def test_unknown_tags_are_unwrapped_not_dropped():
    """Losing the sentence would be worse than losing the tag."""
    out = sanitize_html("<marquee>important text</marquee>")
    assert "marquee" not in out
    assert "important text" in out


def test_empty_input_is_safe():
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""


def test_unclosed_tags_are_closed():
    out = sanitize_html("<p>dangling")
    assert out.endswith("</p>")


# --- plain-text extraction -------------------------------------------------


def test_plain_text_strips_markup_and_keeps_structure():
    text = to_plain_text("<p>First para</p><p>Second para</p>")
    assert "<" not in text
    assert "First para" in text and "Second para" in text
    assert "\n" in text


def test_plain_text_drops_script_bodies():
    assert "alert" not in to_plain_text('<p>hi</p><script>alert(1)</script>')


def test_real_mind_reply_round_trips():
    """The actual shape the Mind returned during a live run."""
    raw = (
        "<p>Hey - I can't run the analysis while my cognition runway is negative.</p>"
        '<p>Top-up link: <a href="https://hellominds.ai/minds/abc/top-up?price=15">here</a></p>'
        "<p>• <b>$5</b> - gets us through today<br>• <b>$15</b> - a working week</p>"
    )
    html_out = sanitize_html(raw)
    assert "<script" not in html_out
    assert "hellominds.ai" in html_out
    assert "<b>$5</b>" in html_out

    text_out = to_plain_text(raw)
    assert "cognition runway is negative" in text_out
    assert "<p>" not in text_out
