"""Shared pytest fixtures for financial-lakehouse tests."""
from __future__ import annotations

import json
import os
from datetime import date

import pandas as pd
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def spark():
    """Local SparkSession for unit tests. Reused across the test session."""
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[2]")
        .appName("financial-lakehouse-tests")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def sample_ohlcv_pdf() -> pd.DataFrame:
    """Sample OHLCV pandas DataFrame (AAPL + BTC-USD + EURUSD=X)."""
    return pd.read_csv(
        os.path.join(FIXTURES_DIR, "sample_ohlcv.csv"),
        parse_dates=["date"],
    )


@pytest.fixture
def sample_news_records() -> list[dict]:
    """Sample news article records from fixtures."""
    with open(os.path.join(FIXTURES_DIR, "sample_news.json")) as f:
        return json.load(f)


@pytest.fixture
def sample_catalog() -> list[dict]:
    """Sample catalog entries (3 active, 1 inactive)."""
    with open(os.path.join(FIXTURES_DIR, "sample_catalog.json")) as f:
        return json.load(f)


@pytest.fixture
def start_date() -> date:
    return date(2024, 1, 2)


@pytest.fixture
def end_date() -> date:
    return date(2024, 1, 16)
