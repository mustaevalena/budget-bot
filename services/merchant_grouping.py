import re

_TRAILING_PUNCT_RE = re.compile(r"[^\w.]+$")


def canonical_key(merchant: str) -> str:
    """Chain name used to group near-duplicate merchants from the same chain.
    Bank descriptors vary in what they tack onto the chain name — a store id
    ("Maxi 1234" vs "Maxi 5678"), a branch code ("Univerexport-MP135"), or a
    location that's sometimes present and sometimes not ("Univerexport Mokrin"
    vs "Univerexport"). All of that reliably comes after the chain name, so we
    use the first word as the key; a first word under 3 chars is usually an
    abbreviation too ambiguous to group on ("BS", "AU"), so fall back to the
    full string in that case (no grouping, but no false merges either)."""
    name = " ".join(merchant.strip().lower().split())
    first_word = _TRAILING_PUNCT_RE.sub("", name.split(" ", 1)[0]) if name else name
    return first_word if len(first_word) >= 3 else name
