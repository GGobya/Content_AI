"""
Шаги 3/4/6/7 через Telegram-бота (long polling):

  /run или ежедневный джоб            — бот сначала просит ссылку на Google
                                          Диск с фото товара (см. on_text_message)
                                          и только после получения ссылки
                                          запускает тренды -> сценарии
  scn_approve:<id> / scn_reject:<id>  — согласование сценария (после шага 3)
                                          при approve -> сразу уходит в Higgsfield
  vid_approve:<id> / vid_reject:<id>  — согласование готового видео (после шага 4)
                                          при approve -> сразу публикуется в Instagram
  vid_regen:<id>                      — сгенерировать ещё один вариант видео
                                          по тому же сценарию (без повторного апрува)

Команды:
  /run   — запустить пайплайн вручную (спросит ссылку на фото -> сценарии на согласование)
  /start — приветствие/проверка что бот жив
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.config import CFG, get_logger
from app.state import STATE
from app.pipeline import run_trend_and_prompt_pipeline
from app.claude_analysis import analyze_product_photos
from app.drive_import import is_drive_link, download_from_drive
from app.higgsfield_client import generate_video_for_scenario
from app.instagram_publish import publish_reel

log = get_logger("movirevo.telegram")


# --------------------------------------------------------------------------- #
# Отправка на согласование
# --------------------------------------------------------------------------- #

async def send_scenario_for_approval(app: Application, scenario: dict):
    STATE.add_scenario(scenario["scenario_id"], {**scenario, "status": "pending"})

    text = (
        f"🎬 *Новый сценарий на согласование*\n\n"
        f"*Тренд:* {scenario.get('trend_title', '—')}\n"
        f"*Название:* {scenario.get('scenario_title', '—')}\n"
        f"*Товар:* {scenario.get('product_type', '—')}\n\n"
        f"*Реплика модели:*\n{scenario.get('speech_ru', '—')}\n\n"
        f"*Полный промпт:*\n{scenario.get('video_prompt', '—')[:900]}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"scn_approve:{scenario['scenario_id']}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"scn_reject:{scenario['scenario_id']}"),
    ]])
    await app.bot.send_message(
        chat_id=CFG.telegram_chat_id, text=text, parse_mode="Markdown", reply_markup=keyboard
    )


async def send_video_for_approval(app: Application, video_id: str, video_path, caption: str, scenario_id: str):
    STATE.add_video(video_id, {
        "status": "pending", "path": str(video_path), "caption": caption, "scenario_id": scenario_id,
    })

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Опубликовать в Instagram", callback_data=f"vid_approve:{video_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"vid_reject:{video_id}"),
        ],
        [InlineKeyboardButton("🔁 Сгенерировать ещё раз", callback_data=f"vid_regen:{video_id}")],
    ])
    with open(video_path, "rb") as f:
        await app.bot.send_video(
            chat_id=CFG.telegram_chat_id,
            video=f,
            caption=f"🎥 Видео готово. Опубликовать в Instagram?\n\n{caption[:900]}",
            reply_markup=keyboard,
        )


# --------------------------------------------------------------------------- #
# Обработчики callback-кнопок
# --------------------------------------------------------------------------- #

async def on_scenario_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, scenario_id = query.data.split(":", 1)
    scenario = STATE.get("scenarios", scenario_id)
    if not scenario:
        await query.edit_message_text("Сценарий не найден (возможно, устарел).")
        return

    if action == "scn_reject":
        STATE.update("scenarios", scenario_id, status="rejected")
        await query.edit_message_text(f"❌ Сценарий «{scenario.get('scenario_title')}» отклонён.")
        return

    STATE.update("scenarios", scenario_id, status="approved")
    await query.edit_message_text(
        f"✅ Сценарий «{scenario.get('scenario_title')}» одобрен. Отправляю в Higgsfield..."
    )

    try:
        video_path = await asyncio.to_thread(generate_video_for_scenario, scenario)
        video_id = f"vid_{scenario_id}_{int(time.time())}"
        await send_video_for_approval(
            context.application, video_id, video_path,
            caption=scenario.get("speech_ru", ""), scenario_id=scenario_id,
        )
    except Exception as e:
        log.exception("Ошибка генерации видео для %s", scenario_id)
        await context.bot.send_message(
            chat_id=CFG.telegram_chat_id,
            text=f"⚠️ Ошибка при генерации видео для «{scenario.get('scenario_title')}»: {e}",
        )


async def on_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, video_id = query.data.split(":", 1)
    video = STATE.get("videos", video_id)
    if not video:
        await query.edit_message_caption("Видео не найдено (возможно, устарело).")
        return

    if action == "vid_reject":
        STATE.update("videos", video_id, status="rejected")
        await query.edit_message_caption("❌ Видео отклонено, публикация отменена.")
        return

    if action == "vid_regen":
        scenario = STATE.get("scenarios", video.get("scenario_id"))
        if not scenario:
            await context.bot.send_message(
                chat_id=CFG.telegram_chat_id,
                text="⚠️ Не найден исходный сценарий для повторной генерации.",
            )
            return
        await context.bot.send_message(
            chat_id=CFG.telegram_chat_id,
            text=f"🔁 Генерирую ещё один вариант для «{scenario.get('scenario_title')}»...",
        )
        try:
            new_video_path = await asyncio.to_thread(generate_video_for_scenario, scenario)
            new_video_id = f"vid_{scenario['scenario_id']}_{int(time.time())}"
            await send_video_for_approval(
                context.application, new_video_id, new_video_path,
                caption=scenario.get("speech_ru", ""), scenario_id=scenario["scenario_id"],
            )
        except Exception as e:
            log.exception("Ошибка повторной генерации видео для %s", video.get("scenario_id"))
            await context.bot.send_message(
                chat_id=CFG.telegram_chat_id, text=f"⚠️ Ошибка при генерации видео: {e}",
            )
        return

    STATE.update("videos", video_id, status="approved")
    await query.edit_message_caption("✅ Одобрено. Публикую в Instagram...")

    try:
        post_url = await asyncio.to_thread(publish_reel, Path(video["path"]), video.get("caption", ""))
        STATE.update("videos", video_id, status="published", post_url=post_url)
        await context.bot.send_message(
            chat_id=CFG.telegram_chat_id, text=f"🚀 Опубликовано в Instagram: {post_url}"
        )
    except Exception as e:
        log.exception("Ошибка публикации видео %s", video_id)
        await context.bot.send_message(
            chat_id=CFG.telegram_chat_id, text=f"⚠️ Ошибка публикации в Instagram: {e}"
        )


# --------------------------------------------------------------------------- #
# Команды и ежедневный джоб
# --------------------------------------------------------------------------- #

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Контент-завод {CFG.brand_name} на связи.\n"
        f"Автозапуск каждый день в {CFG.daily_run_time} (спрошу ссылку на Google Диск с фото товара).\n"
        f"Команда /run — запустить пайплайн вручную прямо сейчас."
    )


async def request_product_photos(app: Application):
    STATE.data["awaiting_photo_link"] = True
    STATE.save()
    await app.bot.send_message(
        chat_id=CFG.telegram_chat_id,
        text=(
            "📎 Пришлите ссылку на Google Диск с фото товара для сегодняшней "
            "генерации (файл или папка, доступ «Всем, у кого есть ссылка»). "
            "Как только пришлёте — начну собирать тренды и писать сценарии."
        ),
    )


async def cmd_run_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await request_product_photos(context.application)


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    log.info("=== Запуск ежедневного пайплайна контент-завода ===")
    await request_product_photos(context.application)


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловит обычный текст (не команду) — используется только для ссылки на
    Google Диск, которую бот запросил через request_product_photos(). Всё
    остальное вне этого ожидания игнорируется."""
    if not STATE.data.get("awaiting_photo_link"):
        return

    link = (update.message.text or "").strip()
    if not is_drive_link(link):
        await update.message.reply_text(
            "Это не похоже на ссылку Google Диска. Пришлите ссылку вида https://drive.google.com/..."
        )
        return

    STATE.data["awaiting_photo_link"] = False
    STATE.save()
    await update.message.reply_text("⏳ Скачиваю фото с Google Диска...")

    try:
        photos = await asyncio.to_thread(download_from_drive, link)
    except Exception as e:
        log.exception("Ошибка скачивания с Google Диска")
        await update.message.reply_text(f"⚠️ Не удалось скачать с Google Диска: {e}")
        return

    if not photos:
        await update.message.reply_text(
            "⚠️ По ссылке не нашлось ни одного фото (jpg/png/webp). "
            "Проверьте доступ («Всем, у кого есть ссылка») и пришлите /run ещё раз."
        )
        return

    await update.message.reply_text(f"✅ Скачано {len(photos)} фото. Анализирую и собираю тренды...")

    try:
        photo_info = await asyncio.to_thread(analyze_product_photos, photos)
        scenarios = await asyncio.to_thread(run_trend_and_prompt_pipeline, photos, photo_info)
    except Exception as e:
        log.exception("Ошибка пайплайна после получения фото с Google Диска")
        await update.message.reply_text(f"⚠️ Ошибка при генерации сценариев: {e}")
        return

    if not scenarios:
        await update.message.reply_text("Не удалось сгенерировать сценарии, проверьте логи.")
        return
    for scn in scenarios:
        await send_scenario_for_approval(context.application, scn)


# --------------------------------------------------------------------------- #
# Сборка приложения
# --------------------------------------------------------------------------- #

def build_app() -> Application:
    if not CFG.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

    app = Application.builder().token(CFG.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("run", cmd_run_pipeline))
    app.add_handler(CallbackQueryHandler(on_scenario_callback, pattern=r"^scn_"))
    app.add_handler(CallbackQueryHandler(on_video_callback, pattern=r"^vid_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    run_time = datetime.strptime(CFG.daily_run_time, "%H:%M").time()
    app.job_queue.run_daily(daily_job, time=run_time)

    return app
