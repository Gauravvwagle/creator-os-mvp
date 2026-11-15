from app.research.verify import html_to_text, normalize, quote_in_text

PAGE = """
<html><head><title>Affiliate Program</title>
<style>.x { color: red; }</style></head>
<body><script>var secret = "hidden text here";</script>
<p>Members earn a   30% commission
on every qualifying sale.</p></body></html>
"""


def test_normalize_collapses_whitespace_and_case():
    assert normalize("  Hello \n  WORLD ") == "hello world"


def test_normalize_unifies_curly_quotes():
    assert normalize("It\u2019s fine") == "it's fine"


def test_html_to_text_extracts_title_and_ignores_scripts():
    title, text = html_to_text(PAGE)
    assert title == "Affiliate Program"
    assert "hidden text here" not in text
    assert "color: red" not in text


def test_quote_found_despite_whitespace_differences():
    _, text = html_to_text(PAGE)
    assert quote_in_text("earn a 30% commission on every qualifying sale", text)


def test_quote_not_found_when_wording_differs():
    _, text = html_to_text(PAGE)
    assert not quote_in_text("earn a 50% commission on every qualifying sale", text)


def test_too_short_excerpt_never_matches():
    assert not quote_in_text("the", "the quick brown fox")