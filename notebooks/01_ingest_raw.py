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
# DBTITLE 1,Install dependencies
# MAGIC %pip install yfinance newsapi-python --quiet

# COMMAND ----------
# DBTITLE 1,Imports
from datetime import date, datetime, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DateType, DoubleType, LongType, TimestampType
)

from src.fetchers.yfinance_fetcher import fetch_multiple
from src.fetchers.news_fetcher import fetch_for_keywords
from src.utils.settings_loader import load_settings, get_database_name, get_lookback_days, get_run_date
from src.utils.catalog_reader import read_active_catalog, get_market_tickers, get_news_keywords
from src.utils.delta_utils import ensure_database, merge_into_delta, table_has_data, add_ingestion_timestamp
from src.utils.logger import PipelineLogger

# COMMAND ----------
# DBTITLE 1,Load settings + catalog
settings = load_settings()
DB = get_database_name(settings)
RUN_DATE = get_run_date(settings)
log = PipelineLogger(stage="01_ingest_raw")
log.stage_start()

ensure_database(spark, DB)

catalog = read_active_catalog(spark, DB)
if not catalog:
    log.warning("Catalog is empty — nothing to ingest")
    dbutils.notebook.exit("EMPTY_CATALOG")

log.info(f"Catalog loaded: {len(catalog)} active assets | run_date={RUN_DATE}")

# COMMAND ----------
# DBTITLE 1,Determine date range for ingestion
is_initial = not table_has_data(spark, f"{DB}.raw_market_data")
lookback_days = get_lookback_days(settings, is_initial=is_initial)

end_dt = date.fromisoformat(RUN_DATE)
start_dt = end_dt - timedelta(days=lookback_days)

log.info(f"Fetch window: {start_dt} → {end_dt} | initial_run={is_initial} | lookback={lookback_days}d")

# COMMAND ----------
# DBTITLE 1,Fetch market data (stocks, crypto, FX) via yfinance
tickers = get_market_tickers(catalog)
log.info(f"Fetching OHLCV for {len(tickers)} tickers: {tickers}")

market_pdf = fetch_multiple(tickers, start_date=start_dt, end_date=end_dt)
log.info(f"yfinance returned {len(market_pdf):,} rows across {market_pdf['ticker'].nunique() if not market_pdf.empty else 0} tickers")

# COMMAND ----------
# DBTITLE 1,Write raw_market_data to Delta
RAW_MARKET_SCHEMA = StructType([
    StructField("ticker",       StringType(),    nullable=False),
    StructField("date",         DateType(),      nullable=False),
    StructField("open",         DoubleType(),    nullable=True),
    StructField("high",         DoubleType(),    nullable=True),
    StructField("low",          DoubleType(),    nullable=True),
    StructField("close",        DoubleType(),    nullable=True),
    StructField("adj_close",    DoubleType(),    nullable=True),
    StructField("volume",       LongType(),      nullable=True),
    StructField("ingestion_ts", TimestampType(), nullable=False),
])

if market_pdf.empty:
    log.warning("No market data fetched — skipping raw_market_data write")
else:
    raw_market_df = spark.createDataFrame(market_pdf)
    raw_market_df = raw_market_df.withColumn("date", F.col("date").cast(DateType()))
    raw_market_df = add_ingestion_timestamp(raw_market_df)
    raw_market_df = spark.createDataFrame(raw_market_df.rdd, schema=RAW_MARKET_SCHEMA)

    market_count = merge_into_delta(
        spark=spark,
        source_df=raw_market_df,
        full_table_name=f"{DB}.raw_market_data",
        merge_keys=["ticker", "date"],
        partition_by=["ticker"],
    )
    log.rows(f"{DB}.raw_market_data", market_count)

# COMMAND ----------
# DBTITLE 1,Fetch news articles via NewsAPI
try:
    newsapi_key = dbutils.secrets.get(
        scope=settings["news"]["secret_scope"],
        key=settings["news"]["secret_key"],
    )
except Exception:
    log.warning("NewsAPI key not found in Databricks Secrets — skipping news ingestion")
    log.warning(f"Setup: dbutils.secrets.put(scope='{settings['news']['secret_scope']}', key='{settings['news']['secret_key']}')")
    newsapi_key = None

if newsapi_key:
    keywords = get_news_keywords(catalog)
    log.info(f"Fetching news for {len(keywords)} keywords")

    articles = fetch_for_keywords(
        api_key=newsapi_key,
        keywords=keywords,
        from_date=start_dt,
        to_date=end_dt,
        language=settings["news"]["language"],
        max_articles_per_keyword=settings["news"]["max_articles_per_keyword"],
        sort_by=settings["news"]["sort_by"],
    )
    log.info(f"NewsAPI returned {len(articles):,} unique articles")

# COMMAND ----------
# DBTITLE 1,Write raw_news to Delta
    RAW_NEWS_SCHEMA = StructType([
        StructField("article_id",    StringType(),    nullable=False),
        StructField("title",         StringType(),    nullable=True),
        StructField("description",   StringType(),    nullable=True),
        StructField("source",        StringType(),    nullable=True),
        StructField("url",           StringType(),    nullable=True),
        StructField("published_at",  TimestampType(), nullable=True),
        StructField("query_keyword", StringType(),    nullable=True),
        StructField("ingestion_ts",  TimestampType(), nullable=False),
    ])

    if not articles:
        log.warning("No news articles fetched — skipping raw_news write")
    else:
        raw_news_df = spark.createDataFrame(articles)
        raw_news_df = raw_news_df.withColumn(
            "published_at", F.to_timestamp("published_at")
        )
        raw_news_df = add_ingestion_timestamp(raw_news_df)
        raw_news_df = spark.createDataFrame(raw_news_df.rdd, schema=RAW_NEWS_SCHEMA)

        news_count = merge_into_delta(
            spark=spark,
            source_df=raw_news_df,
            full_table_name=f"{DB}.raw_news",
            merge_keys=["article_id"],
        )
        log.rows(f"{DB}.raw_news", news_count)

log.stage_end()
