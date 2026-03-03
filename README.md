# Financial Lakehouse

> A catalog-driven financial data pipeline built on Databricks and Delta Lake. Monitor stocks, crypto, FX rates, and financial news through a raw → bronze → silver → gold medallion architecture — producing trend-ready tables for AI Agent or dashboard consumption.

---

## Overview

Financial Lakehouse ingests daily market data and financial news for any set of assets you define, transforms them through four medallion layers, and surfaces clean, summarized Gold tables optimized for trend monitoring.

The pipeline is **catalog-driven**: add a ticker to `config/catalog.yaml` and the entire pipeline — raw ingestion, schema enforcement, normalization, and trend computation — automatically processes it on the next run.

**Data sources:**
- **Yahoo Finance** (`yfinance`) — daily OHLCV for stocks, crypto, and FX pairs (no API key required)
- **NewsAPI** — financial news headlines filtered by per-asset keywords

**Target platform:** Databricks Community / Personal Edition — no DLT, no Databricks Jobs required.

---

## Architecture

```
config/catalog.yaml
        |
        v (00_setup_catalog)
  catalog [Delta]
        |
        v (01_ingest_raw)
yfinance --> raw_market_data [Delta]
NewsAPI  --> raw_news        [Delta]
        |
        v (02_bronze)
  bronze_market_data [Delta]  <- schema enforced, deduplicated
  bronze_news        [Delta]  <- schema enforced, deduplicated
        |
        v (03_silver)
  silver_market_data [Delta]  <- adj_close, pct_change_1d, 30d avg volume
  silver_news        [Delta]  <- matched_asset_ids[], keyword correlation
        |
        v (04_gold)
  gold_price_trend_summary [Delta]  <- 7d / 30d / 90d trends, UP/DOWN/FLAT
  gold_news_summary        [Delta]  <- headline count, top sources, samples
        |
        v
  AI Agent / Dashboard  (future)
```

All 9 Delta tables live in the `financial_lakehouse` Hive database. Every write uses `MERGE INTO` for idempotency — re-running the pipeline on the same day produces identical results.

---

## Features

- **Catalog-driven** — one YAML file controls what gets monitored; add a ticker and it flows through all layers automatically
- **Four asset types** — stocks (`AAPL`), crypto (`BTC-USD`), FX pairs (`EURUSD=X`), news keywords
- **Medallion architecture** — raw → bronze → silver → gold with clear data contracts at each boundary
- **Idempotent writes** — Delta MERGE prevents duplicates on re-runs
- **Auto lookback** — 90-day history on first run, 3-day incremental on subsequent runs
- **News correlation** — headlines linked to catalog assets via configurable keyword matching
- **Trend scoring** — 7d / 30d / 90d percent change with UP / DOWN / FLAT classification
- **AI-agent-ready gold tables** — `sample_headlines` and `top_sources` arrays designed for LLM context injection
- **Graceful degradation** — individual ticker or API failures are logged and skipped; pipeline continues

---

## Project Structure

```
financial-lakehouse/
├── config/
│   ├── catalog.yaml          # Assets to monitor (edit this to add tickers)
│   └── settings.yaml         # Pipeline tuning (lookback, thresholds, API config)
├── notebooks/
│   ├── 00_setup_catalog.py   # Load catalog.yaml -> Delta catalog table
│   ├── 01_ingest_raw.py      # Fetch from yfinance + NewsAPI -> raw Delta tables
│   ├── 02_bronze.py          # Schema enforcement, deduplication, metadata
│   ├── 03_silver.py          # Price normalization, news keyword matching
│   ├── 04_gold.py            # Trend summaries, news aggregation
│   └── 99_run_pipeline.py    # Master orchestrator -- run this notebook
├── src/
│   ├── fetchers/
│   │   ├── yfinance_fetcher.py   # Yahoo Finance OHLCV fetcher
│   │   └── news_fetcher.py       # NewsAPI article fetcher
│   └── utils/
│       ├── catalog_reader.py     # Read and filter catalog Delta table
│       ├── delta_utils.py        # Delta table helpers (create, MERGE, count)
│       ├── logger.py             # Structured pipeline logging
│       └── settings_loader.py    # Load and validate settings.yaml
├── tests/
│   ├── conftest.py               # Shared pytest fixtures (SparkSession, samples)
│   ├── fixtures/                 # Sample data for tests
│   └── test_*.py                 # 52 unit tests across 6 test files
└── requirements.txt
```

---

## Databricks Setup

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Databricks account | [Community Edition](https://community.cloud.databricks.com/) is free and sufficient |
| Python 3.10+ | Provided by Databricks Runtime 13.x+ |
| NewsAPI key (optional) | Free developer key from [newsapi.org](https://newsapi.org) — pipeline runs without it (news ingestion is skipped) |

---

### Step 1 — Create a Databricks Cluster

1. Log in to your Databricks workspace
2. Go to **Compute** → **Create compute**
3. Configure the cluster:
   - **Runtime:** Databricks Runtime 13.x or higher (includes Delta Lake and PySpark)
   - **Node type:** Single node is sufficient for this project
   - **Terminate after:** 60 minutes of inactivity (Community Edition)
4. Click **Create compute**

---

### Step 2 — Clone the Repository into Databricks Repos

1. In the left sidebar, click **Workspace** → **Repos**
2. Click **Add Repo**
3. Paste the Git repository URL and click **Create Repo**
4. The repo will be cloned to `/Workspace/Repos/<your-username>/financial-lakehouse/`

> **Alternative:** If you don't use Git with Databricks, upload the files manually via **Workspace** → **Import** → upload as a `.zip`.

---

### Step 3 — Install Python Dependencies

Open any notebook in the repo and run this in the first cell:

```python
%pip install yfinance newsapi-python pyyaml
```

Or install for the entire cluster via the cluster's **Libraries** tab:
- PyPI: `yfinance`
- PyPI: `newsapi-python`
- PyPI: `pyyaml`

> `pyspark` and `delta-spark` are **pre-installed** in the Databricks Runtime — do not install them separately.

---

### Step 4 — Configure the NewsAPI Secret (Optional)

Store your NewsAPI key in Databricks Secrets so it is never committed to Git.

**Option A — Databricks CLI (recommended):**

```bash
# Install the CLI locally if needed
pip install databricks-cli

# Configure authentication
databricks configure --token

# Create a secret scope
databricks secrets create-scope --scope financial-lakehouse

# Store the API key
databricks secrets put --scope financial-lakehouse --key newsapi-key --string-value "<your-newsapi-key>"
```

**Option B — Databricks UI:**

1. Navigate to `https://<your-workspace>.azuredatabricks.net/#secrets/createScope`
2. Create a scope named `financial-lakehouse`
3. Use the Secrets API or CLI to add the key (the UI only creates scopes, not individual secrets)

**Option C — Notebook (temporary, for testing only):**

```python
# Run once in a notebook — never commit this code
dbutils.secrets.put(scope="financial-lakehouse", key="newsapi-key", string_value="<your-key>")
```

> If no secret is configured, the pipeline runs without news ingestion and logs a warning. Market data (stocks, crypto, FX) is always fetched — no API key needed.

---

### Step 5 — Configure Your Asset Catalog

Edit [config/catalog.yaml](config/catalog.yaml) to define what you want to monitor:

```yaml
assets:
  stocks:
    - id: "AAPL"                         # yfinance ticker symbol
      display_name: "Apple Inc."
      active: true
      news_keywords: ["Apple", "AAPL"]   # Keywords matched against news headlines

  crypto:
    - id: "BTC-USD"
      display_name: "Bitcoin"
      active: true
      news_keywords: ["Bitcoin", "BTC"]

  fx:
    - id: "EURUSD=X"
      display_name: "EUR/USD"
      active: true
      news_keywords: ["Euro", "ECB"]
```

**Asset type reference:**

| Type | `id` Format | Examples |
|------|-------------|---------|
| Stock | `TICKER` | `AAPL`, `MSFT`, `NVDA`, `TSLA` |
| Crypto | `TICKER-USD` | `BTC-USD`, `ETH-USD`, `SOL-USD` |
| FX pair | `PAIRNAME=X` | `EURUSD=X`, `GBPUSD=X`, `JPYUSD=X` |

> Set `active: false` to stop processing an asset without removing it from the file.

---

### Step 6 — Run the Pipeline

Open `notebooks/99_run_pipeline.py` in Databricks and click **Run All**.

The master notebook calls each stage in sequence using `%run`:

```
Stage 0: 00_setup_catalog  -> loads catalog.yaml into Delta
Stage 1: 01_ingest_raw     -> fetches yfinance + NewsAPI data
Stage 2: 02_bronze         -> enforces schema, deduplicates
Stage 3: 03_silver         -> normalizes prices, matches news keywords
Stage 4: 04_gold           -> computes 7d/30d/90d trends, aggregates news
```

Expected runtime: **2–5 minutes** for the default catalog of 10 assets on a Community Edition single-node cluster.

---

### Step 7 — Verify the Results

After the pipeline completes, query the Gold layer in a new notebook:

```python
# Price trends for all monitored assets
spark.table("financial_lakehouse.gold_price_trend_summary") \
    .orderBy("ticker") \
    .select("ticker", "run_date", "adj_close", "pct_change_7d", "pct_change_30d", "trend_direction") \
    .show(20, truncate=False)
```

```python
# News summary for a specific asset
spark.table("financial_lakehouse.gold_news_summary") \
    .filter("asset_id = 'BTC-USD'") \
    .orderBy("summary_date", ascending=False) \
    .show(10, truncate=False)
```

```sql
-- SQL equivalent (works in Databricks SQL editor)
SELECT ticker, run_date, pct_change_7d, pct_change_30d, trend_direction
FROM financial_lakehouse.gold_price_trend_summary
ORDER BY ABS(pct_change_7d) DESC
LIMIT 20;
```

---

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: yfinance` | Dependencies not installed | Run `%pip install yfinance newsapi-python pyyaml` in the first cell |
| `AnalysisException: Table not found` | Pipeline hasn't run yet | Run `00_setup_catalog.py` first, then the full pipeline |
| `[WARN] NewsAPI key not found` | Secret not configured | See Step 4; news is optional — market data still runs |
| `No data returned for <ticker>` | Invalid ticker symbol | Check the ticker format in `catalog.yaml` against [Yahoo Finance](https://finance.yahoo.com) |
| `Catalog is empty` | `catalog.yaml` has no active entries | Add at least one asset with `active: true` |
| Cluster terminates mid-run | Community Edition 2-hour limit | Restart cluster and re-run — pipeline is idempotent |

---

## Configuration Reference

### `config/catalog.yaml` — Asset Registry

The central hub. Every asset here is processed on each pipeline run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | yfinance ticker (e.g., `AAPL`, `BTC-USD`, `EURUSD=X`) |
| `display_name` | string | No | Human-readable label |
| `active` | boolean | Yes | Set to `false` to pause without deleting |
| `news_keywords` | list[string] | No | Keywords matched against news headline + description |

### `config/settings.yaml` — Pipeline Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `pipeline.database_name` | `financial_lakehouse` | Hive database for all Delta tables |
| `pipeline.lookback_days_initial` | `90` | History window on first run (new asset) |
| `pipeline.lookback_days_incremental` | `3` | History window on re-runs (overlap for safety) |
| `pipeline.run_date` | `null` (today) | Override to `YYYY-MM-DD` for backfill |
| `news.secret_scope` | `financial-lakehouse` | Databricks Secret scope name |
| `news.max_articles_per_keyword` | `20` | Max articles fetched per keyword per run |
| `gold.trend_thresholds.up_pct` | `0.5` | 7d % change above this → `UP` |
| `gold.trend_thresholds.down_pct` | `-0.5` | 7d % change below this → `DOWN` |

---

## Delta Table Reference

| Table | Layer | Key Columns | Merge Keys |
|-------|-------|-------------|------------|
| `catalog` | — | `asset_id`, `asset_type`, `news_keywords[]` | `asset_id` |
| `raw_market_data` | Raw | `ticker`, `date`, OHLCV, `adj_close` | `(ticker, date)` |
| `raw_news` | Raw | `article_id`, `title`, `source`, `published_at` | `article_id` |
| `bronze_market_data` | Bronze | + `asset_type`, `bronze_ts` | `(ticker, date)` |
| `bronze_news` | Bronze | + `bronze_ts` | `article_id` |
| `silver_market_data` | Silver | `pct_change_1d`, `avg_volume_30d` | `(ticker, date)` |
| `silver_news` | Silver | `matched_asset_ids[]` | `article_id` |
| `gold_price_trend_summary` | Gold | `pct_change_7d/30d/90d`, `trend_direction` | `(ticker, run_date)` |
| `gold_news_summary` | Gold | `headline_count`, `sample_headlines[]`, `top_sources[]` | `(asset_id, summary_date)` |

---

## Development

### Local Setup

```bash
git clone <repo-url>
cd financial-lakehouse
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running Tests

```bash
pytest tests/ -v
```

Tests use a local PySpark session (no Databricks connection required). The `tests/fixtures/` directory contains synthetic OHLCV and news data for offline testing.

```bash
# Run a specific test file
pytest tests/test_silver_matching.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Test Coverage

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_yfinance_fetcher.py` | 7 | OHLCV fetching, column normalization, error handling |
| `test_news_fetcher.py` | 8 | Article fetching, ID generation, deduplication |
| `test_catalog_reader.py` | 12 | Catalog filtering, ticker/keyword extraction |
| `test_delta_utils.py` | 9 | Delta MERGE, idempotency, row count |
| `test_silver_matching.py` | 7 | Keyword UDF, case insensitivity, null handling |
| `test_gold_trends.py` | 9 | Window functions, pct_change math, trend direction |

---

## Roadmap

The pipeline is designed to feed these future features:

- **AI Agent** — Claude/GPT agent querying gold tables to answer trend questions (`/define` in progress)
- **Dashboard** — Databricks SQL dashboard or Streamlit app for visual trend monitoring
- **Delta Live Tables** — migrate from notebook `%run` orchestration to DLT for production deployment
- **Alerts** — notify on significant trend changes (UP/DOWN threshold crossings)

---

## API Constraints

| Source | Limit | Impact |
|--------|-------|--------|
| Yahoo Finance (`yfinance`) | Informal ~2000 req/day | No practical limit for ≤50 tickers at daily granularity |
| NewsAPI (free tier) | 100 requests/day | Limits to ~100 unique keywords per day; sufficient for a personal catalog |
| NewsAPI (free tier) | 1-month lookback | Initial backfill limited to 30 days of news history |

---

## License

This project is a portfolio demonstration. See [LICENSE](LICENSE) for details.
