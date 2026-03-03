from __future__ import annotations

import re

ARABIC_LETTER_RE = re.compile(r"[\u0600-\u06FF]")
ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
ARABIC_TATWEEL_RE = re.compile(r"\u0640")
ARABIC_WHITESPACE_RE = re.compile(r"\s+")

_DIGIT_TRANSLATION = str.maketrans(
    {
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
        "\u06F0": "0",
        "\u06F1": "1",
        "\u06F2": "2",
        "\u06F3": "3",
        "\u06F4": "4",
        "\u06F5": "5",
        "\u06F6": "6",
        "\u06F7": "7",
        "\u06F8": "8",
        "\u06F9": "9",
        "\u066B": ".",
        "\u066C": "",
        "\u060C": ",",
        "\u061F": "?",
    }
)


def arabic_ratio(text: str) -> float:
    raw = str(text or "")
    if not raw:
        return 0.0
    total_letters = sum(1 for ch in raw if ch.isalpha())
    if total_letters <= 0:
        return 0.0
    ar_letters = sum(1 for ch in raw if ARABIC_LETTER_RE.search(ch))
    return max(0.0, min(1.0, ar_letters / total_letters))


def contains_arabic(text: str, min_ratio: float = 0.18) -> bool:
    return arabic_ratio(text) >= max(0.0, min(1.0, min_ratio))


def arabic_to_ascii_digits(text: str) -> str:
    return str(text or "").translate(_DIGIT_TRANSLATION)


def normalize_arabic_text(text: str) -> str:
    out = str(text or "")
    out = arabic_to_ascii_digits(out)
    out = ARABIC_TATWEEL_RE.sub("", out)
    out = ARABIC_DIACRITICS_RE.sub("", out)

    # Normalize common letter variants.
    out = re.sub(r"[إأآٱ]", "ا", out)
    out = out.replace("ؤ", "و")
    out = out.replace("ئ", "ي")
    out = out.replace("ى", "ي")
    out = out.replace("ة", "ه")
    out = out.replace("گ", "ك")
    out = out.replace("پ", "ب")
    out = out.replace("چ", "ج")

    out = ARABIC_WHITESPACE_RE.sub(" ", out).strip()
    return out


def canonical_arabic_token(token: str) -> str:
    t = normalize_arabic_text(token)
    t = re.sub(r"[^\u0600-\u06FFa-zA-Z0-9_\-\+\*\/\^=\(\)\.]+", "", t)
    return t.strip().lower()
