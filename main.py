#!/usr/bin/env python3
"""
MOVIREVO content factory — точка входа.

Использование:
  python main.py            # запуск Telegram-бота (авто-запуск в DAILY_RUN_TIME + /run вручную)
  python main.py --once     # разово прогнать шаги 1-3 (тренды -> сценарии) и вывести JSON в stdout,
                             # без Telegram — удобно для отладки промптов
"""

import json
import argparse

from app.config import CFG, get_logger
from app.pipeline import run_trend_and_prompt_pipeline
from app.telegram_bot import build_app

log = get_logger("movirevo.main")


def main():
    parser = argparse.ArgumentParser(description="MOVIREVO content factory automation")
    parser.add_argument(
        "--once", action="store_true",
        help="Разово прогнать шаги 1-3 и вывести JSON, без запуска Telegram-бота",
    )
    args = parser.parse_args()

    CFG.validate()

    if args.once:
        scenarios = run_trend_and_prompt_pipeline()
        print(json.dumps(scenarios, ensure_ascii=False, indent=2))
        return

    app = build_app()
    log.info(
        "Бот запущен. /run в Telegram — ручной запуск, "
        "иначе пайплайн стартует каждый день в %s.", CFG.daily_run_time,
    )
    app.run_polling()


if __name__ == "__main__":
    main()
