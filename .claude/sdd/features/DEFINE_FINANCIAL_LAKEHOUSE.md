# DEFINE: Financial Lakehouse Pipeline

> A catalog-driven Databricks pipeline that ingests financial market data and news, transforms it through a raw → bronze → silver → gold medallion architecture, and produces trend-ready Delta tables for future AI Agent or Dashboard consumption.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | FINANCIAL_LAKEHOUSE |
| **Date** | 2026-03-02 |
| **Author** | define-agent |
| **Status** | Ready for Design |
| **Clarity Score** | 15/15 |
| **Source** | BRAINSTORM_FINANCIAL_LAKEHOUSE.md |

---

## Problem Statement

There is no single place to monitor financial trends across asset classes (stocks, crypto, currencies, financial news). Manually gathering and comparing data from multiple sources is tedious and error-prone. A structured lakehouse pipeline is needed that automatically ingests, cleans, and aggregates this data into Gold-layer tables optimized for trend monitoring and future AI-powered querying.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| Portfolio developer (self) | Builder and primary consumer | No centralized view of trends across stocks, crypto, FX, and news — must check multiple sources manually |
| Future AI Agent | Automated consumer of Gold tables | Needs clean, well-structured, summarized tables with clear semantics to answer trend and correlation questions |

---

## Goals

| Priority | Goal |
|----------|------|
| **MUST** | Catalog-driven pipeline: adding a ticker/keyword to `catalog.yaml` triggers end-to-end processing for that asset |
| **MUST** | Raw layer: ingest `yfinance` OHLCV data and NewsAPI headlines with zero data loss |
| **MUST** | Bronze layer: enforce schema, add ingestion metadata, deduplicate records |
| **MUST** | Silver layer: normalize market prices (percent change / adjusted close), correlate news headlines to catalog assets by keyword match |
| **MUST** | Gold layer: produce per-asset trend summary tables (7d / 30d / 90d metrics) and a daily news headline aggregation table |
| **MUST** | All layers stored as Delta tables with schema enforcement enabled |
| **SHOULD** | Pipeline is idempotent — re-running on the same day produces identical results (no duplicates) |
| **SHOULD** | Historical backfill support — configurable lookback period for initial load |
| **COULD** | Delta tables partitioned by date for efficient Gold-layer queries |
| **COULD** | Per-run pipeline execution log (what ran, row counts, errors) |

---

## Success Criteria

Measurable outcomes that must be true for MVP to be complete:

- [ ] Running `99_run_pipeline.py` with a catalog of ≥4 assets (1 stock, 1 crypto, 1 FX, 1 news keyword) completes without errors
- [ ] Raw layer captures 100% of records returned by `yfinance` and NewsAPI (no silent drops)
- [ ] Bronze layer rejects and logs records with null `ticker` or null `date`; pipeline continues without stopping
- [ ] Silver layer produces adjusted close price and daily percent change for all market assets
- [ ] Silver layer links each news headline to ≥1 catalog asset via keyword match (or marks as `unmatched`)
- [ ] Gold layer `price_trend_summary` table contains 7d, 30d, and 90d percent change per ticker, per run date
- [ ] Gold layer `news_summary` table contains headline count and top keywords per catalog asset per day
- [ ] Adding a new ticker to `catalog.yaml` and re-running the pipeline results in that ticker appearing in all 4 layers
- [ ] Re-running pipeline on the same day (idempotency): row counts in all layers remain identical to the first run
- [ ] All Delta tables have `enforceSchema = true` and reject out-of-schema writes

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | Full pipeline run — happy path | `catalog.yaml` contains: `AAPL` (stock), `BTC-USD` (crypto), `EURUSD=X` (FX), `"Apple"` (news keyword) | `99_run_pipeline.py` is executed | All 4 layers have tables created/updated; no exceptions thrown; Gold `price_trend_summary` has rows for AAPL, BTC-USD, EURUSD=X |
| AT-002 | New asset added to catalog | Pipeline has already run for AAPL; `MSFT` is added to `catalog.yaml` | `00_setup_catalog.py` then full pipeline run | MSFT appears in all 4 layers; AAPL data is intact; no duplicate rows in any layer |
| AT-003 | Idempotency on same-day re-run | Pipeline ran successfully once today | `99_run_pipeline.py` runs again with same catalog | Row counts in raw, bronze, silver, gold are identical to the first run (deduplication prevents duplicates) |
| AT-004 | Bronze schema rejection | Bronze table has enforced schema; `yfinance` returns a record missing the `volume` column | Bronze notebook processes the batch | Missing-column records are filtered/logged; valid records are written; pipeline does not crash |
| AT-005 | Gold trend computation with sufficient history | Silver layer has ≥90 days of price history for `AAPL` | `04_gold.py` runs | `price_trend_summary` contains rows with `pct_change_7d`, `pct_change_30d`, `pct_change_90d` all non-null for AAPL |
| AT-006 | Gold trend computation with insufficient history | Silver layer has only 10 days of history for a new asset (e.g., first run) | `04_gold.py` runs | 7d metric is computed; 30d and 90d are `null` (not enough data); no error thrown |
| AT-007 | News keyword matching | News keyword `"Bitcoin"` is in catalog; NewsAPI returns headline "Bitcoin surges past $100k" | Silver notebook runs | Headline is linked to `BTC-USD` asset (or `"Bitcoin"` keyword entry) in `news_silver` table |
| AT-008 | Empty catalog graceful handling | `catalog.yaml` exists but contains no assets | `99_run_pipeline.py` runs | Pipeline completes with a log message "Catalog is empty — nothing to process"; no errors |

---

## Out of Scope

Explicitly NOT included in this feature:

- AI Agent / LLM integration (next feature, separate `/define`)
- Dashboard or BI visualization (Streamlit, Databricks SQL, Power BI)
- Real-time or streaming data ingestion (Kafka, Spark Structured Streaming)
- ML forecasting or anomaly detection models
- Automated alerting (email, Slack, PagerDuty)
- Portfolio management (P&L tracking, cost basis, position sizing)
- Intraday data (only daily OHLCV from `yfinance`)
- Multi-exchange order book data
- Options, futures, or derivatives data
- Authentication / access control (single-user project)
- Unity Catalog or data governance tooling (Community Edition does not support it)

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| Technical | Must run on Databricks Community Edition | No DLT pipelines, no Databricks Jobs scheduler, no Unity Catalog; all orchestration is manual (or via notebook `%run`) |
| Technical | `yfinance` free tier — daily OHLCV only | No intraday data; data freshness is T-1 (previous day's close) |
| Technical | NewsAPI free developer tier | Max 100 requests/day; 1-month lookback only; no full article body (headlines + description only) |
| Technical | No external orchestration | No Airflow, Prefect, or cron scheduling; pipeline triggered manually or via Databricks Workflow if upgraded |
| Technical | Python-only notebooks | PySpark/pandas for transformations; no Scala or SQL-only notebooks |
| Resource | No infrastructure cost budget | All tooling must be free tier (Databricks Community, yfinance, NewsAPI dev) |

---

## Technical Context

| Aspect | Value | Notes |
|--------|-------|-------|
| **Deployment Location** | `notebooks/` (primary) + `src/` (library code) + `config/` | Databricks notebooks are the execution unit; shared library code lives in `src/` |
| **KB Domains** | medallion-architecture, delta-lake, python-developer | Medallion patterns for layer design; Delta Lake for table management |
| **IaC Impact** | None | Databricks Community Edition — no Terraform needed; cluster is pre-provisioned |
| **Runtime** | Databricks Spark cluster (Community Edition) | Cluster auto-terminates after 2 hours of inactivity |
| **Storage** | Databricks DBFS or managed Delta tables | Tables registered in Hive metastore (Community Edition) |
| **Language** | Python 3.x (PySpark + pandas) | `yfinance`, `newsapi-python`, `delta-spark` as key dependencies |

---

## Data Model Overview

### Catalog Table (`catalog`)

| Column | Type | Description |
|--------|------|-------------|
| `asset_id` | STRING | Unique identifier (e.g., `AAPL`, `BTC-USD`, `EURUSD=X`) |
| `asset_type` | STRING | `stock` \| `crypto` \| `fx` \| `news_keyword` |
| `display_name` | STRING | Human-readable name (e.g., `Apple Inc.`) |
| `news_keywords` | ARRAY[STRING] | Keywords to match in NewsAPI queries |
| `active` | BOOLEAN | Whether this asset is currently being processed |
| `added_date` | DATE | When this asset was added to the catalog |

### Layer Schemas (overview)

**Raw Layer** — as-is from API, minimal transformation:
- `raw_market_data`: ticker, date, open, high, low, close, adj_close, volume, ingestion_ts
- `raw_news`: article_id, title, description, source, url, published_at, query_keyword, ingestion_ts

**Bronze Layer** — typed, deduplicated, metadata-enriched:
- `bronze_market_data`: all raw columns + `asset_type`, `bronze_ts`, `source_file`; schema enforced
- `bronze_news`: all raw columns + `bronze_ts`; deduplicated by `article_id`

**Silver Layer** — normalized, correlated, enriched:
- `silver_market_data`: ticker, date, adj_close, pct_change_1d, volume, 30d_avg_volume, asset_type
- `silver_news`: article_id, title, published_at, matched_asset_ids (ARRAY), relevance_score

**Gold Layer** — aggregated, trend-ready, AI-context-friendly:
- `price_trend_summary`: ticker, run_date, pct_change_7d, pct_change_30d, pct_change_90d, avg_volume_30d, trend_direction (UP/DOWN/FLAT)
- `news_summary`: asset_id, summary_date, headline_count, top_sources (ARRAY), sample_headlines (ARRAY[STRING, 3])

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | Databricks Community Edition Spark cluster handles ~20-50 catalog assets without memory issues | May need to batch-process assets or reduce history window | [ ] |
| A-002 | `yfinance` API is accessible without auth and returns consistent OHLCV schema | Pipeline would need fallback source or schema evolution logic | [ ] |
| A-003 | NewsAPI free tier (100 req/day) is sufficient for the number of news keywords in catalog | Would need to either reduce keywords or upgrade to paid tier | [ ] |
| A-004 | Daily batch frequency (once-per-day run) is sufficient granularity for trend monitoring | Would need to redesign for streaming or higher-frequency batch | [x] — confirmed during brainstorm |
| A-005 | Delta Lake is available on Databricks Community Edition | Pipeline cannot use Delta tables if not available; would need Parquet workaround | [ ] |
| A-006 | Hive metastore is available for table registration on Community Edition | Tables would need to be accessed by path instead of by name | [ ] |

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | **3** | Specific pain point: no centralized trend monitoring hub; affects developer and future AI consumer |
| Users | **3** | Two users identified with distinct pain points and data needs |
| Goals | **3** | MoSCoW-prioritized, all MUST goals are pipeline stages with clear deliverables |
| Success | **3** | 10 measurable, testable acceptance criteria; row-count, schema, and behavior checks |
| Scope | **3** | Explicit out-of-scope list (10 items) from YAGNI session; no ambiguity |
| **Total** | **15/15** | Ready for Design phase |

---

## Open Questions

None — all questions resolved during brainstorm session. Ready for Design.

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-02 | define-agent | Initial version from BRAINSTORM_FINANCIAL_LAKEHOUSE.md |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_FINANCIAL_LAKEHOUSE.md`
