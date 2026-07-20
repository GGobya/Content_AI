"""
Базовые тесты для app.state.State — запуск: pytest tests/
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.state import State


def test_add_and_get_scenario(tmp_path):
    state = State(tmp_path / "state.json")
    state.add_scenario("scn_1", {"status": "pending", "title": "test"})
    assert state.get("scenarios", "scn_1")["title"] == "test"


def test_update_scenario(tmp_path):
    state = State(tmp_path / "state.json")
    state.add_scenario("scn_1", {"status": "pending"})
    state.update("scenarios", "scn_1", status="approved")
    assert state.get("scenarios", "scn_1")["status"] == "approved"


def test_persists_to_disk(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.add_video("vid_1", {"status": "pending"})
    assert path.exists()
    reloaded = State(path)
    assert reloaded.get("videos", "vid_1")["status"] == "pending"


def test_pending_filter(tmp_path):
    state = State(tmp_path / "state.json")
    state.add_scenario("scn_1", {"status": "pending"})
    state.add_scenario("scn_2", {"status": "approved"})
    pending = state.pending("scenarios")
    assert list(pending.keys()) == ["scn_1"]
