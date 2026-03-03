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
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DateType, DoubleType, LongType, TimestampType, BooleanType
)

from src.utils.settings_loader import load_settings, get_database_name
from src.utils.catalog_reader import read_active_catalog
from src.utils.delta_utils import ensure_database, merge_into_delta, table_has_data
from src.utils.logger import PipelineLogger

# COMMAND ----------
# DBTITLE 1,Load settings
settings = load_settings()
DB = get_database_name(settings)
log = PipelineLogger(stage="02_bronze")
log.stage_start()

ensure_database(spark, DB)

# COMMAND ----------
# DBTITLE 1,Define bronze schemas
BRONZE_MARKET_SCHEMA = StructType([
    StructField("ticker",       StringType(),    nullable=False),
    StructField("date",         DateType(),      nullable=False),
    StructField("open",         DoubleType(),    nullable=True),
    StructField("high",         DoubleType(),    nullable=True),
    StructField("low",          DoubleType(),    nullable=True),
    StructField("close",        DoubleType(),    nullable=True),
    StructField("adj_close",    DoubleType(),    nullable=True),
    StructField("volume",       LongType(),      nullable=True),
    StructField("asset_type",   StringType(),    nullable=False),
    StructField("bronze_ts",    TimestampType(), nullable=False),
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

# COMMAND ----------
# DBTITLE 1,Build asset_type lookup from catalog
if not table_has_data(spark, f"{DB}.raw_market_data") and not table_has_data(spark, f"{DB}.raw_news"):
    log.warning("Both raw tables are empty — nothing to bronze")
    dbutils.notebook.exit("NO_RAW_DATA")

catalog = read_active_catalog(spark, DB)
ticker_to_type = {a["asset_id"]: a["asset_type"] for a in catalog}
type_map_rows = [(k, v) for k, v in ticker_to_type.items()]
type_map_df = spark.createDataFrame(type_map_rows, ["asset_id", "asset_type"])

# COMMAND ----------
# DBTITLE 1,Bronze — market data
if table_has_data(spark, f"{DB}.raw_market_data"):
    raw_market = spark.table(f"{DB}.raw_market_data")

    bronze_market = (
        raw_market
        .join(type_map_df, raw_market.ticker == type_map_df.asset_id, how="left")
        .drop("asset_id", "ingestion_ts")
        .withColumn("bronze_ts", F.current_timestamp())
        .withColumn("asset_type", F.coalesce(F.col("asset_type"), F.lit("unknown")))
    )

    # Filter rows violating non-nullable constraints
    before_count = bronze_market.count()
    bronze_market = bronze_market.filter(
        F.col("ticker").isNotNull() & F.col("date").isNotNull()
    )
    rejected = before_count - bronze_market.count()
    if rejected > 0:
        log.warning(f"Rejected {rejected} market rows with null ticker or date")

    bronze_market = spark.createDataFrame(bronze_market.rdd, schema=BRONZE_MARKET_SCHEMA)

    market_count = merge_into_delta(
        spark=spark,
        source_df=bronze_market,
        full_table_name=f"{DB}.bronze_market_data",
        merge_keys=["ticker", "date"],
        partition_by=["ticker"],
    )
    log.rows(f"{DB}.bronze_market_data", market_count)
else:
    log.warning("raw_market_data is empty — skipping bronze market transform")

# COMMAND ----------
# DBTITLE 1,Bronze — news
if table_has_data(spark, f"{DB}.raw_news"):
    raw_news = spark.table(f"{DB}.raw_news")

    bronze_news = (
        raw_news
        .dropDuplicates(["article_id"])
        .filter(F.col("article_id").isNotNull())
        .drop("ingestion_ts")
        .withColumn("bronze_ts", F.current_timestamp())
    )

    bronze_news = spark.createDataFrame(bronze_news.rdd, schema=BRONZE_NEWS_SCHEMA)

    news_count = merge_into_delta(
        spark=spark,
        source_df=bronze_news,
        full_table_name=f"{DB}.bronze_news",
        merge_keys=["article_id"],
    )
    log.rows(f"{DB}.bronze_news", news_count)
else:
    log.warning("raw_news is empty — skipping bronze news transform")

log.stage_end()
