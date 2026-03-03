# Databricks notebook source
# COMMAND ----------
# DBTITLE 1,Setup — Add repo root to sys.path
import sys
import os

try:
    ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
    notebook_path = ctx.notebookPath().get()
    repo_root = "/Workspace" + notebook_path.rsplit("/notebooks/", 1)[0]
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
except Exception:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

# COMMAND ----------
# DBTITLE 1,Imports
from pyspark.sql import functions as F, Window

from src.utils.settings_loader import load_settings, get_database_name, get_run_date
from src.utils.delta_utils import ensure_database, merge_into_delta, table_has_data
from src.utils.logger import PipelineLogger

# COMMAND ----------
# DBTITLE 1,Load settings
settings = load_settings()
DB = get_database_name(settings)
RUN_DATE = get_run_date(settings)
UP_PCT = settings["gold"]["trend_thresholds"]["up_pct"]
DOWN_PCT = settings["gold"]["trend_thresholds"]["down_pct"]
SAMPLE_SIZE = settings["gold"]["news_sample_size"]
TOP_SOURCES = settings["gold"]["top_sources_count"]

log = PipelineLogger(stage="04_gold")
log.stage_start()

ensure_database(spark, DB)

# COMMAND ----------
# DBTITLE 1,Gold — price trend summary (7d / 30d / 90d)
if not table_has_data(spark, f"{DB}.silver_market_data"):
    log.warning("silver_market_data is empty — skipping gold price trends")
else:
    ticker_window = Window.partitionBy("ticker").orderBy("date")
    latest_window = Window.partitionBy("ticker").orderBy(F.desc("date"))

    price_trends = (
        spark.table(f"{DB}.silver_market_data")
        .withColumn("adj_close_7d_ago",  F.lag("adj_close", 7).over(ticker_window))
        .withColumn("adj_close_30d_ago", F.lag("adj_close", 30).over(ticker_window))
        .withColumn("adj_close_90d_ago", F.lag("adj_close", 90).over(ticker_window))
        .withColumn(
            "pct_change_7d",
            F.round(
                (F.col("adj_close") - F.col("adj_close_7d_ago")) / F.col("adj_close_7d_ago") * 100,
                2,
            ),
        )
        .withColumn(
            "pct_change_30d",
            F.round(
                (F.col("adj_close") - F.col("adj_close_30d_ago")) / F.col("adj_close_30d_ago") * 100,
                2,
            ),
        )
        .withColumn(
            "pct_change_90d",
            F.round(
                (F.col("adj_close") - F.col("adj_close_90d_ago")) / F.col("adj_close_90d_ago") * 100,
                2,
            ),
        )
        .withColumn(
            "trend_direction",
            F.when(F.col("pct_change_7d") > UP_PCT, "UP")
             .when(F.col("pct_change_7d") < DOWN_PCT, "DOWN")
             .when(F.col("pct_change_7d").isNotNull(), "FLAT")
             .otherwise(None),
        )
        .withColumn("_rank", F.rank().over(latest_window))
        .filter(F.col("_rank") == 1)
        .withColumn("run_date", F.lit(RUN_DATE).cast("date"))
        .select(
            "ticker",
            "run_date",
            F.round("adj_close", 4).alias("adj_close"),
            "pct_change_7d",
            "pct_change_30d",
            "pct_change_90d",
            "avg_volume_30d",
            "trend_direction",
            "asset_type",
        )
    )

    trend_count = merge_into_delta(
        spark=spark,
        source_df=price_trends,
        full_table_name=f"{DB}.gold_price_trend_summary",
        merge_keys=["ticker", "run_date"],
    )
    log.rows(f"{DB}.gold_price_trend_summary", trend_count)

    log.info("Top movers today:")
    price_trends.orderBy(F.abs("pct_change_7d").desc()).show(10, truncate=False)

# COMMAND ----------
# DBTITLE 1,Gold — news summary (headline aggregation per asset per day)
if not table_has_data(spark, f"{DB}.silver_news"):
    log.warning("silver_news is empty — skipping gold news summary")
else:
    news_exploded = (
        spark.table(f"{DB}.silver_news")
        .withColumn("asset_id", F.explode("matched_asset_ids"))
        .filter(F.col("asset_id") != "__unmatched__")
        .withColumn("summary_date", F.to_date("published_at"))
        .filter(F.col("summary_date").isNotNull())
    )

    news_summary = (
        news_exploded
        .groupBy("asset_id", "summary_date")
        .agg(
            F.count("article_id").alias("headline_count"),
            F.slice(
                F.collect_list("source"),
                1,
                TOP_SOURCES,
            ).alias("top_sources"),
            F.slice(
                F.collect_list("title"),
                1,
                SAMPLE_SIZE,
            ).alias("sample_headlines"),
        )
    )

    news_count = merge_into_delta(
        spark=spark,
        source_df=news_summary,
        full_table_name=f"{DB}.gold_news_summary",
        merge_keys=["asset_id", "summary_date"],
    )
    log.rows(f"{DB}.gold_news_summary", news_count)

log.stage_end()
