# Content_AI — Telegram-бот для видео-сценариев MOVIREVO

Бот пишет сценарии рекламных вертикальных видео (9:16, UGC-стиль) для бренда
**MOVIREVO** (шарфы, свитера, бомберы, ветровки), берёт фото товаров с
Google Диска, после твоего согласования в Telegram отправляет промпт в
Higgsfield на генерацию видео и присылает готовый ролик обратно в чат.

## Как это работает

```
/new  →  бот берёт неиспользованное фото товара с Google Диска
      →  Claude пишет сценарий + детальный промпт для Higgsfield
      →  сценарий приходит в Telegram с кнопками ✅ / ✏️ / ❌
      →  ✅ Запустить генерацию → запрос уходит в Higgsfield (платно!)
      →  бот периодически проверяет статус задачи
      →  готовое видео присылается в тот же чат
```

Правки (✏️) позволяют переписать сценарий с твоим комментарием и снова
отправить на согласование, не тратя кредиты Higgsfield зря.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполни `.env`:

1. **TELEGRAM_BOT_TOKEN** — токен от [@BotFather](https://t.me/BotFather).
2. **TELEGRAM_ALLOWED_USER_IDS** — твой Telegram user_id (узнать у
   [@userinfobot](https://t.me/userinfobot)), через запятую если пользователей
   несколько. Если оставить пустым — бот отвечает всем, кто напишет.
3. **ANTHROPIC_API_KEY** — ключ Claude API (console.anthropic.com).
4. **HF_API_KEY** / **HF_API_SECRET** — ключи Higgsfield из
   [cloud.higgsfield.ai](https://cloud.higgsfield.ai).
5. **GOOGLE_SERVICE_ACCOUNT_FILE** + **GOOGLE_DRIVE_FOLDER_ID** — см. ниже.

### Настройка доступа к Google Диску

1. Создай проект в [Google Cloud Console](https://console.cloud.google.com/),
   включи **Google Drive API**.
2. Создай сервисный аккаунт (Service Account), скачай его JSON-ключ →
   положи в `credentials/google-service-account.json` (путь берётся из
   `GOOGLE_SERVICE_ACCOUNT_FILE`).
3. Открой нужную папку с фото товаров на Google Диске → «Доступ» →
   расшарь её (роль «Читатель») на email сервисного аккаунта — он выглядит
   как `...@...iam.gserviceaccount.com` и указан в JSON-ключе (поле
   `client_email`).
4. Скопируй ID папки из её ссылки
   (`https://drive.google.com/drive/folders/ЭТОТ_ID`) в `GOOGLE_DRIVE_FOLDER_ID`.

Имя товара бот берёт из имени файла фото (без расширения), поэтому фото
удобно называть как сам товар: `Шарф бежевый вязаный.jpg`.

### Запуск

```bash
python main.py
```

Дальше в Telegram: `/start`, затем `/new` на каждое новое видео.

## Важно: Higgsfield job_type ещё нужно сверить вживую

Бот использует официальный `higgsfield-client` (Python SDK) и по умолчанию
дёргает job_type `marketing_studio_video` в режиме `ugc` — это готовый
Higgsfield-пресет именно под UGC/рекламные ролики. Но:

- На некоторых тарифах Marketing Studio ожидает заранее созданные
  `product`/`avatar` сущности (создаются через `higgsfield marketing-studio
  products create` / `avatars create`, либо в веб-интерфейсе). Если так —
  впиши их id в `HIGGSFIELD_PRODUCT_ID` / `HIGGSFIELD_AVATAR_ID` в `.env`.
  Без них бот передаёт фото товара напрямую полем `image` — рабочая гипотеза
  по документации CLI, не проверенная вживую с реальным ключом.
- Перед первым боевым запуском сверь точную схему аргументов:
  ```bash
  higgsfield model get marketing_studio_video --json
  ```
  и при необходимости поправь `_build_arguments()` в `app/higgsfield_client.py`.
- Формат ответа Higgsfield (где именно лежит ссылка на готовое видео) тоже
  не задокументирован публично — `_extract_video_url()` в том же файле
  перебирает самые вероятные пути и, если ни один не подошёл, кидает ошибку
  с полным списком реальных полей ответа — по ней сразу видно, что поправить.

Дальше эти два места — единственное, что стоит подправить после первого
реального запуска с деньгами на балансе Higgsfield.

## Структура проекта

```
app/
├── config.py            .env → Config
├── state.py              JSON-очередь задач (переживает рестарт бота)
├── drive_client.py        Google Drive: список/скачивание фото товаров
├── scenario_writer.py     Claude API: сценарий + промпт для Higgsfield
├── higgsfield_client.py   Higgsfield SDK: upload → submit → poll → download
└── telegram_bot.py        хендлеры, approve-flow, фоновый опрос задач
main.py                    точка входа
tests/                     unit-тесты (state, scenario_writer, higgsfield_client)
```

## Тесты

```bash
pip install pytest
pytest -q
```

## Дальнейшее развитие (не входит в MVP)

- Автопостинг одобренного видео в Instagram (Meta Graph API) — в прошлых
  прототипах для этого требовался публичный URL видео (S3/R2), сюда не
  включено по ТЗ текущей версии.
- Автоматический подбор трендов (Google Trends) для тем сценариев.
- SQLite вместо JSON-файла, если очередь вырастет и понадобится
  конкурентный доступ из нескольких процессов.
