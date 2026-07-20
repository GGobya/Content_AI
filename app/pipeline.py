"""
Оркестрация шагов 1-3: тренды -> отбор Claude -> сюжетные промпты.
Генерация видео и публикация запускаются из telegram_bot.py по согласованию,
чтобы человек оставался в контуре перед каждой тратой кредитов/бюджета.
"""

from app.config import get_logger
from app.trends import fetch_all_trends
from app.claude_analysis import select_relevant_trends, generate_video_prompts, load_product_photos

log = get_logger("movirevo.pipeline")


def run_trend_and_prompt_pipeline() -> list[dict]:
    log.info("=== Шаг 1: сбор трендов ===")
    trends = fetch_all_trends()

    log.info("=== Шаг 2: отбор релевантных трендов через Claude ===")
    selected = select_relevant_trends(trends)

    log.info("=== Шаг 3: генерация сюжетных промптов ===")
    photos = load_product_photos()
    scenarios = generate_video_prompts(selected, photos)

    return scenarios
