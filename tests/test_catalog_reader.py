"""Unit tests for src/utils/catalog_reader.py"""
from __future__ import annotations

import pytest

from src.utils.catalog_reader import (
    build_keyword_to_asset_map,
    filter_by_type,
    get_market_tickers,
    get_news_keywords,
)


@pytest.fixture
def active_catalog(sample_catalog):
    """Return only active catalog entries (mirrors read_active_catalog behaviour)."""
    return [a for a in sample_catalog if a["active"]]


class TestFilterByType:
    def test_filters_stocks(self, active_catalog):
        result = filter_by_type(active_catalog, "stock")
        assert all(a["asset_type"] == "stock" for a in result)
        assert len(result) == 1

    def test_filters_crypto(self, active_catalog):
        result = filter_by_type(active_catalog, "crypto")
        assert len(result) == 1
        assert result[0]["asset_id"] == "BTC-USD"

    def test_returns_empty_for_unknown_type(self, active_catalog):
        result = filter_by_type(active_catalog, "nonexistent")
        assert result == []


class TestGetMarketTickers:
    def test_returns_market_tickers_only(self, active_catalog):
        tickers = get_market_tickers(active_catalog)
        assert "AAPL" in tickers
        assert "BTC-USD" in tickers
        assert "EURUSD=X" in tickers

    def test_excludes_news_keywords(self, active_catalog):
        # Inject a news_keyword type entry
        catalog = active_catalog + [
            {"asset_id": "AI", "asset_type": "news_keyword", "news_keywords": ["AI"]}
        ]
        tickers = get_market_tickers(catalog)
        assert "AI" not in tickers

    def test_excludes_inactive(self, sample_catalog):
        tickers = get_market_tickers(sample_catalog)
        assert "INACTIVE" not in tickers


class TestGetNewsKeywords:
    def test_returns_all_unique_keywords(self, active_catalog):
        keywords = get_news_keywords(active_catalog)
        assert "Apple" in keywords
        assert "Bitcoin" in keywords
        assert "ECB" in keywords

    def test_keywords_are_sorted(self, active_catalog):
        keywords = get_news_keywords(active_catalog)
        assert keywords == sorted(keywords)

    def test_no_duplicates(self, active_catalog):
        keywords = get_news_keywords(active_catalog)
        assert len(keywords) == len(set(keywords))


class TestBuildKeywordToAssetMap:
    def test_maps_keyword_to_asset_id(self, active_catalog):
        mapping = build_keyword_to_asset_map(active_catalog)
        assert mapping["apple"] == "AAPL"
        assert mapping["bitcoin"] == "BTC-USD"
        assert mapping["ecb"] == "EURUSD=X"

    def test_all_keys_are_lowercase(self, active_catalog):
        mapping = build_keyword_to_asset_map(active_catalog)
        assert all(k == k.lower() for k in mapping.keys())

    def test_handles_empty_keywords(self):
        catalog = [{"asset_id": "X", "asset_type": "stock", "news_keywords": []}]
        assert build_keyword_to_asset_map(catalog) == {}

    def test_handles_none_keywords(self):
        catalog = [{"asset_id": "X", "asset_type": "stock", "news_keywords": None}]
        assert build_keyword_to_asset_map(catalog) == {}
