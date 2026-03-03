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
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DateType, DoubleType, LongType, TimestampType, ArrayType
)

from src.utils.settings_loader import load_settings, get_database_name
from src.utils.catalog_reader import read_active_catalog, build_keyword_to_asset_map
from src.utils.delta_utils import ensure_database, merge_into_delta, table_has_data
from src.utils.logger import PipelineLogger

# COMMAND ----------
# DBTITLE 1,Load settings + catalog
settings = load_settings()
DB = get_database_name(settings)
log = PipelineLogger(stage="03_silver")
log.stage_start()

ensure_database(spark, DB)

catalog = read_active_catalog(spark, DB)

# COMMAND ----------
# DBTITLE 1,Silver — market data (price normalization)
if not table_has_data(spark, f"{DB}.bronze_market_data"):
    log.warning("bronze_market_data is empty — skipping silver market transform")
else:
    ticker_window = Window.partitionBy("ticker").orderBy("date")

    silver_market = (
        spark.table(f"{DB}.bronze_market_data")
        .withColumn(
            "pct_change_1d",
            F.round(
                (F.col("adj_close") - F.lag("adj_close", 1).over(ticker_window))
                / F.lag("adj_close", 1).over(ticker_window) * 100,
                4,
            ),
        )
        .withColumn(
            "avg_volume_30d",
            F.round(
                F.avg("volume").over(ticker_window.rowsBetween(-29, 0)),
                0,
            ),
        )
        .select(
            "ticker",
            "date",
            "adj_close",
            "pct_change_1d",
            F.col("volume").cast(LongType()),
            F.col("avg_volume_30d").cast(DoubleType()),
            "asset_type",
        )
    )

    market_count = merge_into_delta(
        spark=spark,
        source_df=silver_market,
        full_table_name=f"{DB}.silver_market_data",
        merge_keys=["ticker", "date"],
        partition_by=["ticker"],
    )
    log.rows(f"{DB}.silver_market_data", market_count)

# COMMAND ----------
# DBTITLE 1,Silver — news (keyword matching to catalog assets)
if not table_has_data(spark, f"{DB}.bronze_news"):
    log.warning("bronze_news is empty — skipping silver news transform")
else:
    keyword_map = build_keyword_to_asset_map(catalog)
    kw_broadcast = spark.sparkContext.broadcast(keyword_map)

    @F.udf(ArrayType(StringType()))
    def find_matched_assets(title, description):
        """Case-insensitive keyword scan → list of matching asset_ids."""
        text = f"{title or ''} {description or ''}".lower()
        matched = list({
            asset_id
            for kw, asset_id in kw_broadcast.value.items()
            if kw in text
        })
        return matched if matched else ["__unmatched__"]

    silver_news = (
        spark.table(f"{DB}.bronze_news")
        .withColumn(
            "matched_asset_ids",
            find_matched_assets(F.col("title"), F.col("description")),
        )
        .select(
            "article_id",
            "title",
            "description",
            "published_at",
            "source",
            "query_keyword",
            "matched_asset_ids",
        )
    )

    news_count = merge_into_delta(
        spark=spark,
        source_df=silver_news,
        full_table_name=f"{DB}.silver_news",
        merge_keys=["article_id"],
    )
    log.rows(f"{DB}.silver_news", news_count)

log.stage_end()
