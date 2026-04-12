"""
Normalizer: cleans raw HTML/text and extracts structured fields.
Pure sync functions — no DB access, no I/O.
"""
import re
import unicodedata


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"https?://\S+")


def strip_html(text: str) -> str:
    text = _TAG_RE.sub(" ", text)
    # Decode common HTML entities
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    return text


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def remove_urls(text: str) -> str:
    return _URL_RE.sub("", text)


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def clean_text(raw: str | None, max_chars: int = 8000) -> str:
    """Full cleaning pipeline for arbitrary text."""
    if not raw:
        return ""
    text = normalize_unicode(raw)
    text = strip_html(text)
    text = normalize_whitespace(text)
    return text[:max_chars]


def clean_title(raw: str | None, max_chars: int = 512) -> str:
    if not raw:
        return ""
    text = normalize_unicode(raw)
    text = strip_html(text)
    text = normalize_whitespace(text)
    # Titles should not contain newlines
    text = text.replace("\n", " ")
    return text[:max_chars]


def extract_text_for_hashing(title: str | None, content: str | None) -> str:
    """
    Produce a normalized string suitable for MinHash / content dedup.
    Strips URLs, lowercases, condenses whitespace.
    """
    combined = f"{title or ''} {content or ''}".lower()
    combined = strip_html(combined)
    combined = remove_urls(combined)
    combined = normalize_whitespace(combined)
    return combined


def tokenize_for_minhash(text: str, ngram_size: int = 3) -> list[str]:
    """
    Convert text to character n-grams for MinHash.
    Character n-grams are more robust to minor edits than word tokens.
    """
    text = text.lower()
    if len(text) < ngram_size:
        return [text]
    return [text[i : i + ngram_size] for i in range(len(text) - ngram_size + 1)]
