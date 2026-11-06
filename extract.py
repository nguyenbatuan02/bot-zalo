"""Trích số điện thoại Việt Nam từ văn bản."""
import re

# 0xxxxxxxxx / +84xxxxxxxxx / 84xxxxxxxxx, cho phép dấu cách . - ngăn cách
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){8,9}(?!\d)")
_VALID_PREFIX = re.compile(r"^0(3[2-9]|5[25689]|7[06-9]|8[1-9]|9\d|2\d)")


def normalize(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits


def find_phones(text: str) -> list[str]:
    seen, out = set(), []
    for m in _PHONE_RE.finditer(text or ""):
        p = normalize(m.group())
        if len(p) in (10, 11) and _VALID_PREFIX.match(p) and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    low = (text or "").lower()
    return [k for k in keywords if k.lower() in low]
