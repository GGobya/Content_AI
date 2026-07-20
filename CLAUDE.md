# MOVIREVO Content Factory — контекст для Claude Code

## Что это
Автоматизированный контент-завод для бренда **MOVIREVO** (женские шарфы, свитера,
бомберы, ветровки). Цель: 3 сценария / 3 видео в день, минимум ручного труда,
контент усиливает органические продажи на **Wildberries** и **Ozon** через Reels
в Instagram, с минимальной долей рекламных расходов.

## Пайплайн (уже реализован в коде, см. app/)
1. `app/trends.py` — тренды из Google Trends RSS (US) + опционально trendsee
2. `app/claude_analysis.py` — Claude API отбирает 5 релевантных бренду трендов,
   затем генерирует 3 сюжетных видео-промпта на русском для Higgsfield
3. `app/telegram_bot.py` — промпты уходят на согласование в Telegram (кнопки ✅/❌)
4. `app/higgsfield_client.py` — при одобрении: фото товара из `photos/` + промпт
   отправляются в Higgsfield, видео генерируется и скачивается
5. `app/telegram_bot.py` — готовое видео уходит на финальное согласование в Telegram
6. `app/instagram_publish.py` + `app/storage.py` — при подтверждении видео
   публикуется в Instagram как Reels через Meta Graph API

Всё завязано на `app/state.py` (простой json-стейт очереди задач) и
`app/config.py` (единая точка чтения .env).

## ЧТО ТОЧНО НУЖНО ДОДЕЛАТЬ / ПРОВЕРИТЬ

### 1. Higgsfield API — приоритет №1

**Обновление (июль 2026):** `app/higgsfield_client.py` переписан на основе
исходного кода официального Python SDK
(https://github.com/higgsfield-ai/higgsfield-client) — `docs.higgsfield.ai`
недоступен из окружения разработки (403), поэтому SDK был единственным
надёжным источником. Подробный комментарий с источником — в шапке файла.

**Подтверждено из исходников SDK** (уже применено в коде):
- базовый URL `https://platform.higgsfield.ai` (не `api.higgsfield.ai/v1`)
- заголовок авторизации `Authorization: Key {api_key}:{api_secret}` (не
  `Bearer`) — теперь нужен отдельный `HIGGSFIELD_API_SECRET` в `.env`
- загрузка фото: `POST /files/generate-upload-url` → `{upload_url, public_url}`
  → `PUT` байтов на `upload_url` → референсом на фото служит `public_url`
  (не `media_id`)
- запуск генерации: `POST {BASE_URL}/{application}` с телом = параметры
  модели напрямую; ответ — `{request_id, status_url, response_url}`
- статус задачи — поле `status` (не `state`) со значениями `queued` /
  `in_progress` / `completed` / `failed` / `nsfw` / `canceled`

**Всё ещё нужно проверить перед первым реальным запуском:**
- `HIGGSFIELD_APPLICATION` (путь модели для Marketing Studio / product-video)
  — сейчас в `.env.example` best-effort значение
  `higgsfield/marketing-studio/video` по аналогии с MCP-инструментом
  `generate_video` (там модель называется `marketing_studio_video` и
  принимает `prompt` + `aspect_ratio` + `medias:[{role:"image", value:<url>}]`
  — этот формат уже используется в `submit_video_job()`). Точную строку пути
  для REST API нужно свериться в личном кабинете https://cloud.higgsfield.ai
  или в поддержке Higgsfield.
- точное имя поля с URL готового видео в ответе `response_url` —
  `_extract_video_url()` в `app/higgsfield_client.py` проверяет несколько
  вероятных вариантов (`video.url` / `video_url` / `url`) и явно падает с
  понятной ошибкой, если ни один не подошёл — это будет легко
  продиагностировать по логам при первом реальном запуске и поправить.

### 2. Instagram публикация — публичный хостинг видео
`app/storage.py` реализован под S3-совместимое хранилище (AWS S3 или Cloudflare
R2). Нужно:
- завести бакет, сделать его публично читаемым (или отдавать через CDN)
- заполнить `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_PUBLIC_BASE_URL` в `.env`
- если пользователь предпочитает другое хранилище (GCS, Bunny CDN и т.п.) —
  добавить провайдер в `upload_video_public()`

### 3. Instagram Graph API — токены
- `IG_ACCESS_TOKEN` должен быть **long-lived** (не истекает через час) с правом
  `instagram_content_publish`. Long-lived токен получают через обмен
  short-lived user token: `GET /oauth/access_token?grant_type=fb_exchange_token`.
  Рекомендуется добавить отдельный скрипт `scripts/refresh_ig_token.py` для
  автообновления, т.к. даже long-lived токены истекают через ~60 дней.
- `IG_BUSINESS_ACCOUNT_ID` — это ID Instagram Business Account, НЕ username,
  получается через `GET /me/accounts` -> `GET /{page-id}?fields=instagram_business_account`

### 4. Тесты
В `tests/` пока пусто-заготовка. Стоит добавить:
- unit-тесты на `select_relevant_trends`/`generate_video_prompts` с моком
  Anthropic-клиента (проверка, что невалидный JSON от Claude не роняет пайплайн)
- unit-тест на `State` (add/update/get)
- интеграционный smoke-test: `python main.py --once` должен отработать без
  Telegram/Higgsfield ключей и просто вывести пустой список с понятным warning

### 5. Что НЕ нужно менять без запроса пользователя
- Структура согласования (сценарий -> видео -> публикация) — три чекпоинта
  специально оставлены ручными, чтобы не улететь в бан/спам аккаунта и не жечь
  Higgsfield-кредиты на брак
- Язык всех промптов и реплик — русский (это жёсткое требование бренда)

## Установка и запуск
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить ключи
mkdir -p photos        # положить фото товаров (шарфы/свитера/бомберы/ветровки)
python main.py --once  # тест шагов 1-3, без Telegram и без трат
python main.py         # полный запуск бота (long polling)
```

## Структура проекта
```
movirevo_factory/
├── app/
│   ├── config.py           # .env -> Config, логирование
│   ├── state.py             # json-очередь сценариев/видео
│   ├── trends.py             # Google Trends RSS + trendsee
│   ├── claude_analysis.py    # отбор трендов + генерация промптов (Claude API)
│   ├── higgsfield_client.py  # upload фото -> generate video -> poll -> download
│   ├── storage.py            # S3/R2 upload для публичного URL видео
│   ├── instagram_publish.py  # Meta Graph API, публикация Reels
│   ├── telegram_bot.py       # согласование, оркестрация всего цикла
│   └── pipeline.py           # шаги 1-3 одной функцией
├── photos/                   # сюда класть фото товаров
├── output/                   # сюда сохраняются готовые mp4
├── tests/                    # заготовка под unit-тесты
├── main.py                   # точка входа
├── requirements.txt
├── .env.example
└── CLAUDE.md                 # этот файл
```
