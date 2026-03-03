from __future__ import annotations

from typing import Optional

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def ensure_database(spark: SparkSession, db_name: str) -> None:
    """Create database if it does not exist and set it as the active database."""
    spark.sql(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    spark.sql(f"USE `{db_name}`")


def table_exists(spark: SparkSession, full_table_name: str) -> bool:
    """Return True if the Delta table is registered in the metastore."""
    try:
        spark.table(full_table_name)
        return True
    except Exception:
        return False


def create_or_replace_table(
    df: DataFrame,
    full_table_name: str,
    partition_by: Optional[list[str]] = None,
) -> None:
    """Create a managed Delta table from a DataFrame (first-run bootstrap)."""
    writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.saveAsTable(full_table_name)


def merge_into_delta(
    spark: SparkSession,
    source_df: DataFrame,
    full_table_name: str,
    merge_keys: list[str],
    partition_by: Optional[list[str]] = None,
) -> int:
    """
    Idempotent upsert into a Delta table.
    Creates the table on first call; performs MERGE on subsequent calls.
    Returns the total row count of the target table after the operation.
    """
    if not table_exists(spark, full_table_name):
        create_or_replace_table(source_df, full_table_name, partition_by)
        return source_df.count()

    target = DeltaTable.forName(spark, full_table_name)
    merge_condition = " AND ".join(
        [f"target.`{k}` = source.`{k}`" for k in merge_keys]
    )

    (
        target.alias("target")
        .merge(source_df.alias("source"), merge_condition)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )

    return spark.table(full_table_name).count()


def get_row_count(spark: SparkSession, full_table_name: str) -> int:
    """Return row count for a Delta table, or 0 if it does not exist."""
    if not table_exists(spark, full_table_name):
        return 0
    return spark.table(full_table_name).count()


def table_has_data(spark: SparkSession, full_table_name: str) -> bool:
    """Return True if the table exists and has at least one row."""
    return get_row_count(spark, full_table_name) > 0


def add_ingestion_timestamp(df: DataFrame, col_name: str = "ingestion_ts") -> DataFrame:
    """Add a current_timestamp column to a DataFrame."""
    return df.withColumn(col_name, F.current_timestamp())
