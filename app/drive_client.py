from __future__ import annotations

import io
import logging
import os
import random

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class DriveClient:
    """Читает фото товаров из указанной папки на Google Диске.

    Доступ выдаётся через сервисный аккаунт: папку на Диске нужно
    расшарить (Читатель) на email сервисного аккаунта из ключа.
    """

    def __init__(self, service_account_file: str, folder_id: str):
        self._folder_id = folder_id
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def list_product_photos(self) -> list[dict]:
        """Возвращает [{id, name, mimeType}, ...] для файлов-изображений в папке."""
        files: list[dict] = []
        page_token = None
        query = f"'{self._folder_id}' in parents and trashed = false"
        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(
                f for f in response.get("files", []) if f.get("mimeType") in IMAGE_MIME_TYPES
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return files

    def download(self, file_id: str, dest_path: str) -> str:
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        request = self._service.files().get_media(fileId=file_id)
        with io.FileIO(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return dest_path

    async def pick_unused_photo(self, is_used) -> dict | None:
        """is_used: async callable(drive_file_id) -> bool. Возвращает случайное
        неиспользованное фото или None, если в папке закончились новые товары."""
        photos = self.list_product_photos()
        random.shuffle(photos)
        for photo in photos:
            if not await is_used(photo["id"]):
                return photo
        return None
