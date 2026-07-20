"""
Шаги 4/6/7 через Telegram-бота (long polling):

  scn_approve:<id> / scn_reject:<id>  — согласование сценария (после шага 3)
                                          при approve -> сразу уходит в Higgsfield
  vid_approve:<id> / vid_reject:<id>  — согласование готового видео (после шага 4)
                                          при approve -> сразу публикуется в Instagram

Команды:
  /run   — запустить пайплайн вручную (тренды -> сценарии -> отправка на согласование)
  /start — приветствие/проверка что бот жив
"""

from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from app.config import CFG, get_logger
from app.state import STATE
from app.pipeline import run_trend_and_prompt_pipeline
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


async def send_video_for_approval(app: Application, video_id: str, video_path, caption: str):
    STATE.add_video(video_id, {"status": "pending", "path": str(video_path), "caption": caption})

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Опубликовать в Instagram", callback_data=f"vid_approve:{video_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"vid_reject:{video_id}"),
    ]])
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
        video_path = generate_video_for_scenario(scenario)
        video_id = f"vid_{scenario_id}"
        await send_video_for_approval(
            context.application, video_id, video_path, caption=scenario.get("speech_ru", "")
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

    STATE.update("videos", video_id, status="approved")
    await query.edit_message_caption("✅ Одобрено. Публикую в Instagram...")

    try:
        post_url = publish_reel(__import__("pathlib").Path(video["path"]), video.get("caption", ""))
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
        f"Автозапуск каждый день в {CFG.daily_run_time}.\n"
        f"Команда /run — запустить пайплайн вручную прямо сейчас."
    )


async def cmd_run_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запускаю пайплайн: собираю тренды и генерирую сценарии...")
    scenarios = run_trend_and_prompt_pipeline()
    if not scenarios:
        await update.message.reply_text("Не удалось сгенерировать сценарии, проверьте логи.")
        return
    for scn in scenarios:
        await send_scenario_for_approval(context.application, scn)


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    log.info("=== Запуск ежедневного пайплайна контент-завода ===")
    scenarios = run_trend_and_prompt_pipeline()
    if not scenarios:
        await context.bot.send_message(
            chat_id=CFG.telegram_chat_id,
            text="⚠️ Не удалось сгенерировать сценарии сегодня, проверьте логи.",
        )
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

    run_time = datetime.strptime(CFG.daily_run_time, "%H:%M").time()
    app.job_queue.run_daily(daily_job, time=run_time)

    return app
