from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class JobStatus(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_FEEDBACK = "awaiting_feedback"
    GENERATING = "generating"
    DONE = "done"
    FAILED = "failed"
    REJECTED = "rejected"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    chat_id: int
    status: str
    drive_file_id: str
    drive_file_name: str
    product_name: str
    photo_path: str
    scenario_text: str = ""
    hf_prompt: str = ""
    message_id: int | None = None
    hf_request_id: str | None = None
    video_path: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(**data)


class StateStore:
    """Плоское JSON-хранилище задач бота. Переживает перезапуски процесса."""

    def __init__(self, path: str):
        self._path = path
        self._lock = asyncio.Lock()
        self._jobs: dict[str, Job] = {}
        self._used_drive_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, encoding="utf-8") as f:
            raw = json.load(f)
        self._jobs = {jid: Job.from_dict(j) for jid, j in raw.get("jobs", {}).items()}
        self._used_drive_ids = set(raw.get("used_drive_ids", []))

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        tmp_path = f"{self._path}.tmp"
        payload = {
            "jobs": {jid: job.to_dict() for jid, job in self._jobs.items()},
            "used_drive_ids": sorted(self._used_drive_ids),
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._path)

    async def create_job(
        self,
        *,
        chat_id: int,
        drive_file_id: str,
        drive_file_name: str,
        product_name: str,
        photo_path: str,
        scenario_text: str,
        hf_prompt: str,
    ) -> Job:
        async with self._lock:
            job = Job(
                id=str(uuid.uuid4()),
                chat_id=chat_id,
                status=JobStatus.AWAITING_APPROVAL,
                drive_file_id=drive_file_id,
                drive_file_name=drive_file_name,
                product_name=product_name,
                photo_path=photo_path,
                scenario_text=scenario_text,
                hf_prompt=hf_prompt,
            )
            self._jobs[job.id] = job
            self._used_drive_ids.add(drive_file_id)
            self._save()
            return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **fields) -> Job:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in fields.items():
                setattr(job, key, value)
            job.updated_at = _now()
            self._save()
            return job

    async def list_by_status(self, status: str) -> list[Job]:
        async with self._lock:
            return [j for j in self._jobs.values() if j.status == status]

    async def is_photo_used(self, drive_file_id: str) -> bool:
        async with self._lock:
            return drive_file_id in self._used_drive_ids
