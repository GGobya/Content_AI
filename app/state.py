"""
Простое персистентное состояние между шагами пайплайна.
Хранит очередь сценариев и видео в json-файле (state.json).
Для продакшена с несколькими воркерами замените на Redis/SQLite —
интерфейс класса State специально узкий, чтобы замена была лёгкой.
"""

import json
from pathlib import Path
from typing import Optional

from app.config import CFG, get_logger

log = get_logger("movirevo.state")


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"scenarios": {}, "videos": {}}
        if self.path.exists() and self.path.read_text(encoding="utf-8").strip():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                log.exception("Не удалось прочитать state file, начинаю с чистого листа")

    def save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_scenario(self, scenario_id: str, payload: dict):
        self.data.setdefault("scenarios", {})[scenario_id] = payload
        self.save()

    def add_video(self, video_id: str, payload: dict):
        self.data.setdefault("videos", {})[video_id] = payload
        self.save()

    def get(self, bucket: str, item_id: str) -> Optional[dict]:
        return self.data.get(bucket, {}).get(item_id)

    def update(self, bucket: str, item_id: str, **fields):
        if item_id in self.data.get(bucket, {}):
            self.data[bucket][item_id].update(fields)
            self.save()

    def pending(self, bucket: str) -> dict:
        return {
            k: v for k, v in self.data.get(bucket, {}).items()
            if v.get("status") == "pending"
        }


STATE = State(CFG.state_file)
