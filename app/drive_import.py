"""
Шаг 3 (перед генерацией промптов, опционально): скачивание фото товара по
ссылке на Google Диск, присланной пользователем в Telegram.

Использует gdown — скачивание публичных файлов/папок Google Диска без
OAuth, по обычной ссылке "Доступно всем, у кого есть ссылка". Своего
Google API-ключа не требует.
"""

import shutil
from pathlib import Path

import gdown

from app.config import CFG, get_logger

log = get_logger("movirevo.drive_import")

_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def is_drive_link(text: str) -> bool:
    return "drive.google.com" in text


def download_from_drive(link: str) -> list[Path]:
    """Скачивает фото (файл или папку) по ссылке на Google Диск в
    photos/_incoming (старое содержимое этой папки предварительно чистится).
    Возвращает список путей к скачанным изображениям."""
    target_dir = CFG.photos_dir / "_incoming"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    log.info("Скачиваю с Google Диска: %s", link)
    if "/folders/" in link:
        gdown.download_folder(url=link, output=str(target_dir), quiet=True, use_cookies=False)
    else:
        gdown.download(url=link, output=f"{target_dir}/", quiet=True, fuzzy=True)

    photos = sorted(p for p in target_dir.rglob("*") if p.suffix.lower() in _PHOTO_EXTS)
    log.info("Скачано %d фото с Google Диска", len(photos))
    return photos
