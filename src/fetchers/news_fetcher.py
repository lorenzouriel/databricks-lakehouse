from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any, Optional

from newsapi import NewsApiClient


def _article_id(url: str) -> str:
    """Generate a stable, deterministic article identifier from its URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def fetch_articles(
    api_key: str,
    keyword: str,
    from_date: date,
    to_date: date,
    language: str = "en",
    max_articles: int = 20,
    sort_by: str = "publishedAt",
) -> list[dict[str, Any]]:
    """
    Fetch news articles matching a keyword from NewsAPI.
    Returns a list of flat dicts suitable for Spark DataFrame creation.

    Free tier limits: 100 requests/day, 1-month lookback.
    """
    client = NewsApiClient(api_key=api_key)

    try:
        response = client.get_everything(
            q=keyword,
            from_param=from_date.isoformat(),
            to=to_date.isoformat(),
            language=language,
            sort_by=sort_by,
            page_size=min(max_articles, 100),
        )
    except Exception as e:
        print(f"[news_fetcher] API error for keyword '{keyword}': {e}")
        return []

    if response.get("status") != "ok":
        print(f"[news_fetcher] Non-OK response for '{keyword}': {response.get('message')}")
        return []

    articles = response.get("articles", [])
    results: list[dict[str, Any]] = []

    for article in articles[:max_articles]:
        url = article.get("url") or ""
        if not url:
            continue

        results.append({
            "article_id": _article_id(url),
            "title": article.get("title"),
            "description": article.get("description"),
            "source": (article.get("source") or {}).get("name"),
            "url": url,
            "published_at": article.get("publishedAt"),
            "query_keyword": keyword,
        })

    return results


def fetch_for_keywords(
    api_key: str,
    keywords: list[str],
    from_date: date,
    to_date: date,
    language: str = "en",
    max_articles_per_keyword: int = 20,
    sort_by: str = "publishedAt",
) -> list[dict[str, Any]]:
    """
    Fetch articles for multiple keywords, deduplicating by article_id.
    Skips keywords that fail; pipeline continues.
    """
    seen_ids: set[str] = set()
    all_articles: list[dict[str, Any]] = []

    for keyword in keywords:
        articles = fetch_articles(
            api_key=api_key,
            keyword=keyword,
            from_date=from_date,
            to_date=to_date,
            language=language,
            max_articles=max_articles_per_keyword,
            sort_by=sort_by,
        )

        for article in articles:
            aid = article["article_id"]
            if aid not in seen_ids:
                seen_ids.add(aid)
                all_articles.append(article)

    return all_articles
