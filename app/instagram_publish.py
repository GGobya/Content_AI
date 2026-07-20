"""
Шаг 6: публикация одобренного видео в Instagram как Reels через Meta Graph API.

Требования:
  - Instagram Business/Creator аккаунт, привязанный к Facebook Page
  - Long-lived access token с правами instagram_content_publish
  - IG_BUSINESS_ACCOUNT_ID (Instagram Business Account ID, не username)
"""

import time
from pathlib import Path

import requests

from app.config import CFG, get_logger
from app.storage import upload_video_public

log = get_logger("movirevo.instagram")

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def publish_reel(video_path: Path, caption: str) -> str:
    if not CFG.ig_access_token or not CFG.ig_business_account_id:
        raise RuntimeError("IG_ACCESS_TOKEN / IG_BUSINESS_ACCOUNT_ID не заданы")

    public_video_url = upload_video_public(video_path)

    log.info("Создаю контейнер Reels в Instagram...")
    create_resp = requests.post(
        f"{GRAPH_BASE}/{CFG.ig_business_account_id}/media",
        data={
            "media_type": "REELS",
            "video_url": public_video_url,
            "caption": caption,
            "access_token": CFG.ig_access_token,
        },
        timeout=60,
    )
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    log.info("Жду обработки видео Instagram (container_id=%s)...", creation_id)
    for _ in range(30):
        status_resp = requests.get(
            f"{GRAPH_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": CFG.ig_access_token},
            timeout=30,
        )
        status_resp.raise_for_status()
        code = status_resp.json().get("status_code")
        log.info("Instagram media status: %s", code)
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError("Instagram сообщил об ошибке обработки видео")
        time.sleep(10)
    else:
        raise TimeoutError("Instagram не обработал видео вовремя")

    log.info("Публикую контейнер...")
    publish_resp = requests.post(
        f"{GRAPH_BASE}/{CFG.ig_business_account_id}/media_publish",
        data={"creation_id": creation_id, "access_token": CFG.ig_access_token},
        timeout=60,
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]
    return f"https://www.instagram.com/reel/{media_id}/"
