from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CATEGORIES


def confirm_keyboard(idx: int = 0, merge_candidate: dict | None = None) -> InlineKeyboardMarkup:
    rows = []
    if merge_candidate:
        rows.append([
            InlineKeyboardButton(f"🔗 Да, это {merge_candidate['example']}", callback_data=f"merge_yes:{idx}"),
            InlineKeyboardButton("Только сейчас", callback_data=f"merge_once:{idx}"),
        ])
    rows.append([
        InlineKeyboardButton("✅ Добавить", callback_data=f"confirm:{idx}"),
        InlineKeyboardButton("✏️ Категория", callback_data=f"edit_category:{idx}"),
        InlineKeyboardButton("❌ Пропустить", callback_data=f"skip:{idx}"),
    ])
    return InlineKeyboardMarkup(rows)


def category_keyboard(idx: int = 0) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(c, callback_data=f"cat:{idx}:{c}") for c in CATEGORIES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton("« Назад", callback_data=f"back:{idx}")])
    return InlineKeyboardMarkup(rows)


def format_card(tx: dict, idx: int = 0, total: int = 1) -> str:
    counter = f" ({idx + 1}/{total})" if total > 1 else ""
    card = (
        f"📅 <b>{tx['date']}</b>  |  {tx['merchant']}  |  <b>{tx['amount']:,} RSD</b>{counter}\n"
        f"🏷 {tx['suggested_category']}"
    ).replace(",", " ")
    mc = tx.get("merge_candidate")
    if mc:
        card += f"\n🔗 Похоже на «{mc['example']}» ({mc['category']}) — тот же мерчант?"
    return card
