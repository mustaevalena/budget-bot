import logging
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import CATEGORIES, CHOOSING_CATEGORY, CONFIRMING
from keyboards import category_keyboard, confirm_keyboard, format_card
from services.categorize import classify_transactions
from services.claude import parse_text

logger = logging.getLogger(__name__)

# A message that's just a number, e.g. "500" or "1200.50" — no merchant to parse,
# skip Claude and go straight to category selection.
_AMOUNT_RE = re.compile(r"^\d+([.,]\d+)?$")


async def _handle_bare_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    tx = {
        "date": datetime.now().strftime("%d.%m"),
        "merchant": "",
        "amount": round(float(text.replace(",", "."))),
        "suggested_category": CATEGORIES[0],
    }
    context.user_data["txs"] = [tx]
    context.user_data["tx_idx"] = 0
    context.user_data["auto_saved"] = []
    await update.message.reply_text(
        format_card(tx, idx=0, total=1),
        reply_markup=category_keyboard(idx=0),
        parse_mode="HTML",
    )
    return CHOOSING_CATEGORY


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.startswith("/"):
        return -1

    if _AMOUNT_RE.match(text):
        return await _handle_bare_amount(update, context, text)

    msg = await update.message.reply_text("🔍 Разбираю расход...")

    try:
        txs = parse_text(text)
    except Exception as e:
        logger.error("Claude error: %s", e)
        await msg.edit_text("❌ Не удалось разобрать расход. Попробуй в формате: «Кофе 500» или «Wolt 1200 RSD»")
        return -1

    auto_saved, pending = classify_transactions(txs)

    if not pending:
        # Nothing to confirm — show report immediately
        if auto_saved:
            lines = "\n".join(f"• {t['date']} {t['merchant']} {t['amount']} RSD → {t['suggested_category']}" for t in auto_saved)
            await msg.edit_text(f"✅ Записано ({len(auto_saved)}):\n{lines}")
        else:
            await msg.delete()
        return -1

    context.user_data["txs"] = pending
    context.user_data["tx_idx"] = 0
    context.user_data["auto_saved"] = auto_saved
    total = len(pending)

    await msg.edit_text(
        format_card(pending[0], idx=0, total=total),
        reply_markup=confirm_keyboard(idx=0, merge_candidate=pending[0].get("merge_candidate")),
        parse_mode="HTML",
    )
    return CONFIRMING
