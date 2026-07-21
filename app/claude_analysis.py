"""
Шаг 2-3: анализ трендов и генерация видео-промптов через Claude API.
"""

import base64
import json
import mimetypes
from pathlib import Path
from datetime import datetime

import anthropic

from app.config import CFG, get_logger

log = get_logger("movirevo.claude")


def get_client() -> anthropic.Anthropic:
    if not CFG.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан")
    return anthropic.Anthropic(api_key=CFG.anthropic_api_key)


def _extract_json(message) -> str:
    raw = "".join(b.text for b in message.content if b.type == "text").strip()
    return raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def select_relevant_trends(trends: list[dict]) -> list[dict]:
    """Просит Claude выбрать N трендов, органично сочетающихся с ассортиментом бренда."""
    if not trends:
        log.warning("Список трендов пуст, нечего анализировать")
        return []

    client = get_client()
    trends_text = "\n".join(
        f"- {t['title']} (объём: {t.get('traffic', 'н/д')}, источник: {t['source']})"
        for t in trends
    )

    system = (
        "Ты — маркетолог-стратег бренда женской одежды. Твоя задача — находить "
        "актуальные новостные/культурные тренды, которые можно органично, без натяжек "
        "обыграть в коротких видео о продукте, чтобы зацепить внимание в Instagram Reels "
        "и повысить продажи на маркетплейсах WB и Ozon."
    )
    user_prompt = f"""Бренд: {CFG.brand_name}
Ассортимент: {CFG.brand_description}

Вот список актуальных трендов США за сегодня:
{trends_text}

Выбери ровно {CFG.trends_count_to_select} трендов, которые реалистично и органично
можно обыграть в коротких вертикальных видео с моделью в одежде этого бренда
(через настроение, эстетику, повод, событие, сезонность — не обязательно
буквальную тему тренда).

Верни ТОЛЬКО валидный JSON-массив без markdown-разметки, без пояснений:
[
  {{
    "trend_title": "...",
    "relevance_reason": "почему это подходит бренду, 1 предложение",
    "content_angle": "конкретный ракурс для видео, 1-2 предложения",
    "suggested_product_type": "шарф | свитер | бомбер | ветровка"
  }}
]"""

    log.info("Отправляю тренды в Claude на анализ и отбор...")
    message = client.messages.create(
        model=CFG.claude_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = _extract_json(message)
    try:
        selected = json.loads(raw)
    except json.JSONDecodeError:
        log.error("Claude вернул невалидный JSON:\n%s", raw)
        return []

    log.info("Claude отобрал %d трендов", len(selected))
    return selected


def analyze_product_photos(photos: list[Path]) -> list[dict]:
    """Просит Claude (vision) по каждому фото определить тип товара и коротко
    описать ключевые визуальные детали — чтобы сценарий и промпт для Higgsfield
    ссылались на реальную вещь с фото, а не на общую категорию."""
    if not photos:
        return []

    client = get_client()
    info = []
    for photo in photos:
        media_type = mimetypes.guess_type(photo.name)[0] or "image/jpeg"
        image_b64 = base64.standard_b64encode(photo.read_bytes()).decode("utf-8")

        log.info("Анализирую фото товара: %s", photo.name)
        message = client.messages.create(
            model=CFG.claude_model,
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": (
                        f"На фото — товар бренда {CFG.brand_name} ({CFG.brand_description}). "
                        "Определи тип товара и опиши ключевые визуальные детали (цвет, фактура, "
                        "принт, посадка) 1-2 предложениями на русском. Верни ТОЛЬКО валидный JSON "
                        'без markdown: {"product_type": "шарф | свитер | бомбер | ветровка", "description": "..."}'
                    )},
                ],
            }],
        )
        raw = _extract_json(message)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Не удалось разобрать анализ фото %s, использую заглушку", photo.name)
            parsed = {"product_type": "товар", "description": ""}
        parsed["photo_path"] = str(photo)
        info.append(parsed)

    return info


def generate_video_prompts(
    selected_trends: list[dict], product_photos: list[Path], photo_info: list[dict] | None = None,
) -> list[dict]:
    """Генерирует N сюжетных промптов для Higgsfield на основе отобранных трендов.

    photo_info (опционально) — результат analyze_product_photos(): если задан,
    фото подбирается сценарию по совпадению product_type, а описание фото
    добавляется в промпт для Higgsfield; иначе фото раздаются по кругу как раньше.
    """
    if not selected_trends:
        return []

    client = get_client()
    n = min(CFG.daily_video_count, len(selected_trends)) or CFG.daily_video_count
    trends_for_prompt = selected_trends[:n]

    system = (
        "Ты — сценарист коротких вертикальных рекламных видео (UGC-стиль) для "
        "AI-видеогенератора Higgsfield. Пишешь только на русском языке. "
        "Модель в видео всегда говорит на русском, с синхронизацией губ. "
        "Стиль — реалистичный смартфон-контент, не глянцевая студийная реклама."
    )
    user_prompt = f"""Бренд: {CFG.brand_name}
Ассортимент: {CFG.brand_description}

Отобранные тренды-поводы:
{json.dumps(trends_for_prompt, ensure_ascii=False, indent=2)}

Для каждого тренда напиши ОДИН детальный видео-промпт для Higgsfield (UGC-пресет),
на русском языке, включающий:
- внешность и типаж модели (славянская внешность, вариативный возраст 20-35)
- локацию/сеттинг, соответствующие сезону и поводу
- конкретное действие модели с товаром (шарф/свитер/бомбер/ветровка),
  демонстрирующее посадку, ткань и то, как вещь сочетается с образом
- реплику модели на русском (естественная, разговорная, 2-3 предложения,
  без клише "успей купить", без прямого упоминания скидок — органичная рекомендация)
- стиль съёмки (вертикальное видео 9:16, смартфон-стайл, естественный свет)

Верни ТОЛЬКО валидный JSON-массив без markdown:
[
  {{
    "trend_title": "...",
    "scenario_title": "короткое название сценария для внутреннего использования",
    "product_type": "шарф | свитер | бомбер | ветровка",
    "video_prompt": "полный промпт для Higgsfield одним текстом",
    "speech_ru": "реплика модели отдельным полем для контроля"
  }}
]"""

    log.info("Прошу Claude сгенерировать %d сюжетных промптов...", n)
    message = client.messages.create(
        model=CFG.claude_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = _extract_json(message)
    try:
        prompts = json.loads(raw)
    except json.JSONDecodeError:
        log.error("Claude вернул невалидный JSON для промптов:\n%s", raw)
        return []

    if not product_photos:
        log.warning("В %s не найдено фото товара — сценарии без референсного фото", CFG.photos_dir)

    used_by_type: dict[str, int] = {}
    for i, p in enumerate(prompts):
        p["scenario_id"] = f"scn_{datetime.now():%Y%m%d_%H%M%S}_{i + 1}"

        if photo_info:
            matches = [ph for ph in photo_info if ph.get("product_type") == p.get("product_type")]
            pool = matches or photo_info
            idx = used_by_type.get(p.get("product_type", ""), 0) % len(pool)
            used_by_type[p.get("product_type", "")] = idx + 1
            chosen = pool[idx]
            p["photo_path"] = chosen["photo_path"]
            if chosen.get("description"):
                p["video_prompt"] += f"\n\nДеталь товара с фото: {chosen['description']}"
        else:
            p["photo_path"] = str(product_photos[i % len(product_photos)]) if product_photos else None

    log.info("Сгенерировано %d промптов", len(prompts))
    return prompts


def load_product_photos() -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    photos = sorted(p for p in CFG.photos_dir.glob("*") if p.suffix.lower() in exts)
    log.info("Найдено %d фото товара в %s", len(photos), CFG.photos_dir)
    return photos
