"""Unit tests for src/fetchers/news_fetcher.py"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.fetchers.news_fetcher import _article_id, fetch_articles, fetch_for_keywords


def _make_api_response(articles: list[dict]) -> dict:
    return {"status": "ok", "totalResults": len(articles), "articles": articles}


def _make_article(url: str = "https://example.com/article-1", keyword: str = "Apple") -> dict:
    return {
        "title": f"Test headline about {keyword}",
        "description": f"Description about {keyword}",
        "url": url,
        "source": {"name": "Reuters"},
        "publishedAt": "2024-01-10T14:30:00Z",
    }


class TestArticleId:
    def test_deterministic(self):
        url = "https://example.com/article"
        assert _article_id(url) == _article_id(url)

    def test_different_urls_give_different_ids(self):
        assert _article_id("https://a.com") != _article_id("https://b.com")

    def test_length_is_32(self):
        assert len(_article_id("https://example.com")) == 32


class TestFetchArticles:
    @patch("src.fetchers.news_fetcher.NewsApiClient")
    def test_returns_flat_dicts(self, mock_client_class, start_date, end_date):
        mock_client = MagicMock()
        mock_client.get_everything.return_value = _make_api_response(
            [_make_article("https://example.com/1")]
        )
        mock_client_class.return_value = mock_client

        result = fetch_articles("fake-key", "Apple", start_date, end_date)

        assert len(result) == 1
        assert "article_id" in result[0]
        assert result[0]["query_keyword"] == "Apple"

    @patch("src.fetchers.news_fetcher.NewsApiClient")
    def test_skips_articles_without_url(self, mock_client_class, start_date, end_date):
        article_no_url = _make_article()
        article_no_url["url"] = ""
        mock_client = MagicMock()
        mock_client.get_everything.return_value = _make_api_response([article_no_url])
        mock_client_class.return_value = mock_client

        result = fetch_articles("fake-key", "Apple", start_date, end_date)

        assert result == []

    @patch("src.fetchers.news_fetcher.NewsApiClient")
    def test_returns_empty_on_api_error(self, mock_client_class, start_date, end_date):
        mock_client = MagicMock()
        mock_client.get_everything.side_effect = Exception("Rate limit")
        mock_client_class.return_value = mock_client

        result = fetch_articles("fake-key", "Apple", start_date, end_date)

        assert result == []

    @patch("src.fetchers.news_fetcher.NewsApiClient")
    def test_returns_empty_on_non_ok_status(self, mock_client_class, start_date, end_date):
        mock_client = MagicMock()
        mock_client.get_everything.return_value = {"status": "error", "message": "apiKeyInvalid"}
        mock_client_class.return_value = mock_client

        result = fetch_articles("fake-key", "Apple", start_date, end_date)

        assert result == []


class TestFetchForKeywords:
    @patch("src.fetchers.news_fetcher.NewsApiClient")
    def test_deduplicates_across_keywords(self, mock_client_class, start_date, end_date):
        shared_url = "https://example.com/shared"
        mock_client = MagicMock()
        mock_client.get_everything.return_value = _make_api_response(
            [_make_article(shared_url)]
        )
        mock_client_class.return_value = mock_client

        result = fetch_for_keywords(
            api_key="fake-key",
            keywords=["Apple", "AAPL"],
            from_date=start_date,
            to_date=end_date,
        )

        assert len(result) == 1

    @patch("src.fetchers.news_fetcher.NewsApiClient")
    def test_aggregates_unique_articles(self, mock_client_class, start_date, end_date):
        def side_effect(**kwargs):
            kw = kwargs.get("q", "")
            return _make_api_response([_make_article(f"https://example.com/{kw}")])

        mock_client = MagicMock()
        mock_client.get_everything.side_effect = lambda **kw: _make_api_response(
            [_make_article(f"https://example.com/{kw.get('q', 'x')}")]
        )
        mock_client_class.return_value = mock_client

        result = fetch_for_keywords(
            api_key="fake-key",
            keywords=["Apple", "Bitcoin"],
            from_date=start_date,
            to_date=end_date,
        )

        assert len(result) == 2
