import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIRMING
from keyboards import confirm_keyboard, format_card
from services.categorize import classify_transactions
from services.claude import parse_text

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
