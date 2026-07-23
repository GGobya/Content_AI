from __future__ import annotations

import os
from dataclasses import dataclass

import higgsfield_client
import httpx


class HiggsfieldError(RuntimeError):
    pass


@dataclass
class GenerationResult:
    video_url: str
    raw: dict


class HiggsfieldVideoClient:
    """Тонкая обёртка над официальным SDK `higgsfield_client`.

    ВАЖНО про job_type=marketing_studio_video: это готовый Higgsfield-пресет
    под рекламные/UGC-ролики (см. `higgsfield model get marketing_studio_video
    --json` в их CLI для полной схемы). На некоторых тарифах он ожидает
    заранее созданные product/avatar сущности (`higgsfield marketing-studio
    products create/list`, `avatars create/list`) — тогда пропиши их id в
    HIGGSFIELD_PRODUCT_ID/HIGGSFIELD_AVATAR_ID в .env. Если оставить пустыми,
    бот передаёт фото товара напрямую полем `image` — это наилучшее
    предположение по документации CLI, сверь и поправь при первом реальном
    запуске, если Higgsfield ответит ошибкой валидации аргументов.
    """

    def __init__(
        self,
        job_type: str,
        mode: str,
        aspect_ratio: str,
        duration: int,
        resolution: str,
        product_id: str | None = None,
        avatar_id: str | None = None,
    ):
        self._job_type = job_type
        self._mode = mode
        self._aspect_ratio = aspect_ratio
        self._duration = duration
        self._resolution = resolution
        self._product_id = product_id
        self._avatar_id = avatar_id

    async def upload_image(self, path: str) -> str:
        return await higgsfield_client.upload_file_async(path)

    def _build_arguments(self, prompt: str, image_url: str) -> dict:
        arguments: dict = {
            "prompt": prompt,
            "mode": self._mode,
            "aspect_ratio": self._aspect_ratio,
            "duration": self._duration,
            "resolution": self._resolution,
        }
        if self._product_id:
            arguments["product_ids"] = [self._product_id]
        else:
            arguments["image"] = image_url

        if self._avatar_id:
            arguments["avatars"] = [{"id": self._avatar_id, "type": "preset"}]

        return arguments

    async def submit(self, prompt: str, image_path: str) -> str:
        image_url = await self.upload_image(image_path)
        arguments = self._build_arguments(prompt, image_url)
        controller = await higgsfield_client.submit_async(self._job_type, arguments)
        return controller.request_id

    async def get_status(self, request_id: str) -> higgsfield_client.Status:
        return await higgsfield_client.status_async(request_id=request_id)

    async def get_result(self, request_id: str) -> GenerationResult:
        data = await higgsfield_client.result_async(request_id=request_id)
        return GenerationResult(video_url=_extract_video_url(data), raw=data)

    @staticmethod
    async def download_video(url: str, dest_path: str) -> str:
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        return dest_path


def _extract_video_url(data: dict) -> str:
    """Формат JSON-ответа конкретного job_type в открытой документации не
    зафиксирован — перебираем самые вероятные пути по конвенции Higgsfield/fal.
    Если ни один не подошёл, ошибка покажет реальные ключи ответа, чтобы
    сразу поправить путь здесь."""
    candidate_paths = [
        ("video", "url"),
        ("output", "video_url"),
        ("output", "video", "url"),
        ("result", "video", "url"),
    ]
    for path in candidate_paths:
        node = data
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, str):
            return node

    videos = data.get("videos")
    if isinstance(videos, list) and videos and isinstance(videos[0], dict):
        url = videos[0].get("url")
        if isinstance(url, str):
            return url

    if isinstance(data.get("url"), str):
        return data["url"]

    raise HiggsfieldError(
        "Не удалось найти ссылку на видео в ответе Higgsfield. "
        f"Доступные поля верхнего уровня: {sorted(data.keys())}. "
        "Поправь _extract_video_url() в app/higgsfield_client.py под реальный "
        "формат ответа (см. распечатанный raw в логе)."
    )
