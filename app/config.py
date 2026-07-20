"""
Конфигурация контент-завода MOVIREVO.
Все значения читаются из переменных окружения (.env). См. .env.example.
"""

import os
import logging
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


log = get_logger("movirevo.config")


@dataclass
class Config:
    # --- Claude / Anthropic ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    # --- Telegram ---
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Higgsfield ---
    # Базовый URL и заголовок авторизации сверены с исходниками официального
    # SDK (github.com/higgsfield-ai/higgsfield-client) — см. комментарий в
    # app/higgsfield_client.py. HIGGSFIELD_APPLICATION — путь модели для
    # генерации видео, значение по умолчанию НЕ подтверждено официально.
    higgsfield_api_key: str = os.getenv("HIGGSFIELD_API_KEY", "")
    higgsfield_api_secret: str = os.getenv("HIGGSFIELD_API_SECRET", "")
    higgsfield_api_base: str = os.getenv("HIGGSFIELD_API_BASE", "https://platform.higgsfield.ai")
    higgsfield_application: str = os.getenv("HIGGSFIELD_APPLICATION", "higgsfield/marketing-studio/video")
    higgsfield_video_timeout_s: int = int(os.getenv("HIGGSFIELD_VIDEO_TIMEOUT_S", "600"))
    higgsfield_poll_interval_s: int = int(os.getenv("HIGGSFIELD_POLL_INTERVAL_S", "10"))

    # --- Trendsee (опционально) ---
    trendsee_api_key: str = os.getenv("TRENDSEE_API_KEY", "")

    # --- Instagram (Meta Graph API) ---
    ig_access_token: str = os.getenv("IG_ACCESS_TOKEN", "")
    ig_business_account_id: str = os.getenv("IG_BUSINESS_ACCOUNT_ID", "")

    # --- Публичный хостинг видео для Instagram (S3 / R2 / GCS) ---
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "s3")  # s3 | r2 | gcs
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_region: str = os.getenv("S3_REGION", "eu-central-1")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "")
    s3_public_base_url: str = os.getenv("S3_PUBLIC_BASE_URL", "")  # напр. https://cdn.movirevo.ru

    # --- Пути ---
    photos_dir: Path = Path(os.getenv("PHOTOS_DIR", "./photos"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "./output"))
    state_file: Path = Path(os.getenv("STATE_FILE", "./state.json"))

    # --- Бренд ---
    brand_name: str = os.getenv("BRAND_NAME", "MOVIREVO")
    brand_description: str = os.getenv(
        "BRAND_DESCRIPTION",
        "Женская одежда: шарфы, свитера, бомберы и ветровки. "
        "Продажи на маркетплейсах Wildberries и Ozon.",
    )
    daily_video_count: int = int(os.getenv("DAILY_VIDEO_COUNT", "3"))
    trends_count_to_select: int = int(os.getenv("TRENDS_COUNT_TO_SELECT", "5"))

    # --- Расписание ---
    daily_run_time: str = os.getenv("DAILY_RUN_TIME", "09:00")  # HH:MM, серверное время

    def validate(self, require_all: bool = False):
        required = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_CHAT_ID": self.telegram_chat_id,
            "HIGGSFIELD_API_KEY": self.higgsfield_api_key,
            "HIGGSFIELD_API_SECRET": self.higgsfield_api_secret,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            msg = f"Не заданы переменные окружения: {missing}"
            if require_all:
                raise RuntimeError(msg)
            log.warning(msg + " — соответствующие шаги пайплайна будут падать до заполнения .env")

        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


CFG = Config()
