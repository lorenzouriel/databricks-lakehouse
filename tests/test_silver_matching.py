"""Unit tests for Silver layer keyword matching logic (03_silver.py)."""
from __future__ import annotations

import pytest
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from src.utils.catalog_reader import build_keyword_to_asset_map


NEWS_SCHEMA = StructType([
    StructField("article_id",  StringType(), nullable=False),
    StructField("title",       StringType(), nullable=True),
    StructField("description", StringType(), nullable=True),
])


def make_matcher_udf(spark, keyword_map: dict):
    """Replicate the keyword matching UDF from 03_silver.py for testability."""
    kw_broadcast = spark.sparkContext.broadcast(keyword_map)

    @F.udf(ArrayType(StringType()))
    def find_matched_assets(title, description):
        text = f"{title or ''} {description or ''}".lower()
        matched = list({
            asset_id
            for kw, asset_id in kw_broadcast.value.items()
            if kw in text
        })
        return matched if matched else ["__unmatched__"]

    return find_matched_assets


@pytest.fixture
def keyword_map(sample_catalog):
    active = [a for a in sample_catalog if a["active"]]
    return build_keyword_to_asset_map(active)


class TestKeywordMatching:
    def test_matches_apple_headline(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a1", "Apple reports record revenue", "iPhone drives growth")],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        assert "AAPL" in result[0]["matched"]

    def test_matches_bitcoin_headline(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a2", "Bitcoin surges past $50k", "Crypto markets rally")],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        assert "BTC-USD" in result[0]["matched"]

    def test_case_insensitive_match(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a3", "APPLE AAPL beats expectations", None)],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        assert "AAPL" in result[0]["matched"]

    def test_unmatched_headline_gets_sentinel(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a4", "Weather forecast for tomorrow", "Sunshine expected")],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        assert result[0]["matched"] == ["__unmatched__"]

    def test_null_title_and_description(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a5", None, None)],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        assert result[0]["matched"] == ["__unmatched__"]

    def test_matches_in_description_only(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a6", "Markets update", "ECB signals rate cut ahead")],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        assert "EURUSD=X" in result[0]["matched"]

    def test_multi_asset_match(self, spark, keyword_map):
        df = spark.createDataFrame(
            [("a7", "Apple buys Bitcoin treasury", "AAPL and BTC news")],
            schema=NEWS_SCHEMA,
        )
        udf = make_matcher_udf(spark, keyword_map)
        result = df.withColumn("matched", udf("title", "description")).collect()

        matched = result[0]["matched"]
        assert "AAPL" in matched
        assert "BTC-USD" in matched
