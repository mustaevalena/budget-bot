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
from services.sheets import append_transaction, get_month_total, repair_summary_formulas

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


async def cmd_repair(update: Update, context) -> None:
    msg = await update.message.reply_text("🔧 Восстанавливаю формулы в листе 'суммы по месяцам'...")
    try:
        repair_summary_formulas()
        await msg.edit_text("✅ Формулы восстановлены.")
    except Exception as e:
        logger.error("Repair error: %s", e)
        await msg.edit_text(f"❌ Ошибка: {e}")


async def cmd_cancel(update: Update, context) -> int:
    context.user_data.clear()
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def _current_tx(context) -> tuple[dict, int, int]:
    txs = context.user_data.get("txs", [])
    idx = context.user_data.get("tx_idx", 0)
    return txs[idx], idx, len(txs)


async def _show_next(query, context, idx: int) -> int:
    """Show next transaction or finish."""
    txs = context.user_data.get("txs", [])
    if idx >= len(txs):
        # Check summary totals for the current month
        saved = context.user_data.get("saved_dates", [])
        summary = ""
        if saved:
            try:
                month_num = int(saved[-1].split(".")[1])
                total = get_month_total(month_num)
                from config import MONTH_NAMES
                month_name = MONTH_NAMES.get(month_num, str(month_num))
                if total is not None:
                    summary = f"\n\n📊 Итого за {month_name}: {total:,} RSD".replace(",", " ")
            except Exception:
                pass
        await query.edit_message_text(f"✅ Все транзакции обработаны.{summary}")
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data["tx_idx"] = idx
    tx = txs[idx]
    await query.edit_message_text(
        format_card(tx, idx=idx, total=len(txs)),
        reply_markup=confirm_keyboard(idx=idx),
        parse_mode="HTML",
    )
    return CONFIRMING


async def cb_confirm(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    txs = context.user_data.get("txs", [])
    tx = txs[idx]
    try:
        append_transaction(
            date=tx["date"],
            merchant=tx["merchant"],
            amount=tx["amount"],
            category=tx["suggested_category"],
            comment=tx.get("comment", ""),
        )
        dates = context.user_data.setdefault("saved_dates", [])
        dates.append(tx["date"])
        await query.answer(f"✅ {tx['merchant']} добавлен", show_alert=False)
    except Exception as e:
        logger.error("Sheets error: %s", e)
        await query.answer("❌ Ошибка записи", show_alert=True)
    return await _show_next(query, context, idx + 1)


async def cb_skip(update: Update, context) -> int:
    query = update.callback_query
    await query.answer("Пропущено")
    idx = int(query.data.split(":")[1])
    return await _show_next(query, context, idx + 1)


async def cb_cancel(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Отменено.")
    context.user_data.clear()
    return ConversationHandler.END


async def cb_edit_category(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    await query.edit_message_reply_markup(reply_markup=category_keyboard(idx=idx))
    return CHOOSING_CATEGORY


async def cb_choose_category(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    _, idx_str, category = query.data.split(":", 2)
    idx = int(idx_str)
    txs = context.user_data.get("txs", [])
    txs[idx]["suggested_category"] = category
    context.user_data["txs"] = txs
    await query.edit_message_text(
        format_card(txs[idx], idx=idx, total=len(txs)),
        reply_markup=confirm_keyboard(idx=idx),
        parse_mode="HTML",
    )
    return CONFIRMING


async def cb_back(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    txs = context.user_data.get("txs", [])
    await query.edit_message_text(
        format_card(txs[idx], idx=idx, total=len(txs)),
        reply_markup=confirm_keyboard(idx=idx),
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
                CallbackQueryHandler(cb_confirm, pattern=r"^confirm:"),
                CallbackQueryHandler(cb_skip, pattern=r"^skip:"),
                CallbackQueryHandler(cb_cancel, pattern=r"^cancel$"),
                CallbackQueryHandler(cb_edit_category, pattern=r"^edit_category:"),
            ],
            CHOOSING_CATEGORY: [
                CallbackQueryHandler(cb_choose_category, pattern=r"^cat:"),
                CallbackQueryHandler(cb_back, pattern=r"^back:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("repair", cmd_repair))
    app.add_handler(conv)

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
