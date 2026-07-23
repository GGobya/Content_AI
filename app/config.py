from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _split_ids(raw: str) -> set[int]:
    return {int(x) for x in raw.split(",") if x.strip()}


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_allowed_user_ids: set[int]

    anthropic_api_key: str
    anthropic_model: str

    higgsfield_job_type: str
    higgsfield_mode: str
    higgsfield_aspect_ratio: str
    higgsfield_duration: int
    higgsfield_resolution: str
    higgsfield_product_id: str | None
    higgsfield_avatar_id: str | None

    google_service_account_file: str
    google_drive_folder_id: str

    brand_name: str
    brand_description: str

    state_file: str
    download_dir: str
    output_dir: str
    poll_interval_seconds: int


def load_config() -> Config:
    missing = [
        name
        for name in ("TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY", "GOOGLE_DRIVE_FOLDER_ID")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(
            "Не заданы обязательные переменные окружения: "
            f"{', '.join(missing)}. Проверь .env (см. .env.example)."
        )

    return Config(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_allowed_user_ids=_split_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        higgsfield_job_type=os.getenv("HIGGSFIELD_JOB_TYPE", "marketing_studio_video"),
        higgsfield_mode=os.getenv("HIGGSFIELD_MODE", "ugc"),
        higgsfield_aspect_ratio=os.getenv("HIGGSFIELD_ASPECT_RATIO", "9:16"),
        higgsfield_duration=int(os.getenv("HIGGSFIELD_DURATION", "10")),
        higgsfield_resolution=os.getenv("HIGGSFIELD_RESOLUTION", "720p"),
        higgsfield_product_id=os.getenv("HIGGSFIELD_PRODUCT_ID") or None,
        higgsfield_avatar_id=os.getenv("HIGGSFIELD_AVATAR_ID") or None,
        google_service_account_file=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE", "./credentials/google-service-account.json"
        ),
        google_drive_folder_id=os.environ["GOOGLE_DRIVE_FOLDER_ID"],
        brand_name=os.getenv("BRAND_NAME", "MOVIREVO"),
        brand_description=os.getenv(
            "BRAND_DESCRIPTION", "Женская одежда: шарфы, свитера, бомберы и ветровки"
        ),
        state_file=os.getenv("STATE_FILE", "./data/state.json"),
        download_dir=os.getenv("DOWNLOAD_DIR", "./data/photos"),
        output_dir=os.getenv("OUTPUT_DIR", "./data/videos"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "20")),
    )
