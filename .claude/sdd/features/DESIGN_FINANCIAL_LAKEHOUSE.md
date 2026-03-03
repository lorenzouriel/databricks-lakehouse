# DESIGN: Financial Lakehouse Pipeline

> Technical architecture for a catalog-driven Databricks medallion pipeline ingesting financial market data and news through raw → bronze → silver → gold layers.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | FINANCIAL_LAKEHOUSE |
| **Date** | 2026-03-02 |
| **Author** | design-agent |
| **DEFINE** | [DEFINE_FINANCIAL_LAKEHOUSE.md](./DEFINE_FINANCIAL_LAKEHOUSE.md) |
| **Status** | Ready for Build |

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FINANCIAL LAKEHOUSE — SYSTEM OVERVIEW                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   CONFIG                    ORCHESTRATION                  STORAGE (Delta)        │
│   ──────                    ─────────────                  ──────────────         │
│                                                                                   │
│  catalog.yaml ──────────▶ 00_setup_catalog ──────────────▶ catalog              │
│  settings.yaml ─────┐                                                             │
│                      │    99_run_pipeline (master)                                │
│                      │         │                                                  │
│                      │    ┌────┴─────────────────────────┐                       │
│                      │    │                               │                       │
│                      │    ▼                               ▼                       │
│                      ├──▶ 01_ingest_raw                                          │
│                      │         │                                                  │
│   EXTERNAL APIs      │    ┌────┴─────────────────┐                               │
│   ────────────       │    │                       │                               │
│                      │    ▼                       ▼                               │
│   yfinance ──────────┼──▶ raw_market_data    raw_news   ◀──── NewsAPI            │
│                      │         │                  │                               │
│                      │    ▼    ▼                  ▼    ▼                          │
│                      └──▶ 02_bronze                                              │
│                                │                                                  │
│                      ┌─────────┴──────────┐                                      │
│                      │                    │                                       │
│                      ▼                    ▼                                       │
│              bronze_market_data      bronze_news                                  │
│                      │                    │                                       │
│                      └─────────┬──────────┘                                      │
│                                ▼                                                  │
│                           03_silver                                               │
│                                │                                                  │
│                      ┌─────────┴──────────┐                                      │
│                      │                    │                                       │
│                      ▼                    ▼                                       │
│              silver_market_data      silver_news                                  │
│                      │                    │                                       │
│                      └─────────┬──────────┘                                      │
│                                ▼                                                  │
│                           04_gold                                                 │
│                                │                                                  │
│                      ┌─────────┴──────────┐                                      │
│                      │                    │                                       │
│                      ▼                    ▼                                       │
│            gold_price_trend_summary   gold_news_summary                           │
│                                                                                   │
│                         ▲ future consumers ▲                                      │
│                    AI Agent        Dashboard                                      │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `config/catalog.yaml` | Asset registry — defines what to monitor | YAML |
| `config/settings.yaml` | Pipeline tuning (lookback days, NewsAPI key, DB name) | YAML |
| `src/fetchers/yfinance_fetcher.py` | Wraps yfinance API calls, returns pandas DataFrames | Python + yfinance |
| `src/fetchers/news_fetcher.py` | Wraps NewsAPI calls, returns structured article dicts | Python + newsapi-python |
| `src/utils/catalog_reader.py` | Reads active catalog entries from Delta table | PySpark |
| `src/utils/delta_utils.py` | Delta table helpers: create, MERGE upsert, schema enforcement | PySpark + delta-spark |
| `src/utils/logger.py` | Structured print-based logging with run_id and timestamp | Python |
| `notebooks/00_setup_catalog.py` | Loads catalog.yaml → Delta `catalog` table (upsert) | PySpark notebook |
| `notebooks/01_ingest_raw.py` | Fetches from APIs → writes to `raw_market_data`, `raw_news` | PySpark notebook |
| `notebooks/02_bronze.py` | Schema enforce, deduplicate, add metadata → bronze tables | PySpark notebook |
| `notebooks/03_silver.py` | Normalize prices, keyword-match news → silver tables | PySpark notebook |
| `notebooks/04_gold.py` | Compute 7/30/90d trends, aggregate news → gold tables | PySpark notebook |
| `notebooks/99_run_pipeline.py` | Master orchestrator using `%run` to call all stages | Databricks notebook |
| `requirements.txt` | Python dependency list | pip |

---

## Key Decisions

### Decision 1: PySpark + pandas Hybrid (not pure pandas, not pure PySpark)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-02 |

**Context:** `yfinance` and `newsapi-python` return pandas DataFrames / Python dicts. Delta tables require Spark DataFrames for write operations with schema enforcement and MERGE support.

**Choice:** Use pandas for API response handling in `src/fetchers/`, convert to Spark DataFrames at the raw ingestion layer boundary, then use PySpark for all Delta table operations throughout bronze → silver → gold.

**Rationale:** This keeps fetcher code simple and testable (no Spark dependency in unit tests), while correctly leveraging Delta Lake capabilities for the pipeline.

**Alternatives Rejected:**
1. Pure pandas + delta-rs — Rejected because delta-rs on Databricks Community Edition is unreliable; native `delta-spark` is the supported path
2. Pure PySpark for API calls — Rejected because `yfinance` is not PySpark-compatible; forcing it would require UDFs that are harder to test

**Consequences:**
- Accept the `spark.createDataFrame(pandas_df)` conversion overhead at raw layer (acceptable for small daily batches)
- Fetcher unit tests can run without a Spark session (faster CI)

---

### Decision 2: Delta MERGE for Idempotency (not overwrite)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-02 |

**Context:** The pipeline must be idempotent — re-running on the same day must not create duplicate rows. Two strategies exist: full overwrite (simpler) or MERGE (preserves history).

**Choice:** Use Delta `MERGE INTO` (upsert) at every layer with composite keys:
- Market data: `(ticker, date)`
- News: `(article_id)`
- Gold summary: `(ticker, run_date)` and `(asset_id, summary_date)`

**Rationale:** MERGE preserves historical data across runs while preventing duplicates. Full overwrite would lose data from previous days if the pipeline only fetches recent data. MERGE is the standard Delta Lake idempotency pattern.

**Alternatives Rejected:**
1. `overwrite` mode — Rejected because it would wipe all historical data when re-running for a single day's delta
2. `append` + deduplication at read time — Rejected because it creates storage bloat and complicates queries

**Consequences:**
- Accept slightly more complex write code (MERGE vs. simple write)
- Gain: safe re-runs, historical accumulation, no data loss

---

### Decision 3: Single Databricks Database Namespace

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-02 |

**Context:** Tables need to be organized and discoverable. On Community Edition, Unity Catalog is unavailable; Hive metastore is the only option.

**Choice:** Create a single database `financial_lakehouse` with all tables registered in it:
- `financial_lakehouse.catalog`
- `financial_lakehouse.raw_market_data`, `financial_lakehouse.raw_news`
- `financial_lakehouse.bronze_market_data`, `financial_lakehouse.bronze_news`
- `financial_lakehouse.silver_market_data`, `financial_lakehouse.silver_news`
- `financial_lakehouse.gold_price_trend_summary`, `financial_lakehouse.gold_news_summary`

**Rationale:** Single database keeps all tables discoverable in one place, avoids naming collisions, and makes the medallion layers visible in the Databricks Data browser.

**Alternatives Rejected:**
1. One database per layer (raw_db, bronze_db, etc.) — Rejected as unnecessarily complex for this scale
2. Path-based access only (no metastore registration) — Rejected because table names are more readable and portable

**Consequences:**
- Accept that dropping the database drops all tables (acceptable for dev)
- Gain: clean namespace, visible in Databricks UI

---

### Decision 4: `%run` for Notebook Orchestration

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-02 |

**Context:** The master orchestrator needs to call other notebooks in sequence. On Community Edition, `dbutils.notebook.run()` requires Databricks Jobs/Workflows infrastructure that may not be available.

**Choice:** Use Databricks `%run` magic command to include and execute sibling notebooks inline within the same Spark session.

**Rationale:** `%run` executes the target notebook in the same kernel scope, sharing the Spark session and variables. It's the native Community Edition orchestration primitive. No extra infrastructure needed.

**Alternatives Rejected:**
1. `dbutils.notebook.run()` — Rejected because it spawns a new job cluster context (not reliable on Community Edition)
2. Import notebooks as Python modules — Rejected because Databricks notebooks are not importable as standard modules without special configuration

**Consequences:**
- Accept that `%run` shares scope (variable names must not collide across notebooks)
- Gain: simple, reliable, works on Community Edition

---

### Decision 5: String Keyword Matching for News-to-Asset Correlation (Silver Layer)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-02 |

**Context:** News headlines from NewsAPI need to be linked to catalog assets to enable per-asset news aggregation in Gold.

**Choice:** Case-insensitive string matching — check if any of an asset's `news_keywords` appear in the headline title or description. Store all matching `asset_id`s in an array column `matched_asset_ids`.

**Rationale:** Simple, deterministic, zero-cost, no external API needed. Sufficient for MVP trend monitoring. The catalog's `news_keywords` field gives the user control over matching precision.

**Alternatives Rejected:**
1. Embedding-based semantic matching (sentence-transformers) — Rejected as YAGNI; adds ML model dependency, overkill for keyword-level matching
2. Named Entity Recognition (NER) — Rejected for same reason; future AI Agent feature

**Consequences:**
- Accept false positives (e.g., "Apple" matching Apple Inc. news AND apple orchards)
- User controls precision via `news_keywords` in catalog.yaml
- Gain: zero-latency, fully offline, deterministic

---

### Decision 6: Settings in `settings.yaml`, Secrets via Databricks Secrets

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-03-02 |

**Context:** The NewsAPI key must not be hardcoded. Pipeline tuning parameters (lookback days, database name) should be configurable without code changes.

**Choice:**
- Non-secret settings: `config/settings.yaml` (version-controlled)
- API keys: Databricks Secrets (`dbutils.secrets.get(scope, key)`) — never in files

**Rationale:** `settings.yaml` keeps tunable parameters visible and reviewable. Databricks Secrets is the correct Community Edition mechanism for storing API keys without embedding them in notebooks or config files.

**Alternatives Rejected:**
1. Environment variables — Rejected because Databricks notebooks don't have persistent env vars without init scripts
2. Hardcoded in notebooks — Rejected as a security anti-pattern

**Consequences:**
- Requires one-time setup of Databricks Secret Scope for NewsAPI key
- settings.yaml is safe to commit to Git (no secrets)

---

## File Manifest

| # | File | Action | Purpose | Agent | Dependencies |
|---|------|--------|---------|-------|--------------|
| 1 | `config/catalog.yaml` | Create | Asset catalog definition — stocks, crypto, FX, news keywords | (general) | None |
| 2 | `config/settings.yaml` | Create | Pipeline tuning parameters (lookback_days, db_name, log_level) | (general) | None |
| 3 | `requirements.txt` | Create | Python dependencies | (general) | None |
| 4 | `src/__init__.py` | Create | Package marker | (general) | None |
| 5 | `src/fetchers/__init__.py` | Create | Package marker | (general) | None |
| 6 | `src/fetchers/yfinance_fetcher.py` | Create | Wraps yfinance OHLCV download with error handling + retry | @python-developer | None |
| 7 | `src/fetchers/news_fetcher.py` | Create | Wraps NewsAPI calls with pagination and rate-limit awareness | @python-developer | None |
| 8 | `src/utils/__init__.py` | Create | Package marker | (general) | None |
| 9 | `src/utils/catalog_reader.py` | Create | Reads active catalog entries from Delta table, returns list of dicts | @python-developer | None |
| 10 | `src/utils/delta_utils.py` | Create | Delta table helpers: ensure_table, merge_into, get_row_count | @spark-specialist | None |
| 11 | `src/utils/logger.py` | Create | Structured logging with run_id, stage, timestamp | @python-developer | None |
| 12 | `src/utils/settings_loader.py` | Create | Loads and validates settings.yaml | @python-developer | 2 |
| 13 | `notebooks/00_setup_catalog.py` | Create | Reads catalog.yaml, upserts into Delta catalog table | @lakeflow-pipeline-builder | 1, 9, 10, 11 |
| 14 | `notebooks/01_ingest_raw.py` | Create | Iterates catalog, fetches yfinance + NewsAPI, writes raw Delta tables | @lakeflow-pipeline-builder | 6, 7, 9, 10, 11, 12 |
| 15 | `notebooks/02_bronze.py` | Create | Schema enforcement, deduplication, metadata enrichment → bronze tables | @lakeflow-pipeline-builder | 9, 10, 11 |
| 16 | `notebooks/03_silver.py` | Create | Price normalization, news keyword matching → silver tables | @spark-specialist | 9, 10, 11 |
| 17 | `notebooks/04_gold.py` | Create | 7/30/90d trend computation, news aggregation → gold tables | @spark-specialist | 9, 10, 11 |
| 18 | `notebooks/99_run_pipeline.py` | Create | Master orchestrator using `%run` to chain all stages | (general) | 13, 14, 15, 16, 17 |
| 19 | `tests/__init__.py` | Create | Package marker | (general) | None |
| 20 | `tests/test_yfinance_fetcher.py` | Create | Unit tests for yfinance fetcher with mocked responses | @test-generator | 6 |
| 21 | `tests/test_news_fetcher.py` | Create | Unit tests for news fetcher with mocked NewsAPI responses | @test-generator | 7 |
| 22 | `tests/test_catalog_reader.py` | Create | Unit tests for catalog reader (mocked Spark session) | @test-generator | 9 |
| 23 | `tests/test_delta_utils.py` | Create | Unit tests for delta_utils helpers | @test-generator | 10 |
| 24 | `tests/test_silver_matching.py` | Create | Unit tests for keyword matching logic | @test-generator | 16 |
| 25 | `tests/test_gold_trends.py` | Create | Unit tests for trend computation functions | @test-generator | 17 |

**Total Files:** 25

---

## Agent Assignment Rationale

| Agent | Files | Why This Agent |
|-------|-------|----------------|
| @python-developer | 6, 7, 9, 11, 12 | Clean Python patterns, dataclasses, type hints — fetchers and utilities are pure Python with no Spark dependency |
| @spark-specialist | 10, 16, 17 | PySpark transformations: window functions (trend %), aggregations, MERGE operations, schema handling |
| @lakeflow-pipeline-builder | 13, 14, 15 | Databricks notebook structure, medallion layer patterns, Delta table creation and ingestion |
| @test-generator | 20, 21, 22, 23, 24, 25 | pytest fixtures, mock patterns, unit test generation |
| (general) | 1, 2, 3, 4, 5, 8, 18, 19 | Config files, package markers, simple orchestrator — no specialist needed |

**Agent Discovery:** Scanned `.claude/agents/` — matched by file type, purpose keywords, and KB domain alignment.

---

## Code Patterns

### Pattern 1: `catalog.yaml` Structure

```yaml
# config/catalog.yaml
# Central registry of assets to monitor.
# Add a ticker here → it gets processed through all pipeline layers.

assets:
  stocks:
    - id: "AAPL"
      display_name: "Apple Inc."
      news_keywords: ["Apple", "AAPL", "Tim Cook"]

    - id: "MSFT"
      display_name: "Microsoft Corporation"
      news_keywords: ["Microsoft", "MSFT", "Satya Nadella"]

    - id: "NVDA"
      display_name: "NVIDIA Corporation"
      news_keywords: ["NVIDIA", "NVDA", "Jensen Huang"]

  crypto:
    - id: "BTC-USD"
      display_name: "Bitcoin"
      news_keywords: ["Bitcoin", "BTC", "Satoshi"]

    - id: "ETH-USD"
      display_name: "Ethereum"
      news_keywords: ["Ethereum", "ETH", "Vitalik"]

  fx:
    - id: "EURUSD=X"
      display_name: "EUR/USD"
      news_keywords: ["EUR/USD", "Euro", "ECB"]

    - id: "GBPUSD=X"
      display_name: "GBP/USD"
      news_keywords: ["GBP/USD", "Sterling", "Bank of England"]
```

---

### Pattern 2: `settings.yaml` Structure

```yaml
# config/settings.yaml
# Non-secret pipeline configuration. Safe to commit to Git.

pipeline:
  database_name: "financial_lakehouse"
  lookback_days_initial: 90      # Days of history to fetch on first run
  lookback_days_incremental: 3   # Days to fetch on subsequent runs (overlap for safety)
  run_date: null                 # null = today; override for backfill (YYYY-MM-DD)

news:
  # NewsAPI key stored in Databricks Secrets:
  # dbutils.secrets.get(scope="financial-lakehouse", key="newsapi-key")
  secret_scope: "financial-lakehouse"
  secret_key: "newsapi-key"
  max_articles_per_keyword: 20
  language: "en"

gold:
  trend_thresholds:
    up_pct: 0.5      # pct_change_7d > 0.5 → UP
    down_pct: -0.5   # pct_change_7d < -0.5 → DOWN
    # else → FLAT
```

---

### Pattern 3: yfinance Fetcher

```python
# src/fetchers/yfinance_fetcher.py
from __future__ import annotations
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from typing import Optional


def fetch_ohlcv(
    ticker: str,
    start_date: date,
    end_date: date,
) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV data for a single ticker.
    Returns None if ticker is invalid or data unavailable.
    """
    try:
        raw = yf.download(
            ticker,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=False,
            progress=False,
        )
        if raw.empty:
            return None

        df = raw.reset_index()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        })
        df["ticker"] = ticker
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df[["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]]

    except Exception as e:
        print(f"[yfinance_fetcher] ERROR fetching {ticker}: {e}")
        return None


def fetch_multiple(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Fetch OHLCV for multiple tickers, returning a combined DataFrame."""
    frames = []
    for ticker in tickers:
        df = fetch_ohlcv(ticker, start_date, end_date)
        if df is not None:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
```

---

### Pattern 4: Delta MERGE Upsert (Idempotency)

```python
# src/utils/delta_utils.py — core MERGE pattern
from delta.tables import DeltaTable
from pyspark.sql import SparkSession, DataFrame


def merge_into_delta(
    spark: SparkSession,
    source_df: DataFrame,
    target_table: str,
    merge_keys: list[str],
) -> int:
    """
    Idempotent upsert: insert new rows, update existing ones.
    Returns number of rows in target after merge.
    """
    if not DeltaTable.isDeltaTable(spark, f"default.{target_table}"):
        source_df.write.format("delta").saveAsTable(target_table)
        return source_df.count()

    target = DeltaTable.forName(spark, target_table)
    merge_condition = " AND ".join(
        [f"target.{k} = source.{k}" for k in merge_keys]
    )

    (
        target.alias("target")
        .merge(source_df.alias("source"), merge_condition)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )

    return spark.table(target_table).count()


def ensure_database(spark: SparkSession, db_name: str) -> None:
    """Create database if it does not exist."""
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    spark.sql(f"USE {db_name}")
```

---

### Pattern 5: Schema Enforcement with StructType

```python
# Used in 02_bronze.py — enforce explicit schema before writing to Delta

from pyspark.sql.types import (
    StructType, StructField,
    StringType, DateType, DoubleType, LongType, TimestampType
)

BRONZE_MARKET_SCHEMA = StructType([
    StructField("ticker",      StringType(),    nullable=False),
    StructField("date",        DateType(),      nullable=False),
    StructField("open",        DoubleType(),    nullable=True),
    StructField("high",        DoubleType(),    nullable=True),
    StructField("low",         DoubleType(),    nullable=True),
    StructField("close",       DoubleType(),    nullable=True),
    StructField("adj_close",   DoubleType(),    nullable=True),
    StructField("volume",      LongType(),      nullable=True),
    StructField("asset_type",  StringType(),    nullable=False),
    StructField("bronze_ts",   TimestampType(), nullable=False),
])

BRONZE_NEWS_SCHEMA = StructType([
    StructField("article_id",    StringType(),    nullable=False),
    StructField("title",         StringType(),    nullable=True),
    StructField("description",   StringType(),    nullable=True),
    StructField("source",        StringType(),    nullable=True),
    StructField("url",           StringType(),    nullable=True),
    StructField("published_at",  TimestampType(), nullable=True),
    StructField("query_keyword", StringType(),    nullable=True),
    StructField("bronze_ts",     TimestampType(), nullable=False),
])

def enforce_schema_and_filter(df, schema):
    """Cast to schema, drop rows with null non-nullable fields."""
    from pyspark.sql import functions as F
    from datetime import datetime

    df = spark.createDataFrame(df.rdd, schema=schema)
    non_nullable = [f.name for f in schema.fields if not f.nullable]
    for col in non_nullable:
        df = df.filter(F.col(col).isNotNull())
    return df
```

---

### Pattern 6: Silver Layer — News Keyword Matching

```python
# Used in 03_silver.py — link news headlines to catalog assets

from pyspark.sql import functions as F, DataFrame


def match_news_to_assets(
    news_df: DataFrame,
    catalog_df: DataFrame,
) -> DataFrame:
    """
    For each headline, find all catalog assets whose news_keywords
    appear (case-insensitive) in the title or description.
    Returns news_df with added 'matched_asset_ids' ARRAY column.
    """
    # Build keyword → asset_id lookup as broadcast dict
    keyword_map = {}  # keyword_lower → asset_id
    for row in catalog_df.collect():
        for kw in (row.news_keywords or []):
            keyword_map[kw.lower()] = row.asset_id

    kw_broadcast = spark.sparkContext.broadcast(keyword_map)

    @F.udf("array<string>")
    def find_matches(title, description):
        text = f"{title or ''} {description or ''}".lower()
        matched = list({
            asset_id
            for kw, asset_id in kw_broadcast.value.items()
            if kw in text
        })
        return matched if matched else ["__unmatched__"]

    return news_df.withColumn(
        "matched_asset_ids",
        find_matches(F.col("title"), F.col("description"))
    )
```

---

### Pattern 7: Gold Layer — Trend Computation with Window Functions

```python
# Used in 04_gold.py — compute 7/30/90-day percent change

from pyspark.sql import functions as F, Window


def compute_price_trends(silver_market_df: DataFrame) -> DataFrame:
    """
    Compute rolling percent change vs. N days ago.
    Uses Window lag() to look back across ordered dates per ticker.
    """
    ticker_window = Window.partitionBy("ticker").orderBy("date")

    df = silver_market_df.withColumn(
        "adj_close_7d_ago",  F.lag("adj_close", 7).over(ticker_window)
    ).withColumn(
        "adj_close_30d_ago", F.lag("adj_close", 30).over(ticker_window)
    ).withColumn(
        "adj_close_90d_ago", F.lag("adj_close", 90).over(ticker_window)
    )

    df = df.withColumn(
        "pct_change_7d",
        F.round((F.col("adj_close") - F.col("adj_close_7d_ago")) / F.col("adj_close_7d_ago") * 100, 2)
    ).withColumn(
        "pct_change_30d",
        F.round((F.col("adj_close") - F.col("adj_close_30d_ago")) / F.col("adj_close_30d_ago") * 100, 2)
    ).withColumn(
        "pct_change_90d",
        F.round((F.col("adj_close") - F.col("adj_close_90d_ago")) / F.col("adj_close_90d_ago") * 100, 2)
    ).withColumn(
        "trend_direction",
        F.when(F.col("pct_change_7d") > 0.5, "UP")
         .when(F.col("pct_change_7d") < -0.5, "DOWN")
         .otherwise("FLAT")
    )

    # Keep only the latest run date per ticker for Gold summary
    latest_window = Window.partitionBy("ticker").orderBy(F.desc("date"))
    return (
        df.withColumn("_rank", F.rank().over(latest_window))
          .filter(F.col("_rank") == 1)
          .drop("_rank", "adj_close_7d_ago", "adj_close_30d_ago", "adj_close_90d_ago")
    )
```

---

### Pattern 8: Master Orchestrator (`99_run_pipeline.py`)

```python
# notebooks/99_run_pipeline.py
# Master pipeline orchestrator. Run this notebook to execute the full pipeline.

import time
from datetime import datetime

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"[pipeline] Starting run {RUN_ID} at {datetime.now().isoformat()}")

stages = [
    ("00_setup_catalog",  "./00_setup_catalog"),
    ("01_ingest_raw",     "./01_ingest_raw"),
    ("02_bronze",         "./02_bronze"),
    ("03_silver",         "./03_silver"),
    ("04_gold",           "./04_gold"),
]

for stage_name, stage_path in stages:
    print(f"\n{'='*60}")
    print(f"[pipeline] Running stage: {stage_name}")
    print(f"{'='*60}")
    t0 = time.time()
    %run $stage_path
    elapsed = round(time.time() - t0, 1)
    print(f"[pipeline] Completed {stage_name} in {elapsed}s")

print(f"\n[pipeline] Run {RUN_ID} COMPLETE at {datetime.now().isoformat()}")
```

---

## Data Flow

```text
1. catalog.yaml → 00_setup_catalog.py
   ├── Load YAML with PyYAML
   ├── Flatten to rows: (asset_id, asset_type, display_name, news_keywords[], active, added_date)
   └── MERGE INTO financial_lakehouse.catalog ON asset_id

2. catalog table → 01_ingest_raw.py
   ├── Read active catalog entries
   ├── For each market asset (stock/crypto/fx):
   │   ├── fetch_ohlcv(ticker, start_date, end_date) via yfinance_fetcher
   │   └── MERGE INTO financial_lakehouse.raw_market_data ON (ticker, date)
   └── For each news_keyword:
       ├── newsapi.get_everything(q=keyword, ...) via news_fetcher
       └── MERGE INTO financial_lakehouse.raw_news ON article_id

3. raw_market_data, raw_news → 02_bronze.py
   ├── Cast raw_market_data to BRONZE_MARKET_SCHEMA
   ├── Filter nulls on (ticker, date)
   ├── Add bronze_ts = current_timestamp(), asset_type from catalog
   ├── MERGE INTO bronze_market_data ON (ticker, date)
   ├── Cast raw_news to BRONZE_NEWS_SCHEMA
   ├── Deduplicate by article_id
   ├── Add bronze_ts = current_timestamp()
   └── MERGE INTO bronze_news ON article_id

4. bronze_market_data → 03_silver.py (market path)
   ├── Compute pct_change_1d = (adj_close - prev_adj_close) / prev_adj_close * 100
   ├── Compute 30d_avg_volume using Window(30)
   └── MERGE INTO silver_market_data ON (ticker, date)

4. bronze_news + catalog → 03_silver.py (news path)
   ├── match_news_to_assets(): keyword scan → matched_asset_ids[]
   ├── Mark unmatched as ["__unmatched__"]
   └── MERGE INTO silver_news ON article_id

5. silver_market_data → 04_gold.py (price trends)
   ├── compute_price_trends(): Window lag for 7/30/90d
   ├── Add trend_direction (UP/DOWN/FLAT)
   └── MERGE INTO gold_price_trend_summary ON (ticker, run_date)

5. silver_news → 04_gold.py (news aggregation)
   ├── Explode matched_asset_ids
   ├── Group by (asset_id, summary_date)
   ├── headline_count = count(article_id)
   ├── top_sources = collect_list(source) deduplicated, top 3
   ├── sample_headlines = collect_list(title), first 3
   └── MERGE INTO gold_news_summary ON (asset_id, summary_date)
```

---

## Integration Points

| External System | Integration Type | Authentication | Rate Limits |
|-----------------|-----------------|----------------|-------------|
| Yahoo Finance (`yfinance`) | Python library (HTTP internally) | None — no API key required | Informal; ~2000 req/day practical limit |
| NewsAPI | REST API via `newsapi-python` SDK | API Key (Databricks Secret) | 100 req/day (free tier) |
| Databricks DBFS | Managed storage for Delta tables | Cluster IAM (auto) | None |
| Hive Metastore | Table registration | Cluster IAM (auto) | None |

---

## Full Table Schemas

### `financial_lakehouse.catalog`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `asset_id` | STRING | No | Primary key (e.g., `AAPL`, `BTC-USD`) |
| `asset_type` | STRING | No | `stock` \| `crypto` \| `fx` \| `news_keyword` |
| `display_name` | STRING | Yes | Human-readable label |
| `news_keywords` | ARRAY\<STRING\> | Yes | Keywords for NewsAPI + Silver matching |
| `active` | BOOLEAN | No | Default `true` |
| `added_date` | DATE | No | Date first added to catalog |

### `financial_lakehouse.raw_market_data`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `ticker` | STRING | No | Merge key |
| `date` | DATE | No | Merge key |
| `open` | DOUBLE | Yes | |
| `high` | DOUBLE | Yes | |
| `low` | DOUBLE | Yes | |
| `close` | DOUBLE | Yes | |
| `adj_close` | DOUBLE | Yes | Adjusted for splits/dividends |
| `volume` | LONG | Yes | |
| `ingestion_ts` | TIMESTAMP | No | API fetch timestamp |

### `financial_lakehouse.raw_news`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `article_id` | STRING | No | SHA256 hash of URL; merge key |
| `title` | STRING | Yes | |
| `description` | STRING | Yes | |
| `source` | STRING | Yes | Source name (e.g., "Reuters") |
| `url` | STRING | Yes | |
| `published_at` | TIMESTAMP | Yes | |
| `query_keyword` | STRING | Yes | Catalog keyword that retrieved this article |
| `ingestion_ts` | TIMESTAMP | No | |

### `financial_lakehouse.bronze_market_data`
All columns from raw + `asset_type STRING NOT NULL`, `bronze_ts TIMESTAMP NOT NULL`

### `financial_lakehouse.bronze_news`
All columns from raw_news + `bronze_ts TIMESTAMP NOT NULL`

### `financial_lakehouse.silver_market_data`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `ticker` | STRING | No | |
| `date` | DATE | No | |
| `adj_close` | DOUBLE | Yes | |
| `pct_change_1d` | DOUBLE | Yes | (adj_close - prev) / prev * 100 |
| `volume` | LONG | Yes | |
| `avg_volume_30d` | DOUBLE | Yes | Rolling 30-day average |
| `asset_type` | STRING | No | |

### `financial_lakehouse.silver_news`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `article_id` | STRING | No | |
| `title` | STRING | Yes | |
| `description` | STRING | Yes | |
| `published_at` | TIMESTAMP | Yes | |
| `source` | STRING | Yes | |
| `query_keyword` | STRING | Yes | |
| `matched_asset_ids` | ARRAY\<STRING\> | No | Min 1 entry; `["__unmatched__"]` if no match |

### `financial_lakehouse.gold_price_trend_summary`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `ticker` | STRING | No | Merge key |
| `run_date` | DATE | No | Merge key (date of pipeline run) |
| `adj_close` | DOUBLE | Yes | Latest close price |
| `pct_change_7d` | DOUBLE | Yes | Null if < 7 days of history |
| `pct_change_30d` | DOUBLE | Yes | Null if < 30 days of history |
| `pct_change_90d` | DOUBLE | Yes | Null if < 90 days of history |
| `avg_volume_30d` | DOUBLE | Yes | |
| `trend_direction` | STRING | Yes | `UP` \| `DOWN` \| `FLAT` \| null |
| `asset_type` | STRING | No | |

### `financial_lakehouse.gold_news_summary`
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `asset_id` | STRING | No | Merge key |
| `summary_date` | DATE | No | Merge key |
| `headline_count` | LONG | No | Total articles matched |
| `top_sources` | ARRAY\<STRING\> | Yes | Top 3 news sources by count |
| `sample_headlines` | ARRAY\<STRING\> | Yes | First 3 headlines for LLM context |

---

## Testing Strategy

| Test Type | Scope | Files | Tools | Notes |
|-----------|-------|-------|-------|-------|
| Unit | Fetchers (yfinance, NewsAPI) | `tests/test_yfinance_fetcher.py`, `tests/test_news_fetcher.py` | pytest + unittest.mock | Mock HTTP responses; no real API calls |
| Unit | Catalog reader, delta_utils helpers | `tests/test_catalog_reader.py`, `tests/test_delta_utils.py` | pytest + pyspark (local mode) | Use `SparkSession.builder.master("local")` |
| Unit | Silver matching logic | `tests/test_silver_matching.py` | pytest + pyspark local | Test keyword matching UDF with known inputs |
| Unit | Gold trend computation | `tests/test_gold_trends.py` | pytest + pyspark local | Verify pct_change math with synthetic price series |
| Integration | Full pipeline run | Manual: run `99_run_pipeline.py` in Databricks | Databricks notebook | Validate AT-001 through AT-008 acceptance tests |
| Idempotency | Same-day re-run | Manual: run pipeline twice | Databricks notebook | Validate AT-003 |

**Test fixtures to create:**
- `tests/fixtures/sample_ohlcv.csv` — 100 rows of synthetic AAPL data
- `tests/fixtures/sample_news.json` — 10 synthetic NewsAPI article responses
- `tests/fixtures/sample_catalog.json` — minimal catalog with 2 assets

---

## Error Handling

| Error Type | Handling Strategy | Retry? |
|------------|-------------------|--------|
| `yfinance` returns empty DataFrame | Log warning, skip ticker, continue pipeline | No (data unavailable) |
| `yfinance` network error | Catch exception, log error, skip ticker | No (fail-fast on individual asset, not whole pipeline) |
| NewsAPI rate limit exceeded (429) | Log error with rate limit message, skip remaining keyword queries | No (resume next day) |
| NewsAPI invalid API key | Raise immediately with clear message pointing to Secret scope setup | No |
| Bronze schema violation (null key columns) | Filter + log rejected rows to console, write valid rows only | No |
| Delta table not found on first run | `ensure_table()` creates it; subsequent MERGE proceeds | N/A |
| Empty catalog | Log "Catalog is empty — nothing to process", exit cleanly | No |
| `spark.createDataFrame()` schema mismatch | Catch AnalysisException, log columns diff, re-raise | No |

---

## Configuration Reference

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `pipeline.database_name` | string | `financial_lakehouse` | Hive database for all tables |
| `pipeline.lookback_days_initial` | int | `90` | Days of history fetched on first pipeline run |
| `pipeline.lookback_days_incremental` | int | `3` | Days fetched on subsequent runs (overlap for safety) |
| `pipeline.run_date` | string \| null | `null` | Override run date for backfill (YYYY-MM-DD); null = today |
| `news.secret_scope` | string | `financial-lakehouse` | Databricks Secret scope name |
| `news.secret_key` | string | `newsapi-key` | Key name within the secret scope |
| `news.max_articles_per_keyword` | int | `20` | Max articles per keyword per API call |
| `gold.trend_thresholds.up_pct` | float | `0.5` | 7d pct change threshold for UP classification |
| `gold.trend_thresholds.down_pct` | float | `-0.5` | 7d pct change threshold for DOWN classification |

---

## Security Considerations

- NewsAPI key stored exclusively in Databricks Secrets — never in code, config files, or notebooks
- `catalog.yaml` and `settings.yaml` are safe to commit (no credentials)
- All Delta tables registered in Hive metastore — access controlled by Databricks workspace permissions
- `yfinance` requires no credentials — no secrets management needed
- No user-facing API surface — single-user notebook project; no auth layer needed

---

## Observability

| Aspect | Implementation |
|--------|----------------|
| Logging | Print-based structured logging via `src/utils/logger.py` with `[stage][timestamp]` prefix; visible in Databricks notebook output |
| Row counts | `merge_into_delta()` returns post-merge row count; logged at each stage |
| Run tracking | `run_id` generated at pipeline start (`YYYYMMDD_HHMMSS`); passed to all stages via notebook shared scope |
| Error visibility | Exceptions bubble up to notebook cell output; failed cells halt `%run` chain with clear traceback |
| Future: LangFuse / MLflow | Not in scope for MVP; structured logging format designed to be LangFuse-compatible when AI Agent is added |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-02 | design-agent | Initial version from DEFINE_FINANCIAL_LAKEHOUSE.md |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_FINANCIAL_LAKEHOUSE.md`