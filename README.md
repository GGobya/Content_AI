# MOVIREVO Content Factory

Автоматизированный контент-завод: тренды → Claude отбирает и пишет сценарии →
согласование в Telegram → генерация видео в Higgsfield → согласование видео →
публикация в Instagram Reels. 3 сценария и 3 видео в день, язык — русский.

Цель — усилить органические продажи MOVIREVO (шарфы, свитера, бомберы,
ветровки) на Wildberries и Ozon с минимальной долей рекламных расходов.

## Быстрый старт

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt --break-system-packages   # или без флага, если не Debian/Ubuntu system python
cp .env.example .env
# заполните .env: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
# HIGGSFIELD_API_KEY, IG_ACCESS_TOKEN, IG_BUSINESS_ACCOUNT_ID, S3_*

mkdir -p photos
# положите сюда фото товаров: scarf_1.jpg, sweater_1.jpg, bomber_1.jpg, ...

python main.py --once   # проверка шагов 1-3 без Telegram/трат
python main.py          # полный запуск (бот + ежедневное расписание)
```

В Telegram: команда `/run` запускает пайплайн вручную, иначе он стартует
автоматически каждый день в `DAILY_RUN_TIME` (по умолчанию 09:00).

**Перед первым реальным запуском обязательно прочитайте `CLAUDE.md`** — там
список из 3-4 вещей, которые нужно сверить/доделать под ваши реальные
интеграции (эндпоинты Higgsfield, токен Instagram, публичный сторедж видео).

## Как это работает

```
Google Trends RSS ──┐
                     ├─→ Claude: отбор 5 трендов под бренд
trendsee (опц.) ─────┘         │
                                ▼
                  Claude: 3 сюжетных промпта (RU)
                                │
                                ▼
                    Telegram: согласование сценария
                          (✅ / ❌)
                                │ approve
                                ▼
              Higgsfield: фото товара + промпт → видео
                                │
                                ▼
                 Telegram: согласование готового видео
                          (✅ / ❌)
                                │ approve
                                ▼
                  Instagram: публикация как Reels
```

Каждый шаг с тратой денег/риском публикации — под ручным контролем через
Telegram, чтобы не спамить аккаунт и не жечь кредиты на неудачные генерации.
