"""
Оркестрация шагов 1-3: тренды -> отбор Claude -> сюжетные промпты.
Генерация видео и публикация запускаются из telegram_bot.py по согласованию,
чтобы человек оставался в контуре перед каждой тратой кредитов/бюджета.
"""

from pathlib import Path

from app.config import get_logger
from app.trends import fetch_all_trends
from app.claude_analysis import (
    select_relevant_trends,
    generate_video_prompts,
    analyze_product_photos,
    load_product_photos,
)

log = get_logger("movirevo.pipeline")


def run_trend_and_prompt_pipeline(
    photos: list[Path] | None = None, photo_info: list[dict] | None = None,
) -> list[dict]:
    """photos/photo_info — фото товара для этого запуска (например, только что
    скачанные с Google Диска по ссылке от пользователя, вместе с их анализом
    через analyze_product_photos). Если не заданы — берутся локальные фото
    из PHOTOS_DIR без анализа, как раньше."""
    log.info("=== Шаг 1: сбор трендов ===")
    trends = fetch_all_trends()

    log.info("=== Шаг 2: отбор релевантных трендов через Claude ===")
    selected = select_relevant_trends(trends)

    log.info("=== Шаг 3: генерация сюжетных промптов ===")
    if photos is None:
        photos = load_product_photos()
    scenarios = generate_video_prompts(selected, photos, photo_info=photo_info)

    return scenarios
