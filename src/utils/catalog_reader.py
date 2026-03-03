from __future__ import annotations

from typing import Any

from pyspark.sql import SparkSession


def read_active_catalog(spark: SparkSession, database: str) -> list[dict[str, Any]]:
    """
    Read all active assets from the catalog Delta table.
    Returns a list of dicts with keys: asset_id, asset_type, display_name, news_keywords.
    """
    df = spark.table(f"{database}.catalog").filter("active = true")
    return [row.asDict() for row in df.collect()]


def filter_by_type(
    catalog: list[dict[str, Any]],
    asset_type: str,
) -> list[dict[str, Any]]:
    """Return catalog entries filtered by asset_type."""
    return [a for a in catalog if a["asset_type"] == asset_type]


def get_market_tickers(catalog: list[dict[str, Any]]) -> list[str]:
    """Return ticker IDs for all market assets (stock, crypto, fx)."""
    market_types = {"stock", "crypto", "fx"}
    return [a["asset_id"] for a in catalog if a["asset_type"] in market_types]


def get_news_keywords(catalog: list[dict[str, Any]]) -> list[str]:
    """Return all unique news keywords across all catalog assets."""
    keywords: set[str] = set()
    for asset in catalog:
        for kw in (asset.get("news_keywords") or []):
            keywords.add(kw)
    return sorted(keywords)


def build_keyword_to_asset_map(catalog: list[dict[str, Any]]) -> dict[str, str]:
    """
    Build a flat mapping of keyword (lowercased) → asset_id.
    Used in Silver layer keyword matching.
    """
    mapping: dict[str, str] = {}
    for asset in catalog:
        for kw in (asset.get("news_keywords") or []):
            mapping[kw.lower()] = asset["asset_id"]
    return mapping
