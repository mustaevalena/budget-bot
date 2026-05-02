import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIRMING
from keyboards import confirm_keyboard, format_card
from services.claude import parse_text

logger = logging.getLogger(__name__)

_SKIP_COMMANDS = {"/start", "/help", "/cancel"}


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.startswith("/"):
        return -1  # ConversationHandler.END

    msg = await update.message.reply_text("🔍 Разбираю расход...")

    try:
        tx = parse_text(text)
    except Exception as e:
        logger.error("Claude error: %s", e)
        await msg.edit_text("❌ Не удалось разобрать расход. Попробуй в формате: «Кофе 500» или «Wolt 1200 RSD»")
        return -1

    context.user_data["tx"] = tx
    await msg.edit_text(
        format_card(tx),
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )
    return CONFIRMING
