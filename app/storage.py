"""
Instagram Graph API скачивает видео САМ по публичному URL — файлы напрямую
не принимает. Поэтому перед публикацией видео нужно временно загрузить
в публичный object storage (S3 / Cloudflare R2 / GCS) и получить прямую ссылку.

Реализован S3-совместимый провайдер (подходит и для AWS S3, и для Cloudflare R2,
т.к. R2 имеет S3-совместимый API — просто укажите свой endpoint через boto3 config
при необходимости).
"""

from pathlib import Path

from app.config import CFG, get_logger

log = get_logger("movirevo.storage")


def upload_video_public(video_path: Path) -> str:
    """Загружает видео в S3-совместимый бакет, возвращает публичный URL."""
    if CFG.storage_provider not in ("s3", "r2"):
        raise NotImplementedError(
            f"STORAGE_PROVIDER='{CFG.storage_provider}' не реализован. "
            "Поддерживаются: s3, r2 (S3-совместимый API)."
        )

    if not (CFG.s3_bucket and CFG.s3_access_key and CFG.s3_secret_key and CFG.s3_public_base_url):
        raise RuntimeError(
            "Заполните S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY, S3_PUBLIC_BASE_URL в .env "
            "для загрузки видео в публичное хранилище."
        )

    import boto3  # локальный импорт, чтобы boto3 не был жёсткой зависимостью, если не используется

    s3 = boto3.client(
        "s3",
        region_name=CFG.s3_region,
        aws_access_key_id=CFG.s3_access_key,
        aws_secret_access_key=CFG.s3_secret_key,
    )
    key = f"movirevo-reels/{video_path.name}"
    log.info("Загружаю %s в S3-бакет %s...", video_path.name, CFG.s3_bucket)
    s3.upload_file(
        str(video_path), CFG.s3_bucket, key,
        ExtraArgs={"ContentType": "video/mp4", "ACL": "public-read"},
    )
    public_url = f"{CFG.s3_public_base_url.rstrip('/')}/{key}"
    log.info("Видео доступно по адресу: %s", public_url)
    return public_url
