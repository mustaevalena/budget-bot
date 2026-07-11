import logging

from services.merchant_grouping import canonical_key
from services.sheets import append_transaction, get_merchant_categories, get_merchant_rules

logger = logging.getLogger(__name__)


def classify_transactions(txs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split parsed transactions into auto-saved and pending-confirmation lists.

    A transaction auto-saves when its merchant exactly matches history, or its
    canonical key (chain name with the numeric store id stripped) matches an
    already-confirmed merchant-grouping rule. Otherwise it's pending; if its
    canonical key merely resembles a known merchant that has no confirmed rule
    yet, `tx["merge_candidate"]` is set so the UI can ask once whether to treat
    it as the same chain going forward.
    """
    try:
        known_exact = get_merchant_categories()
    except Exception:
        known_exact = {}
    try:
        known_rules = get_merchant_rules()
    except Exception:
        known_rules = {}

    known_groups: dict[str, tuple[str, str]] = {}
    for merchant, category in known_exact.items():
        known_groups.setdefault(canonical_key(merchant), (merchant, category))

    auto_saved: list[dict] = []
    pending: list[dict] = []
    for tx in txs:
        key = tx["merchant"].strip().lower()
        ck = canonical_key(tx["merchant"])

        if key in known_exact:
            tx["suggested_category"] = known_exact[key]
            _save(tx, auto_saved, pending)
            continue

        if ck in known_rules:
            tx["suggested_category"] = known_rules[ck]
            _save(tx, auto_saved, pending)
            continue

        candidate = known_groups.get(ck)
        if candidate and candidate[0] != key:
            tx["merge_candidate"] = {"canonical_key": ck, "example": candidate[0], "category": candidate[1]}
        pending.append(tx)

    return auto_saved, pending


def _save(tx: dict, auto_saved: list[dict], pending: list[dict]) -> None:
    try:
        append_transaction(
            date=tx["date"],
            merchant=tx["merchant"],
            amount=tx["amount"],
            category=tx["suggested_category"],
        )
        auto_saved.append(tx)
    except Exception as e:
        logger.error("Auto-save error: %s", e)
        pending.append(tx)
