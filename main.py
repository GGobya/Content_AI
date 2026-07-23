from __future__ import annotations

import logging

from app.config import load_config
from app.drive_client import DriveClient
from app.higgsfield_client import HiggsfieldVideoClient
from app.scenario_writer import ScenarioWriter
from app.state import StateStore
from app.telegram_bot import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = load_config()

    state = StateStore(cfg.state_file)
    drive = DriveClient(cfg.google_service_account_file, cfg.google_drive_folder_id)
    writer = ScenarioWriter(
        api_key=cfg.anthropic_api_key,
        model=cfg.anthropic_model,
        brand_name=cfg.brand_name,
        brand_description=cfg.brand_description,
    )
    hf = HiggsfieldVideoClient(
        job_type=cfg.higgsfield_job_type,
        mode=cfg.higgsfield_mode,
        aspect_ratio=cfg.higgsfield_aspect_ratio,
        duration=cfg.higgsfield_duration,
        resolution=cfg.higgsfield_resolution,
        product_id=cfg.higgsfield_product_id,
        avatar_id=cfg.higgsfield_avatar_id,
    )

    application = build_application(cfg, state, drive, writer, hf)
    logger.info("Бот запущен для бренда %s", cfg.brand_name)
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
