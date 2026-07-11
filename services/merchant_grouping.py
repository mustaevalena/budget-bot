import re

# Store IDs are the usual reason two raw merchant strings from the same chain
# don't match exactly (e.g. "Maxi 1234" vs "Maxi 5678"). Require 2+ digits so we
# don't strip meaningful single-digit names.
_TRAILING_ID_RE = re.compile(r"^(.+?)[\s\-#№]*\d{2,}\s*$")


def canonical_key(merchant: str) -> str:
    """Chain name used to group near-duplicate merchants that differ only by a
    numeric store id, e.g. "Maxi 1234" and "Maxi 5678" both -> "maxi"."""
    name = " ".join(merchant.strip().lower().split())
    m = _TRAILING_ID_RE.match(name)
    base = m.group(1).strip() if m else name
    return base or name
