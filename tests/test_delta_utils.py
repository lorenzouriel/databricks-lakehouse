"""Unit tests for src/utils/delta_utils.py"""
from __future__ import annotations

import pytest
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from src.utils.delta_utils import add_ingestion_timestamp, get_row_count, merge_into_delta


SCHEMA = StructType([
    StructField("id",    StringType(),  nullable=False),
    StructField("value", IntegerType(), nullable=True),
])


@pytest.fixture
def simple_df(spark):
    return spark.createDataFrame(
        [("a", 1), ("b", 2), ("c", 3)],
        schema=SCHEMA,
    )


@pytest.fixture
def updated_df(spark):
    return spark.createDataFrame(
        [("a", 99), ("d", 4)],
        schema=SCHEMA,
    )


class TestMergeIntoDelta:
    def test_creates_table_on_first_run(self, spark, tmp_path, simple_df):
        table = "test_merge_create"
        spark.sql(f"DROP TABLE IF EXISTS {table}")

        count = merge_into_delta(spark, simple_df, table, merge_keys=["id"])
        assert count == 3

    def test_upserts_existing_rows(self, spark, simple_df, updated_df):
        table = "test_merge_upsert"
        spark.sql(f"DROP TABLE IF EXISTS {table}")

        merge_into_delta(spark, simple_df, table, merge_keys=["id"])
        merge_into_delta(spark, updated_df, table, merge_keys=["id"])

        result = spark.table(table).filter("id = 'a'").collect()
        assert result[0]["value"] == 99

    def test_inserts_new_rows(self, spark, simple_df, updated_df):
        table = "test_merge_insert"
        spark.sql(f"DROP TABLE IF EXISTS {table}")

        merge_into_delta(spark, simple_df, table, merge_keys=["id"])
        count = merge_into_delta(spark, updated_df, table, merge_keys=["id"])

        assert count == 4  # 3 original + 1 new ("d")

    def test_idempotent_on_same_data(self, spark, simple_df):
        table = "test_merge_idempotent"
        spark.sql(f"DROP TABLE IF EXISTS {table}")

        merge_into_delta(spark, simple_df, table, merge_keys=["id"])
        count_after_second_run = merge_into_delta(spark, simple_df, table, merge_keys=["id"])

        assert count_after_second_run == 3


class TestGetRowCount:
    def test_returns_zero_for_nonexistent_table(self, spark):
        count = get_row_count(spark, "nonexistent_table_xyz")
        assert count == 0

    def test_returns_correct_count(self, spark, simple_df):
        table = "test_row_count"
        spark.sql(f"DROP TABLE IF EXISTS {table}")
        simple_df.write.format("delta").mode("overwrite").saveAsTable(table)
        assert get_row_count(spark, table) == 3


class TestAddIngestionTimestamp:
    def test_adds_column(self, spark, simple_df):
        result = add_ingestion_timestamp(simple_df)
        assert "ingestion_ts" in result.columns

    def test_custom_column_name(self, spark, simple_df):
        result = add_ingestion_timestamp(simple_df, col_name="bronze_ts")
        assert "bronze_ts" in result.columns

    def test_column_is_not_null(self, spark, simple_df):
        result = add_ingestion_timestamp(simple_df)
        null_count = result.filter(F.col("ingestion_ts").isNull()).count()
        assert null_count == 0
