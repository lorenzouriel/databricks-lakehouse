# Databricks notebook source
# DBTITLE 1,Financial Lakehouse — Master Pipeline Orchestrator
#
# Run this notebook to execute the full raw → bronze → silver → gold pipeline.
#
# Prerequisites:
#   1. Databricks Secret set up for NewsAPI key:
#      dbutils.secrets.put(scope="financial-lakehouse", key="newsapi-key", string_value="<your-key>")
#   2. config/catalog.yaml updated with your assets of interest
#   3. config/settings.yaml tuned for lookback window and thresholds
#
# Each stage is called via %run in the same Spark session for Community Edition compatibility.

# COMMAND ----------
import time
from datetime import datetime

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
_pipeline_start = time.time()

print("=" * 70)
print(f"  FINANCIAL LAKEHOUSE PIPELINE")
print(f"  Run ID  : {RUN_ID}")
print(f"  Started : {datetime.now().isoformat()}")
print("=" * 70)

# COMMAND ----------
# DBTITLE 1,Stage 0 — Setup Catalog
print(f"\n{'─'*70}")
print(f"[pipeline] Stage 0: Setup Catalog")
print(f"{'─'*70}")
_t0 = time.time()

# MAGIC %run ./00_setup_catalog

print(f"[pipeline] Stage 0 done in {round(time.time() - _t0, 1)}s")

# COMMAND ----------
# DBTITLE 1,Stage 1 — Ingest Raw
print(f"\n{'─'*70}")
print(f"[pipeline] Stage 1: Ingest Raw (yfinance + NewsAPI)")
print(f"{'─'*70}")
_t1 = time.time()

# MAGIC %run ./01_ingest_raw

print(f"[pipeline] Stage 1 done in {round(time.time() - _t1, 1)}s")

# COMMAND ----------
# DBTITLE 1,Stage 2 — Bronze
print(f"\n{'─'*70}")
print(f"[pipeline] Stage 2: Bronze (schema enforcement + deduplication)")
print(f"{'─'*70}")
_t2 = time.time()

# MAGIC %run ./02_bronze

print(f"[pipeline] Stage 2 done in {round(time.time() - _t2, 1)}s")

# COMMAND ----------
# DBTITLE 1,Stage 3 — Silver
print(f"\n{'─'*70}")
print(f"[pipeline] Stage 3: Silver (normalization + keyword matching)")
print(f"{'─'*70}")
_t3 = time.time()

# MAGIC %run ./03_silver

print(f"[pipeline] Stage 3 done in {round(time.time() - _t3, 1)}s")

# COMMAND ----------
# DBTITLE 1,Stage 4 — Gold
print(f"\n{'─'*70}")
print(f"[pipeline] Stage 4: Gold (trend summaries + news aggregation)")
print(f"{'─'*70}")
_t4 = time.time()

# MAGIC %run ./04_gold

print(f"[pipeline] Stage 4 done in {round(time.time() - _t4, 1)}s")

# COMMAND ----------
# DBTITLE 1,Pipeline Summary
total_elapsed = round(time.time() - _pipeline_start, 1)

print(f"\n{'=' * 70}")
print(f"  PIPELINE COMPLETE")
print(f"  Run ID   : {RUN_ID}")
print(f"  Finished : {datetime.now().isoformat()}")
print(f"  Total    : {total_elapsed}s")
print(f"{'=' * 70}")

print("\nGold layer preview:")
spark.table("financial_lakehouse.gold_price_trend_summary") \
    .orderBy("ticker") \
    .select("ticker", "run_date", "adj_close", "pct_change_7d", "pct_change_30d", "trend_direction") \
    .show(20, truncate=False)
