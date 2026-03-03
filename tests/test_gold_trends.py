"""Unit tests for Gold layer trend computation logic (04_gold.py)."""
from __future__ import annotations

from datetime import date

import pytest
from pyspark.sql import Window, functions as F
from pyspark.sql.types import (
    DateType, DoubleType, LongType, StringType, StructField, StructType
)


SILVER_SCHEMA = StructType([
    StructField("ticker",        StringType(), nullable=False),
    StructField("date",          DateType(),   nullable=False),
    StructField("adj_close",     DoubleType(), nullable=True),
    StructField("pct_change_1d", DoubleType(), nullable=True),
    StructField("volume",        LongType(),   nullable=True),
    StructField("avg_volume_30d",DoubleType(), nullable=True),
    StructField("asset_type",    StringType(), nullable=False),
])


def compute_price_trends(spark, silver_df, up_pct: float = 0.5, down_pct: float = -0.5):
    """Replicate trend computation from 04_gold.py for testability."""
    ticker_window = Window.partitionBy("ticker").orderBy("date")
    latest_window = Window.partitionBy("ticker").orderBy(F.desc("date"))

    return (
        silver_df
        .withColumn("adj_close_7d_ago",  F.lag("adj_close", 7).over(ticker_window))
        .withColumn("adj_close_30d_ago", F.lag("adj_close", 30).over(ticker_window))
        .withColumn("adj_close_90d_ago", F.lag("adj_close", 90).over(ticker_window))
        .withColumn(
            "pct_change_7d",
            F.round(
                (F.col("adj_close") - F.col("adj_close_7d_ago")) / F.col("adj_close_7d_ago") * 100, 2
            ),
        )
        .withColumn(
            "pct_change_30d",
            F.round(
                (F.col("adj_close") - F.col("adj_close_30d_ago")) / F.col("adj_close_30d_ago") * 100, 2
            ),
        )
        .withColumn(
            "pct_change_90d",
            F.round(
                (F.col("adj_close") - F.col("adj_close_90d_ago")) / F.col("adj_close_90d_ago") * 100, 2
            ),
        )
        .withColumn(
            "trend_direction",
            F.when(F.col("pct_change_7d") > up_pct, "UP")
             .when(F.col("pct_change_7d") < down_pct, "DOWN")
             .when(F.col("pct_change_7d").isNotNull(), "FLAT")
             .otherwise(None),
        )
        .withColumn("_rank", F.rank().over(latest_window))
        .filter(F.col("_rank") == 1)
        .drop("_rank", "adj_close_7d_ago", "adj_close_30d_ago", "adj_close_90d_ago")
    )


def _make_price_series(spark, ticker: str, n_days: int, start_price: float = 100.0, daily_delta: float = 1.0):
    """Generate a synthetic daily price series."""
    from datetime import timedelta
    base = date(2024, 1, 2)
    rows = []
    for i in range(n_days):
        dt = base + timedelta(days=i)
        price = start_price + daily_delta * i
        rows.append((ticker, dt, price, None, 1_000_000, 1_000_000.0, "stock"))

    return spark.createDataFrame(rows, schema=SILVER_SCHEMA)


class TestTrendComputation:
    def test_pct_change_7d_is_null_with_insufficient_history(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=5)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["pct_change_7d"] is None

    def test_pct_change_7d_is_computed_with_sufficient_history(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=10, start_price=100.0, daily_delta=1.0)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["pct_change_7d"] is not None
        assert result[0]["pct_change_7d"] > 0

    def test_trend_direction_up(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=10, start_price=100.0, daily_delta=2.0)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["trend_direction"] == "UP"

    def test_trend_direction_down(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=10, start_price=200.0, daily_delta=-2.0)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["trend_direction"] == "DOWN"

    def test_trend_direction_flat(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=10, start_price=100.0, daily_delta=0.01)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["trend_direction"] == "FLAT"

    def test_trend_direction_null_without_7d_history(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=5)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["trend_direction"] is None

    def test_returns_one_row_per_ticker(self, spark):
        df_aapl = _make_price_series(spark, "AAPL", n_days=10)
        df_btc  = _make_price_series(spark, "BTC-USD", n_days=10, start_price=40000.0)
        df = df_aapl.union(df_btc)

        result = compute_price_trends(spark, df)
        assert result.count() == 2

    def test_pct_change_30d_null_with_only_10_days(self, spark):
        df = _make_price_series(spark, "AAPL", n_days=10)
        result = compute_price_trends(spark, df).collect()

        assert result[0]["pct_change_30d"] is None

    def test_pct_change_correct_math(self, spark):
        """Verify pct_change = (latest - 7d_ago) / 7d_ago * 100."""
        df = _make_price_series(spark, "AAPL", n_days=10, start_price=100.0, daily_delta=1.0)
        result = compute_price_trends(spark, df).collect()

        # Latest price = 100 + 9 = 109; 7d ago = 100 + 2 = 102
        expected = round((109.0 - 102.0) / 102.0 * 100, 2)
        assert abs(result[0]["pct_change_7d"] - expected) < 0.01
