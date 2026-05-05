import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIRMING
from keyboards import confirm_keyboard, format_card
from services.claude import parse_text
from services.sheets import append_transaction, get_merchant_categories

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.startswith("/"):
        return -1

    msg = await update.message.reply_text("🔍 Разбираю расход...")

    try:
        txs = parse_text(text)
    except Exception as e:
        logger.error("Claude error: %s", e)
        await msg.edit_text("❌ Не удалось разобрать расход. Попробуй в формате: «Кофе 500» или «Wolt 1200 RSD»")
        return -1

    try:
        known = get_merchant_categories()
    except Exception:
        known = {}

    auto_saved = []
    pending = []
    for tx in txs:
        key = tx["merchant"].strip().lower()
        if key in known:
            tx["suggested_category"] = known[key]
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
        else:
            pending.append(tx)

    if auto_saved:
        lines = "\n".join(f"• {t['merchant']} {t['amount']} RSD → {t['suggested_category']}" for t in auto_saved)
        await update.message.reply_text(f"✅ Автоматически записано:\n{lines}")

    if not pending:
        await msg.delete()
        return -1

    context.user_data["txs"] = pending
    context.user_data["tx_idx"] = 0
    total = len(pending)

    await msg.edit_text(
        format_card(pending[0], idx=0, total=total),
        reply_markup=confirm_keyboard(idx=0),
        parse_mode="HTML",
    )
    return CONFIRMING
