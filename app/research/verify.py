import re
import unicodedata
from html.parser import HTMLParser

_QUOTE_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ",
}


def normalize(text: str) -> str:
    """Lowercase, unify quotes/dashes, and collapse whitespace so tiny
    formatting differences don't cause false mismatches."""
    text = unicodedata.normalize("NFKC", text)
    for old, new in _QUOTE_MAP.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def quote_in_text(excerpt: str, page_text: str) -> bool:
    needle = normalize(excerpt)
    if len(needle) < 10:
        return False
    return needle in normalize(page_text)


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip_depth == 0:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, visible_text) from an HTML string."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.title.strip(), " ".join(parser.parts)