# BRAINSTORM: Financial Lakehouse Pipeline

> Exploratory session to clarify intent and approach before requirements capture

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | FINANCIAL_LAKEHOUSE |
| **Date** | 2026-03-02 |
| **Author** | brainstorm-agent |
| **Status** | Ready for Define |

---

## Initial Idea

**Raw Input:**
> Build a project called financial-lakehouse. Develop notebooks that extract and transform financial data and trending data related to crypto, stocks, currencies, and financial news. Create a hub to monitor trends via a centralized `catalog` table. The pipeline queries the catalog and processes the lakehouse for each asset, running a raw → bronze → silver → gold treatment to be queried by an AI Agent or a Dashboard.

**Context Gathered:**
- Project is brand new — empty workspace, only `.claude/` workflow tooling exists
- No existing code, schemas, or data models to carry forward
- Architecture must work on Databricks Community/Personal Edition
- Primary data sources: `yfinance` (stocks, crypto, currencies) + NewsAPI (financial news headlines)
- Consumer: AI Agent (primary), Dashboard (deferred to future iteration)

**Technical Context Observed (for Define):**

| Aspect | Observation | Implication |
|--------|-------------|-------------|
| Likely Location | `notebooks/` + `config/` + `src/` | Standard Databricks project layout |
| Relevant KB Domains | Medallion architecture, Delta Lake, Python | Use Delta tables at each layer |
| IaC Patterns | N/A (Community Edition) | No Terraform needed; cluster managed by Databricks |
| Data Format | Delta tables (managed) | Native Databricks format, ACID transactions |

---

## Discovery Questions & Answers

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Where will notebooks and lakehouse run? | Databricks Community/Personal Edition | Must avoid DLT pipelines (not supported on Community); use regular notebooks |
| 2 | Which financial data APIs? | Yahoo Finance (`yfinance`) + NewsAPI/RSS feeds | No required API keys for `yfinance`; NewsAPI free tier needs a key for dev |
| 3 | What is the primary consumer of the Gold layer? | AI Agent (primary), Dashboard (secondary) | Gold tables must be structured for LLM context injection + SQL queryability |
| 4 | How should the catalog table work? | Static config file (YAML/JSON) loaded into a Delta table | Catalog is version-controlled in `config/catalog.yaml`; pipeline reads from Delta at runtime |
| 5 | Is AI Agent in-scope for this MVP? | No — pipeline only | Gold layer designed to be AI-agent-ready, but agent notebook is a future `/define` |

---

## Sample Data Inventory

> No existing samples available. Will be generated on first pipeline run.

| Type | Location | Count | Notes |
|------|----------|-------|-------|
| Input files | N/A — live API calls | 0 | `yfinance` returns OHLCV DataFrames; NewsAPI returns JSON articles |
| Output examples | To be generated | 0 | First run will seed raw layer; becomes the ground truth |
| Ground truth | N/A | 0 | Accuracy validated by cross-checking with known ticker values |
| Related code | N/A | 0 | Greenfield project |

**How samples will inform the design:**
- `yfinance` output schema (OHLCV columns) is well-documented → defines bronze schema for market data
- NewsAPI response schema is fixed → defines bronze schema for news articles
- First pipeline run output will serve as integration test fixtures

---

## Approaches Explored

### Approach A: Notebooks + Delta Tables ⭐ Recommended

**Description:** Each medallion layer is an independent Databricks notebook. A YAML config seeds a `catalog` Delta table. A master orchestration notebook runs all stages by iterating over catalog entries.

```
config/catalog.yaml           ← assets to monitor (tickers, news keywords)
notebooks/
  00_setup_catalog.py         ← YAML → catalog Delta table
  01_ingest_raw.py            ← yfinance + NewsAPI → raw Delta tables
  02_bronze.py                ← type-cast, metadata, deduplication
  03_silver.py                ← normalize, enrich, news-asset correlation
  04_gold.py                  ← aggregates, trend summaries, AI-ready tables
  99_run_pipeline.py          ← master orchestrator (calls all stages)
src/
  fetchers/
    yfinance_fetcher.py       ← encapsulates yfinance calls
    news_fetcher.py           ← encapsulates NewsAPI calls
  utils/
    catalog_reader.py         ← reads catalog Delta table
config/
  catalog.yaml                ← watched assets definition
requirements.txt
```

**Pros:**
- Works on Databricks Community Edition
- Clean, readable notebook-per-layer structure — great for portfolio
- Each layer independently testable and runnable
- Delta tables provide ACID, time travel, and schema enforcement
- Easy to `/iterate` toward DLT later

**Cons:**
- No automatic scheduling on Community Edition (must run manually)
- No built-in data quality checks (must implement manually in notebooks)

**Why Recommended:** Best fit for a portfolio project on Community Edition. Clear medallion pattern, practical scope, showcases Python + Delta Lake skills.

---

### Approach B: Delta Live Tables (DLT) Pipeline

**Description:** DLT declarative pipeline for bronze → silver → gold. Raw ingestion remains a notebook. Transformations declared as `@dlt.table` Python decorators.

**Pros:**
- Production-grade pipeline management
- Built-in data quality expectations and lineage
- Automatic dependency resolution between tables

**Cons:**
- Not available on Databricks Community Edition
- More complex setup, DLT-specific Python API to learn
- Overkill for MVP scope

---

### Approach C: Lakeflow + Databricks Jobs

**Description:** Full production setup with Lakeflow pipelines, Databricks Jobs for scheduling, and Unity Catalog for governance.

**Pros:**
- Enterprise-grade, auto-scheduled, full observability

**Cons:**
- Requires paid workspace + Unity Catalog
- Overkill for a portfolio project starting point

---

## Selected Approach

| Attribute | Value |
|-----------|-------|
| **Chosen** | Approach A — Notebooks + Delta Tables |
| **User Confirmation** | 2026-03-02 |
| **Reasoning** | Works on Community Edition, clean medallion structure, right scope for portfolio |

---

## Key Decisions Made

| # | Decision | Rationale | Alternative Rejected |
|---|----------|-----------|----------------------|
| 1 | Databricks Community Edition as target platform | Zero cost, authentic Databricks experience | AWS/GCP (more infra complexity, cost) |
| 2 | `yfinance` as primary market data source | Free, no API key, covers stocks + crypto + FX | Alpha Vantage (rate limits), CoinGecko (crypto-only) |
| 3 | NewsAPI for financial news | Free dev tier, structured JSON, easy to integrate | RSS feeds (more parsing work, less structured) |
| 4 | YAML config → Delta catalog table | Version-controlled, readable, pipeline reads Delta at runtime | Pure Delta table (no version history without Git) |
| 5 | AI Agent deferred to next feature | YAGNI — pipeline must be solid before building consumers | Build agent now (premature, pipeline not validated) |
| 6 | Gold layer designed for LLM context injection | Future-proofing without implementing the agent yet | Generic aggregation tables (would need rework later) |

---

## Features Removed (YAGNI)

| Feature Suggested | Reason Removed | Can Add Later? |
|-------------------|----------------|----------------|
| AI Agent notebook (Claude/GPT querying Gold) | Pipeline must be solid first; agent is a separate concern | Yes — next `/define` |
| Dashboard UI (Streamlit / Databricks SQL) | Secondary consumer, not needed to validate pipeline | Yes |
| Real-time streaming (Kafka / Spark Streaming) | Daily batch is sufficient for trend monitoring | Yes |
| Automated alerting (email/Slack on anomalies) | Adds infra complexity, not core to pipeline | Yes |
| ML forecasting models (LSTM, ARIMA) | Out of scope — this is a data pipeline, not an ML project | Yes |
| Multiple AI provider support | Unnecessary abstraction before first use | Yes |
| Portfolio tracking (P&L, positions, cost basis) | Not requested — monitoring only, not trading | Maybe |

---

## Incremental Validations

| Section | Presented | User Feedback | Adjusted? |
|---------|-----------|---------------|-----------|
| Approach selection (A vs B vs C) | ✅ | Chose Approach A | No |
| YAGNI / scope check | ✅ | Removed AI Agent from MVP | Yes — agent deferred |

---

## Suggested Requirements for /define

### Problem Statement (Draft)
Build a Databricks-based financial data lakehouse that monitors a user-defined catalog of assets (stocks, crypto, currencies, news keywords) and processes them through a raw → bronze → silver → gold pipeline using `yfinance` and NewsAPI, producing gold-layer tables optimized for trend monitoring and future AI Agent querying.

### Target Users (Draft)

| User | Pain Point |
|------|------------|
| Portfolio developer (self) | No single place to monitor financial trends across asset classes |
| Future AI Agent | Needs clean, summarized, contextual Gold tables to answer trend questions |

### Success Criteria (Draft)
- [ ] `catalog.yaml` drives the pipeline end-to-end (add a ticker → it gets processed)
- [ ] Raw layer captures `yfinance` OHLCV data and NewsAPI headlines as-is
- [ ] Bronze layer validates schema, adds ingestion metadata, deduplicates
- [ ] Silver layer normalizes prices (adjusted close), links news to catalog assets by keyword matching
- [ ] Gold layer produces one summary table per asset type with 7/30/90-day trend stats
- [ ] Gold layer includes a `news_sentiment_summary` table (headline aggregation per asset, per day)
- [ ] All layers stored as Delta tables (schema enforcement on)
- [ ] Pipeline runs end-to-end from `99_run_pipeline.py` without errors

### Constraints Identified
- Must run on Databricks Community Edition (no DLT, no Jobs scheduler)
- `yfinance` free tier — no intraday data (daily OHLCV only)
- NewsAPI free tier — 100 requests/day, 1-month lookback, no full article body
- No external orchestration tool (Airflow, Prefect) — manual run or Databricks Workflows if upgraded

### Out of Scope (Confirmed)
- AI Agent / LLM integration (next feature)
- Dashboard / BI visualization (future feature)
- Real-time / streaming data
- ML forecasting or anomaly detection models
- Automated alerting
- Portfolio management (P&L tracking, positions)

---

## Asset Type Coverage (for catalog design)

The catalog will support 4 asset types, each with its own raw/bronze/silver/gold flow:

| Asset Type | Source | Identifier Example | Data |
|---|---|---|---|
| Stock | `yfinance` | `AAPL`, `MSFT`, `NVDA` | Daily OHLCV, volume |
| Crypto | `yfinance` | `BTC-USD`, `ETH-USD` | Daily OHLCV |
| Currency (FX) | `yfinance` | `EURUSD=X`, `GBPUSD=X` | Daily OHLCV |
| News Keywords | NewsAPI | `"Bitcoin"`, `"NVIDIA"` | Headlines, source, published_at |

---

## Session Summary

| Metric | Value |
|--------|-------|
| Questions Asked | 5 |
| Approaches Explored | 3 |
| Features Removed (YAGNI) | 7 |
| Validations Completed | 2 |
| Selected Approach | A — Notebooks + Delta Tables |

---

## Next Step

**Ready for:** `/define .claude/sdd/features/BRAINSTORM_FINANCIAL_LAKEHOUSE.md`
