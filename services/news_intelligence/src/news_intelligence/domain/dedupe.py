"""Content hashing and deduplication helpers."""

import hashlib
import re


_WHITESPACE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return _WHITESPACE.sub(" ", text.strip().lower())


def content_hash(title: str, body: str) -> str:
    """Stable hash used for near-exact story deduplication."""
    normalized = normalize_text(f"{title}\n{body}")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def near_duplicate_key(title: str) -> str:
    """Coarser key for title-level clustering."""
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(tokens[:12])
