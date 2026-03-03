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
# MAGIC %pip install pyyaml --quiet

# COMMAND ----------
# DBTITLE 1,Imports
import yaml
from datetime import date
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, BooleanType, DateType, ArrayType
)

from src.utils.settings_loader import load_settings, get_database_name
from src.utils.delta_utils import ensure_database, merge_into_delta
from src.utils.logger import PipelineLogger

# COMMAND ----------
# DBTITLE 1,Load settings
settings = load_settings()
DB = get_database_name(settings)
log = PipelineLogger(stage="00_setup_catalog")
log.stage_start()

# COMMAND ----------
# DBTITLE 1,Load catalog.yaml
catalog_yaml_path = os.path.join(repo_root, "config", "catalog.yaml")

with open(catalog_yaml_path, "r") as f:
    raw_catalog = yaml.safe_load(f)

log.info(f"Loaded catalog from {catalog_yaml_path}")

# COMMAND ----------
# DBTITLE 1,Flatten catalog YAML to rows
TYPE_MAP = {
    "stocks": "stock",
    "crypto": "crypto",
    "fx": "fx",
    "news_keywords": "news_keyword",
}

rows = []
for section, asset_type in TYPE_MAP.items():
    for entry in raw_catalog.get("assets", {}).get(section, []):
        rows.append({
            "asset_id":      entry["id"],
            "asset_type":    asset_type,
            "display_name":  entry.get("display_name", entry["id"]),
            "news_keywords": entry.get("news_keywords", []),
            "active":        entry.get("active", True),
            "added_date":    date.today().isoformat(),
        })

log.info(f"Flattened {len(rows)} catalog entries")

if not rows:
    log.warning("Catalog is empty — nothing to process")
    dbutils.notebook.exit("EMPTY_CATALOG")

# COMMAND ----------
# DBTITLE 1,Create Spark DataFrame with schema enforcement
CATALOG_SCHEMA = StructType([
    StructField("asset_id",      StringType(),              nullable=False),
    StructField("asset_type",    StringType(),              nullable=False),
    StructField("display_name",  StringType(),              nullable=True),
    StructField("news_keywords", ArrayType(StringType()),   nullable=True),
    StructField("active",        BooleanType(),             nullable=False),
    StructField("added_date",    StringType(),              nullable=False),
])

catalog_df = spark.createDataFrame(rows, schema=CATALOG_SCHEMA)
catalog_df = catalog_df.withColumn("added_date", F.col("added_date").cast(DateType()))

log.info(f"Created catalog DataFrame with {catalog_df.count()} rows")
catalog_df.printSchema()

# COMMAND ----------
# DBTITLE 1,Write catalog to Delta table
ensure_database(spark, DB)

row_count = merge_into_delta(
    spark=spark,
    source_df=catalog_df,
    full_table_name=f"{DB}.catalog",
    merge_keys=["asset_id"],
)

log.rows(f"{DB}.catalog", row_count)
log.stage_end(rows_written=row_count)

# COMMAND ----------
# DBTITLE 1,Preview catalog
spark.table(f"{DB}.catalog").display()
