import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN, CONFIRMING, CHOOSING_CATEGORY
from handlers.photo import handle_photo
from handlers.text import handle_text
from keyboards import category_keyboard, confirm_keyboard, format_card
from services.sheets import append_transaction

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context) -> None:
    await update.message.reply_text(
        "👋 Привет! Я записываю расходы в таблицу.\n\n"
        "Пришли скрин транзакции из банка или напиши текстом:\n"
        "<i>Кофе 500</i> или <i>Wolt 1200 RSD еда</i>",
        parse_mode="HTML",
    )


async def cmd_cancel(update: Update, context) -> int:
    context.user_data.clear()
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ── callback handlers ──────────────────────────────────────────────────────────

async def cb_confirm(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    tx = context.user_data.get("tx", {})
    try:
        append_transaction(
            date=tx["date"],
            merchant=tx["merchant"],
            amount=tx["amount"],
            category=tx["suggested_category"],
            comment=tx.get("comment", ""),
        )
        await query.edit_message_text(
            f"✅ Добавлено: {tx['merchant']}, {tx['amount']:,} RSD → {tx['suggested_category']}".replace(",", " ")
        )
    except Exception as e:
        logger.error("Excel error: %s", e)
        await query.edit_message_text("❌ Ошибка при записи в таблицу. Проверь EXCEL_PATH.")
    context.user_data.clear()
    return ConversationHandler.END


async def cb_cancel(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Отменено.")
    context.user_data.clear()
    return ConversationHandler.END


async def cb_edit_category(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=category_keyboard())
    return CHOOSING_CATEGORY


async def cb_choose_category(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data[len("cat:"):]
    tx = context.user_data.get("tx", {})
    tx["suggested_category"] = category
    context.user_data["tx"] = tx
    await query.edit_message_text(
        format_card(tx),
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )
    return CONFIRMING


async def cb_back(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    tx = context.user_data.get("tx", {})
    await query.edit_message_text(
        format_card(tx),
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )
    return CONFIRMING


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        ],
        states={
            CONFIRMING: [
                CallbackQueryHandler(cb_confirm, pattern="^confirm$"),
                CallbackQueryHandler(cb_cancel, pattern="^cancel$"),
                CallbackQueryHandler(cb_edit_category, pattern="^edit_category$"),
            ],
            CHOOSING_CATEGORY: [
                CallbackQueryHandler(cb_choose_category, pattern="^cat:"),
                CallbackQueryHandler(cb_back, pattern="^back$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(conv)

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
