"""Bronze Layer — Raw CSV ingestion to Parquet.

Reads the 9 Olist CSV files from S3 (or local path in dev mode),
casts minimal types, and writes Parquet partitioned by ingestion date.

No business logic here — Bronze is an immutable record of what arrived.
Schema enforcement is lenient: bad rows land in a _rejected/ prefix.

AWS Glue:
    Job type    : Spark
    Glue version: 4.0 (Spark 3.3, Python 3.10)
    Worker type : G.1X
    Workers     : 2

Local dev:
    python -m etl.bronze_ingestion --local
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from loguru import logger

# ── Glue context — falls back gracefully when running locally ────────────────
try:
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext
    IS_GLUE = True
except ImportError:
    IS_GLUE = False
    logger.info("awsglue not available — running in local PySpark mode")

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, StringType, StructField, StructType,
)


# ── Schemas — explicit so Glue doesn't guess wrong on sparse columns ──────────

SCHEMAS: dict[str, StructType] = {
    "orders": StructType([
        StructField("order_id",                      StringType(),    False),
        StructField("customer_id",                   StringType(),    True),
        StructField("order_status",                  StringType(),    True),
        StructField("order_purchase_timestamp",      StringType(),    True),
        StructField("order_approved_at",             StringType(),    True),
        StructField("order_delivered_carrier_date",  StringType(),    True),
        StructField("order_delivered_customer_date", StringType(),    True),
        StructField("order_estimated_delivery_date", StringType(),    True),
    ]),
    "order_items": StructType([
        StructField("order_id",          StringType(),  False),
        StructField("order_item_id",     IntegerType(), True),
        StructField("product_id",        StringType(),  True),
        StructField("seller_id",         StringType(),  True),
        StructField("shipping_limit_date", StringType(), True),
        StructField("price",             DoubleType(),  True),
        StructField("freight_value",     DoubleType(),  True),
    ]),
    "order_payments": StructType([
        StructField("order_id",               StringType(),  False),
        StructField("payment_sequential",     IntegerType(), True),
        StructField("payment_type",           StringType(),  True),
        StructField("payment_installments",   IntegerType(), True),
        StructField("payment_value",          DoubleType(),  True),
    ]),
    "order_reviews": StructType([
        StructField("review_id",              StringType(), True),
        StructField("order_id",               StringType(), False),
        StructField("review_score",           IntegerType(), True),
        StructField("review_comment_title",   StringType(), True),
        StructField("review_comment_message", StringType(), True),
        StructField("review_creation_date",   StringType(), True),
        StructField("review_answer_timestamp",StringType(), True),
    ]),
    "customers": StructType([
        StructField("customer_id",              StringType(), False),
        StructField("customer_unique_id",       StringType(), True),
        StructField("customer_zip_code_prefix", StringType(), True),
        StructField("customer_city",            StringType(), True),
        StructField("customer_state",           StringType(), True),
    ]),
    "sellers": StructType([
        StructField("seller_id",              StringType(), False),
        StructField("seller_zip_code_prefix", StringType(), True),
        StructField("seller_city",            StringType(), True),
        StructField("seller_state",           StringType(), True),
    ]),
    "products": StructType([
        StructField("product_id",               StringType(),  False),
        StructField("product_category_name",    StringType(),  True),
        StructField("product_name_lenght",      IntegerType(), True),
        StructField("product_description_lenght",IntegerType(),True),
        StructField("product_photos_qty",       IntegerType(), True),
        StructField("product_weight_g",         DoubleType(),  True),
        StructField("product_length_cm",        DoubleType(),  True),
        StructField("product_height_cm",        DoubleType(),  True),
        StructField("product_width_cm",         DoubleType(),  True),
    ]),
    "product_category": StructType([
        StructField("product_category_name",         StringType(), False),
        StructField("product_category_name_english", StringType(), True),
    ]),
    "geolocation": StructType([
        StructField("geolocation_zip_code_prefix", StringType(), True),
        StructField("geolocation_lat",             DoubleType(), True),
        StructField("geolocation_lng",             DoubleType(), True),
        StructField("geolocation_city",            StringType(), True),
        StructField("geolocation_state",           StringType(), True),
    ]),
}


def get_spark(local: bool = False) -> SparkSession:
    if IS_GLUE and not local:
        sc = SparkContext()
        glue_ctx = GlueContext(sc)
        return glue_ctx.spark_session
    return (
        SparkSession.builder
        .appName("olist-bronze-ingestion")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def ingest_table(
    spark: SparkSession,
    table: str,
    src_path: str,
    dst_path: str,
    ingestion_date: str,
) -> dict[str, int]:
    """Read one CSV, validate, write partitioned Parquet.

    Returns dict with row counts: total, valid, rejected.
    """
    schema = SCHEMAS.get(table)
    logger.info(f"Ingesting {table} from {src_path}")

    df = (
        spark.read
        .option("header", "true")
        .option("mode", "PERMISSIVE")          # bad rows → _corrupt_record
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .schema(schema)
        .csv(src_path)
    )

    total = df.count()

    # Separate clean from rejected rows
    if "_corrupt_record" in df.columns:
        rejected = df.filter(F.col("_corrupt_record").isNotNull())
        clean    = df.filter(F.col("_corrupt_record").isNull()).drop("_corrupt_record")
    else:
        rejected = spark.createDataFrame([], schema)
        clean    = df

    rejected_count = rejected.count()
    valid_count    = total - rejected_count

    # Add metadata columns
    clean = clean.withColumns({
        "_ingestion_date":   F.lit(ingestion_date),
        "_source_file":      F.lit(f"{table}.csv"),
        "_row_count":        F.lit(total),
    })

    # Write clean rows partitioned by ingestion date
    (
        clean.write
        .mode("overwrite")
        .partitionBy("_ingestion_date")
        .parquet(f"{dst_path}/{table}")
    )

    # Write rejected rows separately for investigation
    if rejected_count > 0:
        logger.warning(f"{table}: {rejected_count} rejected rows")
        rejected.write.mode("overwrite").parquet(
            f"{dst_path}/_rejected/{table}/{ingestion_date}"
        )

    logger.info(f"{table}: {valid_count:,} valid / {rejected_count} rejected")
    return {"total": total, "valid": valid_count, "rejected": rejected_count}


def run(
    src_bucket: str,
    dst_bucket: str,
    ingestion_date: str,
    local: bool = False,
    local_data_dir: str = "data",
) -> None:
    spark = get_spark(local=local)

    stats = {}
    for table in SCHEMAS:
        if local:
            # Local: read from data/ folder
            csv_filename = {
                "order_items":      "olist_order_items_dataset.csv",
                "order_payments":   "olist_order_payments_dataset.csv",
                "order_reviews":    "olist_order_reviews_dataset.csv",
                "customers":        "olist_customers_dataset.csv",
                "sellers":          "olist_sellers_dataset.csv",
                "products":         "olist_products_dataset.csv",
                "product_category": "product_category_name_translation.csv",
                "geolocation":      "olist_geolocation_dataset.csv",
                "orders":           "olist_orders_dataset.csv",
            }[table]
            src = str(Path(local_data_dir) / csv_filename)
            dst = "output/bronze"
        else:
            src = f"s3://{src_bucket}/raw/{table}.csv"
            dst = f"s3://{dst_bucket}"

        stats[table] = ingest_table(spark, table, src, dst, ingestion_date)

    # Summary
    total_valid    = sum(s["valid"]    for s in stats.values())
    total_rejected = sum(s["rejected"] for s in stats.values())
    logger.info(
        f"Bronze ingestion complete — "
        f"{total_valid:,} valid rows, {total_rejected} rejected"
    )

    spark.stop()


if __name__ == "__main__":
    if IS_GLUE:
        args = getResolvedOptions(sys.argv, [
            "JOB_NAME", "src_bucket", "dst_bucket", "ingestion_date"
        ])
        job = Job(GlueContext(SparkContext()))
        run(
            src_bucket=args["src_bucket"],
            dst_bucket=args["dst_bucket"],
            ingestion_date=args["ingestion_date"],
        )
        job.commit()
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--local",            action="store_true")
        parser.add_argument("--local-data-dir",   default="data")
        parser.add_argument("--src-bucket",       default="olist-bronze")
        parser.add_argument("--dst-bucket",       default="olist-bronze")
        parser.add_argument("--ingestion-date",   default=str(date.today()))
        a = parser.parse_args()
        run(
            src_bucket=a.src_bucket,
            dst_bucket=a.dst_bucket,
            ingestion_date=a.ingestion_date,
            local=a.local,
            local_data_dir=a.local_data_dir,
        )
