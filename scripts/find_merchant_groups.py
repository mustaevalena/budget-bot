"""One-off helper: scan transaction history for merchants that likely belong to the
same chain (same canonical key, e.g. "Maxi 1234" and "Maxi 5678" both -> "maxi")
but were saved as different raw strings, so real duplicates can be reviewed before
relying on the bot's merge-confirmation flow to build up "правила мерчантов".

Run locally where the venv has real network access and Google credentials:
    venv/bin/python scripts/find_merchant_groups.py
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.merchant_grouping import canonical_key
from services.sheets import get_merchant_categories


def main() -> None:
    known = get_merchant_categories()  # {merchant_lower: last_used_category}
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for merchant, category in known.items():
        groups[canonical_key(merchant)].append((merchant, category))

    dup_groups = {ck: items for ck, items in groups.items() if len(items) > 1}
    if not dup_groups:
        print("Дублей по эвристике (общий чейн + цифровой ID в конце) не найдено.")
        return

    print(f"Найдено {len(dup_groups)} групп с потенциальными дублями:\n")
    for ck, items in sorted(dup_groups.items()):
        categories = {c for _, c in items}
        flag = "  ⚠️ РАЗНЫЕ КАТЕГОРИИ — уточнить вручную" if len(categories) > 1 else ""
        print(f"«{ck}»{flag}")
        for merchant, category in items:
            print(f"  - {merchant!r} -> {category}")
        print()


if __name__ == "__main__":
    main()
