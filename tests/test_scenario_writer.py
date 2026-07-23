import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.scenario_writer import ScenarioWriter


def _fake_message(payload: dict):
    block = SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(content=[block])


def test_write_parses_json_response():
    writer = ScenarioWriter(
        api_key="test-key",
        model="claude-sonnet-5",
        brand_name="MOVIREVO",
        brand_description="Женская одежда",
    )
    writer._client = MagicMock()
    writer._client.messages.create.return_value = _fake_message(
        {"scenario_text": "Девушка на улице показывает шарф.", "hf_prompt": "Detailed prompt"}
    )

    result = writer.write("Шарф бежевый")

    assert result.scenario_text == "Девушка на улице показывает шарф."
    assert result.hf_prompt == "Detailed prompt"
    call_kwargs = writer._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert "Шарф бежевый" in call_kwargs["messages"][0]["content"]


def test_revise_includes_feedback_in_prompt():
    writer = ScenarioWriter(
        api_key="test-key",
        model="claude-sonnet-5",
        brand_name="MOVIREVO",
        brand_description="Женская одежда",
    )
    writer._client = MagicMock()
    writer._client.messages.create.return_value = _fake_message(
        {"scenario_text": "Обновлённый сценарий.", "hf_prompt": "Updated prompt"}
    )

    result = writer.revise("Свитер серый", "old prompt", "сделай динамичнее")

    assert result.scenario_text == "Обновлённый сценарий."
    call_kwargs = writer._client.messages.create.call_args.kwargs
    assert "сделай динамичнее" in call_kwargs["messages"][0]["content"]
