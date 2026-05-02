import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIRMING
from keyboards import confirm_keyboard, format_card
from services.claude import parse_screenshot

logger = logging.getLogger(__name__)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = await update.message.reply_text("🔍 Распознаю транзакцию...")

    photo = update.message.photo[-1]  # highest resolution
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    try:
        tx = parse_screenshot(bytes(image_bytes))
    except Exception as e:
        logger.error("Claude error: %s", e)
        await msg.edit_text("❌ Не удалось распознать транзакцию. Попробуй ещё раз или введи текстом.")
        return -1  # ConversationHandler.END

    context.user_data["tx"] = tx
    await msg.edit_text(
        format_card(tx),
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )
    return CONFIRMING
