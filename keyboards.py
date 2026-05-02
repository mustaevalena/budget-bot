from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CATEGORIES


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Добавить", callback_data="confirm"),
            InlineKeyboardButton("✏️ Категория", callback_data="edit_category"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
        ]
    ])


def category_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(c, callback_data=f"cat:{c}") for c in CATEGORIES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton("« Назад", callback_data="back")])
    return InlineKeyboardMarkup(rows)


def format_card(tx: dict) -> str:
    return (
        f"📅 <b>{tx['date']}</b>  |  {tx['merchant']}  |  <b>{tx['amount']:,} RSD</b>\n"
        f"🏷 {tx['suggested_category']}"
    ).replace(",", " ")
