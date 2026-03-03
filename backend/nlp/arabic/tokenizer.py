from __future__ import annotations

import re

from .normalizer import normalize_arabic_text

TOKEN_RE = re.compile(r"[\u0600-\u06FF]+|\d+(?:\.\d+)?|[a-zA-Z]+|[\+\-\*\/\^=\(\)]+")


def tokenize_arabic(text: str) -> list[str]:
    normalized = normalize_arabic_text(text)
    return TOKEN_RE.findall(normalized)
