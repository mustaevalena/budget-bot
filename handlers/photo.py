import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIRMING
from keyboards import confirm_keyboard, format_card
from services.claude import parse_screenshot
from services.sheets import append_transaction, get_merchant_categories

logger = logging.getLogger(__name__)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = await update.message.reply_text("🔍 Распознаю транзакции...")

    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    try:
        txs = parse_screenshot(bytes(image_bytes))
    except Exception as e:
        logger.error("Claude error: %s", e)
        await msg.edit_text("❌ Не удалось распознать транзакции. Попробуй ещё раз или введи текстом.")
        return -1

    if not txs:
        await msg.edit_text("❌ Транзакций не найдено на скрине.")
        return -1

    # Auto-save known merchants
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

    # Report auto-saved
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
