# CLAUDE.md

Контекст для Claude Code при доработке этого репозитория.

## Что это

Telegram-бот для бренда женской одежды **MOVIREVO**: пишет сценарии коротких
вертикальных (9:16) UGC-рекламных видео через Claude API, берёт фото товаров
с Google Диска, после approve в Telegram отправляет промпт в Higgsfield на
генерацию видео и присылает готовый ролик обратно в чат. Подробный флоу и
инструкции по установке — в `README.md`.

## Из чего собрано

- `python-telegram-bot` v21 (asyncio, `Application` + `JobQueue` для фонового
  опроса статуса генерации).
- `anthropic` SDK — сценарии пишет Claude (`app/scenario_writer.py`), модель
  задаётся в `.env` (`ANTHROPIC_MODEL`).
- `higgsfield-client` — официальный Python SDK Higgsfield
  (`app/higgsfield_client.py`). Исходники SDK разобраны вручную (PyPI-пакет
  распакован и прочитан), поэтому сигнатуры `submit/status/result/upload_file`
  в обёртке — точные, а не угаданные.
- `google-api-python-client` + сервисный аккаунт — чтение папки на Google
  Диске (`app/drive_client.py`).
- Состояние задач — плоский JSON-файл (`app/state.py`, путь из
  `STATE_FILE`), не БД. Это осознанный выбор для одного бота с низкой
  нагрузкой (3 видео/день из ТЗ) — не усложняй SQLite/Postgres без причины.

## Единственное непроверенное место — Higgsfield job_type/аргументы

Публичной документации по точной JSON-схеме `marketing_studio_video` (и по
формату ответа с готовым видео) в открытом доступе нет — только описание
CLI-флагов (`higgsfield-ai/cli` на GitHub) и код SDK. Поэтому:

- `HiggsfieldVideoClient._build_arguments()` в `app/higgsfield_client.py` —
  собирает аргументы по мотивам CLI-флагов (`--mode`, `--product_ids`,
  `--avatars`, `--aspect_ratio`, `--duration`, `--resolution`, `--image`).
- `_extract_video_url()` там же — перебирает вероятные пути к ссылке на
  видео в JSON-ответе; если ни один не подходит, кидает ошибку со списком
  реальных полей ответа.

Если при первом реальном запуске (с деньгами на балансе Higgsfield) API
вернёт ошибку валидации аргументов или `_extract_video_url` не найдёт
ссылку — это следует поправить **только в этих двух местах**, остальной
код (approve-flow, стейт, Google Drive, Telegram) от точной схемы
Higgsfield не зависит.

Полезно свериться с реальной схемой через официальный CLI:
```bash
higgsfield model get marketing_studio_video --json
```

## Договорённости с пользователем (не отступать без явного запроса)

- Бренд сейчас один — MOVIREVO. Мультибрендовость не нужна, пока не попросят.
- Higgsfield вызывается через REST/SDK по ключу — не через MCP-коннектор
  Claude (бот должен работать автономно на сервере, не завися от сессии
  Claude).
- Обязателен шаг approve сценария в Telegram перед платной генерацией видео.
- Автопостинг в Instagram — вне текущего скоупа (был в более раннем
  прототипе для другого бренда, здесь сознательно не реализован).

## Тесты

```bash
pip install -r requirements.txt pytest
pytest -q
```

Тесты не бьют по реальным Anthropic/Higgsfield/Google API — только логика
`state.py`, сборка аргументов и парсинг ответа `higgsfield_client.py`,
`scenario_writer.py` с замоканным `Anthropic`-клиентом.
