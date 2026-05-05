from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CATEGORIES


def confirm_keyboard(idx: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Добавить", callback_data=f"confirm:{idx}"),
            InlineKeyboardButton("✏️ Категория", callback_data=f"edit_category:{idx}"),
            InlineKeyboardButton("❌ Пропустить", callback_data=f"skip:{idx}"),
        ]
    ])


def category_keyboard(idx: int = 0) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(c, callback_data=f"cat:{idx}:{c}") for c in CATEGORIES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton("« Назад", callback_data=f"back:{idx}")])
    return InlineKeyboardMarkup(rows)


def format_card(tx: dict, idx: int = 0, total: int = 1) -> str:
    counter = f" ({idx + 1}/{total})" if total > 1 else ""
    return (
        f"📅 <b>{tx['date']}</b>  |  {tx['merchant']}  |  <b>{tx['amount']:,} RSD</b>{counter}\n"
        f"🏷 {tx['suggested_category']}"
    ).replace(",", " ")
