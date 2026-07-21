"""
Шаг 4: интеграция с Higgsfield — загрузка фото товара, запуск генерации видео,
поллинг статуса и скачивание результата.

ВАЖНО ДЛЯ CLAUDE CODE / РАЗРАБОТЧИКА:
REST-протокол ниже сверен с исходным кодом официального Python SDK
(https://github.com/higgsfield-ai/higgsfield-client, main, июль 2026) —
docs.higgsfield.ai недоступен из этого окружения (403 на прямой фетч), поэтому
исходники SDK были единственным надёжным источником. ПОДТВЕРЖДЕНО оттуда:
  - базовый URL: https://platform.higgsfield.ai (НЕ api.higgsfield.ai/v1,
    как было в первой версии этого файла)
  - авторизация: заголовок `Authorization: Key {api_key}:{api_secret}`
    (НЕ `Bearer {token}` — нужен отдельный HIGGSFIELD_API_SECRET в .env)
  - загрузка файла: POST /files/generate-upload-url с телом {"content_type": ...}
    -> {"upload_url", "public_url"}; затем PUT байтов файла на upload_url с
    заголовком Content-Type; референсом на фото далее служит public_url,
    а НЕ media_id, как предполагалось раньше
  - запуск генерации: POST {BASE_URL}/{application} с телом = параметры модели
    напрямую (без обёртки {"params": {...}}); ответ содержит
    {"request_id", "status_url", "response_url"}
  - статус задачи — GET status_url, поле "status" со значениями (не "state",
    как было в первой версии файла): "queued" | "in_progress" | "completed" |
    "failed" | "nsfw" | "canceled". Финальный результат — отдельным GET на
    response_url.

ОБНОВЛЕНИЕ (июль 2026): `HIGGSFIELD_APPLICATION="higgsfield/marketing-studio/video"`
дал `404 Not Found` при первом реальном запуске. По github.com/higgsfield-ai/skills
(higgsfield-generate/SKILL.md — их же CLI и MCP-документация) правильный
идентификатор модели — плоская строка `marketing_studio_video`, без префикса
`higgsfield/` и суффикса `/video`; это тот же идентификатор, что используется
и в MCP-инструменте generate_video, и в CLI (`higgsfield generate create
marketing_studio_video ...`). Обновлено в .env.example и app/config.py.

ВСЁ ЕЩЁ НЕ ПОДТВЕРЖДЕНО (сверить в личном кабинете https://cloud.higgsfield.ai
или в поддержке Higgsfield, если снова будет ошибка):
  - точное имя поля с URL готового видео внутри response_url — _extract_video_url()
    ниже проверяет несколько вероятных вариантов и явно падает с понятной
    ошибкой, если ни один не подошёл, чтобы это было легко продиагностировать
"""

import mimetypes
import time
from pathlib import Path

import requests

from app.config import CFG, get_logger

log = get_logger("movirevo.higgsfield")

DONE_STATUSES = {"completed", "failed", "nsfw", "canceled"}


def _headers(json_body: bool = True) -> dict:
    headers = {"Authorization": f"Key {CFG.higgsfield_api_key}:{CFG.higgsfield_api_secret}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def upload_photo(photo_path: Path) -> str:
    """Загружает референсное фото товара в Higgsfield, возвращает публичный URL."""
    content_type = mimetypes.guess_type(photo_path.name)[0] or "application/octet-stream"
    log.info("Запрашиваю upload URL для %s...", photo_path.name)
    resp = requests.post(
        f"{CFG.higgsfield_api_base}/files/generate-upload-url",
        headers=_headers(),
        json={"content_type": content_type},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    upload_url = data["upload_url"]
    public_url = data["public_url"]

    log.info("Загружаю фото %s в Higgsfield...", photo_path.name)
    put_resp = requests.put(
        upload_url,
        data=photo_path.read_bytes(),
        headers={"Content-Type": content_type},
        timeout=60,
    )
    put_resp.raise_for_status()
    log.info("Фото загружено: %s", public_url)
    return public_url


def submit_video_job(scenario: dict) -> dict:
    """Отправляет промпт + фото товара, возвращает job info (включая request_id)."""
    photo_path = scenario.get("photo_path")
    photo_url = upload_photo(Path(photo_path)) if photo_path else None

    arguments = {
        "prompt": scenario["video_prompt"],
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "generate_audio": True,
        "medias": [{"role": "image", "value": photo_url}] if photo_url else [],
    }
    log.info("Отправляю задачу генерации видео для сценария %s", scenario["scenario_id"])
    resp = requests.post(
        f"{CFG.higgsfield_api_base}/{CFG.higgsfield_application}",
        headers=_headers(),
        json=arguments,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    job = {
        "request_id": data["request_id"],
        "status_url": data["status_url"],
        "response_url": data.get("response_url", data["status_url"]),
        "scenario_id": scenario["scenario_id"],
    }
    log.info("Задача создана, request_id=%s", job["request_id"])
    return job


def _extract_video_url(result: dict) -> str:
    if isinstance(result.get("video"), dict) and result["video"].get("url"):
        return result["video"]["url"]
    if result.get("video_url"):
        return result["video_url"]
    if result.get("url"):
        return result["url"]
    raise RuntimeError(
        f"Не удалось найти URL видео в ответе Higgsfield: {result!r}. "
        "Проверьте реальную форму ответа response_url в личном кабинете/логах "
        "и поправьте _extract_video_url() в app/higgsfield_client.py."
    )


def poll_and_download(job: dict) -> Path:
    """Опрашивает статус задачи до готовности и скачивает mp4 в OUTPUT_DIR."""
    elapsed = 0
    timeout_s = CFG.higgsfield_video_timeout_s
    interval_s = CFG.higgsfield_poll_interval_s

    while elapsed < timeout_s:
        resp = requests.get(job["status_url"], headers=_headers(json_body=False), timeout=30)
        resp.raise_for_status()
        status = resp.json().get("status")
        log.info("Задача %s: статус=%s (%ds/%ds)", job["request_id"], status, elapsed, timeout_s)

        if status == "completed":
            result_resp = requests.get(job["response_url"], headers=_headers(json_body=False), timeout=30)
            result_resp.raise_for_status()
            video_url = _extract_video_url(result_resp.json())
            out_path = CFG.output_dir / f"{job.get('scenario_id', job['request_id'])}.mp4"
            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()
            out_path.write_bytes(video_resp.content)
            log.info("Видео сохранено: %s", out_path)
            return out_path

        if status in ("failed", "nsfw", "canceled"):
            raise RuntimeError(f"Higgsfield задача {job['request_id']} завершилась со статусом {status}")

        time.sleep(interval_s)
        elapsed += interval_s

    raise TimeoutError(f"Higgsfield задача {job['request_id']} не завершилась за {timeout_s}s")


def generate_video_for_scenario(scenario: dict) -> Path:
    """Утилита-обёртка: submit + poll в одну функцию для вызова из пайплайна/бота."""
    job = submit_video_job(scenario)
    return poll_and_download(job)
