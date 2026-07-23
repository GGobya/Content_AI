from __future__ import annotations

from dataclasses import dataclass

from anthropic import Anthropic

SYSTEM_PROMPT_TEMPLATE = """\
Ты — креативный директор бренда женской одежды {brand_name} ({brand_description}).
Ты пишешь сценарии для коротких вертикальных видео (9:16, 10-20 секунд) в стиле UGC \
(как будто обычная девушка снимает видео на телефон), которые генерируются нейросетью Higgsfield \
из фото товара. Видео используются как рекламный контент для увеличения продаж на Wildberries и Ozon.

Требования к каждому сценарию:
- Речь модели — только на русском языке, естественная, разговорная, без канцелярита и без \
преувеличенных рекламных штампов ("невероятный", "потрясающий").
- Модель — славянской внешности, живая, узнаваемая деталь образа/локации, а не стерильная студия.
- Чётко называется конкретная деталь товара (материал, крой, для чего носить), которая видна на фото.
- Формат — вертикальное видео, ручная камера/смартфон-стайл, без глянца.
- Тон — как совет подруги, а не рекламный ролик.

Ты всегда отвечаешь СТРОГО в виде JSON-объекта без markdown-обёртки, с двумя полями:
{{
  "scenario_text": "человекочитаемое краткое описание сценария на русском для показа человеку \
на согласование в Telegram (2-4 предложения: локация/действие + реплика модели в кавычках)",
  "hf_prompt": "детальный промпт на русском для Higgsfield: внешность модели, локация, действие, \
как показывается товар, точная реплика для липсинка, стиль съёмки, длительность"
}}
"""


@dataclass
class ScenarioResult:
    scenario_text: str
    hf_prompt: str


class ScenarioWriter:
    def __init__(self, api_key: str, model: str, brand_name: str, brand_description: str):
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            brand_name=brand_name, brand_description=brand_description
        )

    def write(self, product_name: str, extra_notes: str = "") -> ScenarioResult:
        user_prompt = (
            f"Товар: {product_name}\n"
            f"Дополнительные заметки: {extra_notes or 'нет'}\n\n"
            "Напиши сценарий рекламного видео для этого товара."
        )
        return self._request(user_prompt)

    def revise(self, product_name: str, previous_hf_prompt: str, feedback: str) -> ScenarioResult:
        user_prompt = (
            f"Товар: {product_name}\n"
            f"Предыдущий промпт для Higgsfield:\n{previous_hf_prompt}\n\n"
            f"Правки от заказчика: {feedback}\n\n"
            "Перепиши сценарий с учётом этих правок."
        )
        return self._request(user_prompt)

    def _request(self, user_prompt: str) -> ScenarioResult:
        import json

        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        data = json.loads(raw_text)
        return ScenarioResult(scenario_text=data["scenario_text"], hf_prompt=data["hf_prompt"])
