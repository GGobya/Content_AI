"""
Шаг 1: получение актуальных трендов.
Источники: Google Trends RSS (US) как основной, trendsee как опциональный.
"""

import requests
import feedparser

from app.config import CFG, get_logger

log = get_logger("movirevo.trends")

GOOGLE_TRENDS_RSS_US = "https://trends.google.com/trending/rss?geo=US"


def fetch_google_trends() -> list[dict]:
    log.info("Загружаю Google Trends RSS (US)...")
    feed = feedparser.parse(GOOGLE_TRENDS_RSS_US)
    if feed.bozo:
        log.error(
            "Не удалось загрузить/разобрать Google Trends RSS (%s) — "
            "источник трендов недоступен, пайплайн продолжит с тем, что есть",
            feed.bozo_exception,
        )
        return []
    trends = [
        {
            "title": e.get("title", ""),
            "traffic": e.get("ht_approx_traffic", ""),
            "summary": e.get("summary", ""),
            "published": e.get("published", ""),
            "source": "google_trends",
        }
        for e in feed.entries
    ]
    log.info("Получено %d трендов из Google Trends", len(trends))
    return trends


def fetch_trendsee_trends() -> list[dict]:
    """
    Опциональный источник trendsee.io. У сервиса нет единого публичного API —
    при получении доступа впишите реальный endpoint/параметры ниже.
    """
    if not CFG.trendsee_api_key:
        log.info("TRENDSEE_API_KEY не задан — пропускаю источник trendsee")
        return []
    try:
        resp = requests.get(
            "https://api.trendsee.io/v1/trends",  # TODO: подтвердить актуальный endpoint
            headers={"Authorization": f"Bearer {CFG.trendsee_api_key}"},
            params={"geo": "US"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        trends = [
            {
                "title": item.get("title", ""),
                "traffic": item.get("volume", ""),
                "summary": item.get("description", ""),
                "source": "trendsee",
            }
            for item in data.get("trends", [])
        ]
        log.info("Получено %d трендов из trendsee", len(trends))
        return trends
    except Exception:
        log.exception("Не удалось получить тренды из trendsee, пропускаю источник")
        return []


def fetch_all_trends() -> list[dict]:
    return fetch_google_trends() + fetch_trendsee_trends()
