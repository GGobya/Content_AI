from __future__ import annotations

import logging
import os

import higgsfield_client as hf_sdk
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Config
from app.drive_client import DriveClient
from app.higgsfield_client import HiggsfieldVideoClient
from app.scenario_writer import ScenarioWriter
from app.state import JobStatus, StateStore

logger = logging.getLogger(__name__)

BD_CONFIG = "config"
BD_STATE = "state"
BD_DRIVE = "drive"
BD_WRITER = "writer"
BD_HF = "hf"
UD_PENDING_JOB = "pending_feedback_job_id"


def _is_allowed(cfg: Config, user_id: int) -> bool:
    if not cfg.telegram_allowed_user_ids:
        return True
    return user_id in cfg.telegram_allowed_user_ids


def _job_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Запустить генерацию", callback_data=f"approve:{job_id}"),
                InlineKeyboardButton("✏️ Правки", callback_data=f"revise:{job_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{job_id}"),
            ]
        ]
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data[BD_CONFIG]
    if not _is_allowed(cfg, update.effective_user.id):
        await update.message.reply_text("Доступ к этому боту ограничен.")
        return
    await update.message.reply_text(
        f"Привет! Я пишу сценарии рекламных видео для {cfg.brand_name} и запускаю их "
        "генерацию в Higgsfield.\n\n"
        "/new — взять следующее фото товара с Google Диска и предложить сценарий"
    )


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data[BD_CONFIG]
    if not _is_allowed(cfg, update.effective_user.id):
        await update.message.reply_text("Доступ к этому боту ограничен.")
        return

    state: StateStore = context.bot_data[BD_STATE]
    drive: DriveClient = context.bot_data[BD_DRIVE]
    writer: ScenarioWriter = context.bot_data[BD_WRITER]

    status_msg = await update.message.reply_text("Ищу новое фото товара на Google Диске...")

    photo = await drive.pick_unused_photo(state.is_photo_used)
    if photo is None:
        await status_msg.edit_text(
            "Не нашёл новых фото в папке на Google Диске — все уже использованы, "
            "либо папка пуста."
        )
        return

    product_name = os.path.splitext(photo["name"])[0]
    dest_path = os.path.join(cfg.download_dir, f"{photo['id']}_{photo['name']}")
    await status_msg.edit_text(f"Скачиваю «{product_name}»...")
    drive.download(photo["id"], dest_path)

    await status_msg.edit_text("Пишу сценарий...")
    try:
        scenario = writer.write(product_name)
    except Exception:
        logger.exception("Не удалось сгенерировать сценарий")
        await status_msg.edit_text(
            "Не получилось сгенерировать сценарий (ошибка Claude API). Попробуй /new ещё раз."
        )
        return

    job = await state.create_job(
        chat_id=update.effective_chat.id,
        drive_file_id=photo["id"],
        drive_file_name=photo["name"],
        product_name=product_name,
        photo_path=dest_path,
        scenario_text=scenario.scenario_text,
        hf_prompt=scenario.hf_prompt,
    )

    await status_msg.delete()
    with open(dest_path, "rb") as photo_file:
        sent = await update.message.reply_photo(
            photo=photo_file,
            caption=f"🎬 <b>{product_name}</b>\n\n{scenario.scenario_text}",
            parse_mode=ParseMode.HTML,
            reply_markup=_job_keyboard(job.id),
        )
    await state.update(job.id, message_id=sent.message_id)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    cfg: Config = context.bot_data[BD_CONFIG]
    if not _is_allowed(cfg, update.effective_user.id):
        await query.answer("Доступ ограничен.", show_alert=True)
        return

    action, job_id = query.data.split(":", 1)
    state: StateStore = context.bot_data[BD_STATE]
    job = await state.get(job_id)
    if job is None:
        await query.answer("Задача не найдена (возможно, бот перезапускался).", show_alert=True)
        return

    if job.status != JobStatus.AWAITING_APPROVAL:
        await query.answer("Эта задача уже обработана.", show_alert=True)
        return

    if action == "approve":
        await query.answer("Запускаю генерацию...")
        hf: HiggsfieldVideoClient = context.bot_data[BD_HF]
        await query.edit_message_caption(
            caption=f"🎬 <b>{job.product_name}</b>\n\n{job.scenario_text}\n\n"
            "⏳ Генерация запущена в Higgsfield...",
            parse_mode=ParseMode.HTML,
        )
        try:
            request_id = await hf.submit(job.hf_prompt, job.photo_path)
        except Exception:
            logger.exception("Не удалось отправить задачу в Higgsfield")
            await state.update(job.id, status=JobStatus.FAILED, error="submit_failed")
            await query.edit_message_caption(
                caption=f"🎬 <b>{job.product_name}</b>\n\n"
                "❌ Не удалось отправить задачу в Higgsfield. Проверь логи и ключ API.",
            )
            return
        await state.update(job.id, status=JobStatus.GENERATING, hf_request_id=request_id)

    elif action == "reject":
        await query.answer("Отклонено")
        await state.update(job.id, status=JobStatus.REJECTED)
        await query.edit_message_caption(
            caption=f"🎬 <b>{job.product_name}</b>\n\n{job.scenario_text}\n\n❌ Отклонено",
            parse_mode=ParseMode.HTML,
        )

    elif action == "revise":
        await query.answer()
        await state.update(job.id, status=JobStatus.AWAITING_FEEDBACK)
        context.user_data[UD_PENDING_JOB] = job.id
        await query.message.reply_text(
            "Напиши в ответном сообщении, что поправить в сценарии."
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data[BD_CONFIG]
    if not _is_allowed(cfg, update.effective_user.id):
        return

    job_id = context.user_data.get(UD_PENDING_JOB)
    if not job_id:
        return

    state: StateStore = context.bot_data[BD_STATE]
    writer: ScenarioWriter = context.bot_data[BD_WRITER]
    job = await state.get(job_id)
    if job is None or job.status != JobStatus.AWAITING_FEEDBACK:
        context.user_data.pop(UD_PENDING_JOB, None)
        return

    feedback = update.message.text
    status_msg = await update.message.reply_text("Переписываю сценарий с учётом правок...")
    try:
        scenario = writer.revise(job.product_name, job.hf_prompt, feedback)
    except Exception:
        logger.exception("Не удалось переписать сценарий")
        await status_msg.edit_text("Не получилось переписать сценарий, попробуй ещё раз.")
        return

    job = await state.update(
        job.id,
        status=JobStatus.AWAITING_APPROVAL,
        scenario_text=scenario.scenario_text,
        hf_prompt=scenario.hf_prompt,
    )
    context.user_data.pop(UD_PENDING_JOB, None)
    await status_msg.delete()

    with open(job.photo_path, "rb") as photo_file:
        sent = await update.message.reply_photo(
            photo=photo_file,
            caption=f"🎬 <b>{job.product_name}</b>\n\n{job.scenario_text}",
            parse_mode=ParseMode.HTML,
            reply_markup=_job_keyboard(job.id),
        )
    await state.update(job.id, message_id=sent.message_id)


async def poll_generating_jobs(context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg: Config = context.bot_data[BD_CONFIG]
    state: StateStore = context.bot_data[BD_STATE]
    hf: HiggsfieldVideoClient = context.bot_data[BD_HF]

    jobs = await state.list_by_status(JobStatus.GENERATING)
    for job in jobs:
        try:
            status = await hf.get_status(job.hf_request_id)
        except Exception:
            logger.exception("Не удалось получить статус задачи %s в Higgsfield", job.id)
            continue

        if isinstance(status, hf_sdk.Completed):
            try:
                result = await hf.get_result(job.hf_request_id)
                video_path = os.path.join(cfg.output_dir, f"{job.id}.mp4")
                await hf.download_video(result.video_url, video_path)
            except Exception:
                logger.exception("Не удалось скачать готовое видео для задачи %s", job.id)
                await state.update(job.id, status=JobStatus.FAILED, error="download_failed")
                await context.bot.send_message(
                    job.chat_id,
                    f"⚠️ Видео для «{job.product_name}» сгенерировано, но не скачалось. "
                    "Смотри логи бота.",
                )
                continue

            await state.update(job.id, status=JobStatus.DONE, video_path=video_path)
            with open(video_path, "rb") as video_file:
                await context.bot.send_video(
                    chat_id=job.chat_id,
                    video=video_file,
                    caption=f"✅ Готово: {job.product_name}",
                    reply_to_message_id=job.message_id,
                )

        elif isinstance(status, (hf_sdk.Failed, hf_sdk.NSFW, hf_sdk.Cancelled)):
            reason = type(status).__name__
            await state.update(job.id, status=JobStatus.FAILED, error=reason)
            await context.bot.send_message(
                job.chat_id,
                f"❌ Генерация видео для «{job.product_name}» не удалась ({reason}).",
            )
        # Queued / InProgress — просто ждём следующего опроса


def build_application(
    cfg: Config,
    state: StateStore,
    drive: DriveClient,
    writer: ScenarioWriter,
    hf: HiggsfieldVideoClient,
) -> Application:
    application = Application.builder().token(cfg.telegram_bot_token).build()
    application.bot_data[BD_CONFIG] = cfg
    application.bot_data[BD_STATE] = state
    application.bot_data[BD_DRIVE] = drive
    application.bot_data[BD_WRITER] = writer
    application.bot_data[BD_HF] = hf

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("new", cmd_new))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if application.job_queue is not None:
        application.job_queue.run_repeating(
            poll_generating_jobs, interval=cfg.poll_interval_seconds, first=cfg.poll_interval_seconds
        )

    return application
