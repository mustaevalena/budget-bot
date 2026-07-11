import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CONFIRMING
from keyboards import confirm_keyboard, format_card
from services.categorize import classify_transactions
from services.claude import parse_screenshot

logger = logging.getLogger(__name__)

# bot_data key: "album:{media_group_id}" → {"chat_id", "user_id", "images": [...bytes], "msg_id"}
_ALBUM_DELAY = 2.0  # seconds to wait for all album photos to arrive


async def _process_images(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job: process all buffered images from an album."""
    job = context.job
    group_key = job.name
    data = context.bot_data.pop(group_key, None)
    if not data:
        return

    chat_id = data["chat_id"]
    user_id = data["user_id"]
    loading_msg_id = data["msg_id"]

    try:
        await _do_process_images(context, chat_id, user_id, loading_msg_id, data["images"])
    except Exception as e:
        logger.error("_process_images failed: %s", e, exc_info=True)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=loading_msg_id,
                text=f"❌ Ошибка обработки: {e}",
            )
        except Exception:
            pass


async def _do_process_images(context, chat_id, user_id, loading_msg_id, images) -> None:
    all_txs = []
    for image_bytes in images:
        try:
            txs = parse_screenshot(image_bytes)
            all_txs.extend(txs)
        except Exception as e:
            logger.error("Claude error on album image: %s", e)

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=loading_msg_id,
        text=f"🔍 Распознано транзакций: {len(all_txs)}" if all_txs else "❌ Транзакций не найдено.",
    )

    if not all_txs:
        return

    auto_saved, pending = classify_transactions(all_txs)

    if not pending:
        if auto_saved:
            lines = "\n".join(f"• {t['date']} {t['merchant']} {t['amount']} RSD → {t['suggested_category']}" for t in auto_saved)
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=loading_msg_id,
                text=f"✅ Записано ({len(auto_saved)}):\n{lines}",
            )
        else:
            await context.bot.delete_message(chat_id=chat_id, message_id=loading_msg_id)
        return

    # application.user_data is a mappingproxy — can't add new keys, but can modify existing dict.
    # handle_photo always touches context.user_data first, so user_id key is guaranteed to exist.
    user_data = context.application.user_data[user_id]
    existing = user_data.get("txs", [])
    user_data["txs"] = existing + pending
    if "tx_idx" not in user_data:
        user_data["tx_idx"] = 0
    if "auto_saved" not in user_data:
        user_data["auto_saved"] = []
    user_data["auto_saved"].extend(auto_saved)

    # Show current card with updated total (queue may have grown if more album photos merged in)
    all_txs = user_data["txs"]
    current_idx = user_data["tx_idx"]
    current_tx = all_txs[current_idx]
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=loading_msg_id,
        text=format_card(current_tx, idx=current_idx, total=len(all_txs)),
        reply_markup=confirm_keyboard(idx=current_idx, merge_candidate=current_tx.get("merge_candidate")),
        parse_mode="HTML",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    media_group_id = update.message.media_group_id

    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = bytes(await file.download_as_bytearray())

    if media_group_id:
        # Album: buffer the image and (re)schedule processing
        group_key = f"album:{media_group_id}"

        if group_key not in context.bot_data:
            # First photo in the album — send loading message and buffer
            msg = await update.message.reply_text("🔍 Распознаю транзакции...")
            context.bot_data[group_key] = {
                "chat_id": update.effective_chat.id,
                "user_id": update.effective_user.id,
                "msg_id": msg.message_id,
                "images": [image_bytes],
            }
        else:
            # Subsequent photo — just add to buffer
            context.bot_data[group_key]["images"].append(image_bytes)

        # Touch context.user_data so application.user_data[user_id] exists when job fires
        context.user_data.setdefault("_ready", True)

        # Cancel existing job and reschedule (wait for more photos)
        current_jobs = context.job_queue.get_jobs_by_name(group_key)
        for job in current_jobs:
            job.schedule_removal()
        context.job_queue.run_once(_process_images, _ALBUM_DELAY, name=group_key)

        return CONFIRMING

    # Single photo — process immediately
    msg = await update.message.reply_text("🔍 Распознаю транзакции...")

    try:
        txs = parse_screenshot(image_bytes)
    except Exception as e:
        logger.error("Claude error: %s", e)
        await msg.edit_text("❌ Не удалось распознать транзакции. Попробуй ещё раз или введи текстом.")
        return -1

    if not txs:
        await msg.edit_text("❌ Транзакций не найдено на скрине.")
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

    await msg.edit_text(
        format_card(pending[0], idx=0, total=len(pending)),
        reply_markup=confirm_keyboard(idx=0, merge_candidate=pending[0].get("merge_candidate")),
        parse_mode="HTML",
    )
    return CONFIRMING
