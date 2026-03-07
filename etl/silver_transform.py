"""Silver Layer — Clean, validate and enrich Bronze.

Reads Bronze Parquet, applies:
  - Null handling and type casting
  - Timestamp parsing
  - Derived columns (delay_days, is_late, freight_ratio, etc.)
  - Data quality assertions (logged, not dropped)
  - State/region mapping for Brazilian geography
  - Product category translation

Writes partitioned by customer_state + purchase_year_month so downstream
Redshift queries can skip irrelevant partitions.

AWS Glue:
    Job type    : Spark
    Glue version: 4.0
    Worker type : G.1X
    Workers     : 3

Local dev:
    python -m etl.silver_transform --local
"""

from __future__ import annotations

import argparse
import sys

from loguru import logger

try:
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext
    IS_GLUE = True
except ImportError:
    IS_GLUE = False

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType


# ── Brazilian state → region mapping ─────────────────────────────────────────
BR_REGIONS = {
    "SP": "Sudeste", "RJ": "Sudeste", "MG": "Sudeste", "ES": "Sudeste",
    "RS": "Sul",     "PR": "Sul",     "SC": "Sul",
    "BA": "Nordeste","PE": "Nordeste","CE": "Nordeste","MA": "Nordeste",
    "PB": "Nordeste","RN": "Nordeste","AL": "Nordeste","SE": "Nordeste","PI": "Nordeste",
    "PA": "Norte",   "AM": "Norte",   "RO": "Norte",   "AC": "Norte",
    "AP": "Norte",   "RR": "Norte",   "TO": "Norte",
    "DF": "Centro-Oeste","GO": "Centro-Oeste","MT": "Centro-Oeste","MS": "Centro-Oeste",
}


def get_spark(local: bool = False) -> SparkSession:
    if IS_GLUE and not local:
        sc = SparkContext()
        return GlueContext(sc).spark_session
    return (
        SparkSession.builder
        .appName("olist-silver-transform")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def transform_orders(spark: SparkSession, bronze_path: str) -> DataFrame:
    """Clean and enrich the orders table."""
    df = spark.read.parquet(f"{bronze_path}/orders")

    ts_fmt = "yyyy-MM-dd HH:mm:ss"
    df = df.withColumns({
        "order_purchase_timestamp":       F.to_timestamp("order_purchase_timestamp",       ts_fmt),
        "order_approved_at":              F.to_timestamp("order_approved_at",              ts_fmt),
        "order_delivered_carrier_date":   F.to_timestamp("order_delivered_carrier_date",   ts_fmt),
        "order_delivered_customer_date":  F.to_timestamp("order_delivered_customer_date",  ts_fmt),
        "order_estimated_delivery_date":  F.to_timestamp("order_estimated_delivery_date",  ts_fmt),
    })

    # Derived time features
    df = df.withColumns({
        "purchase_year":   F.year("order_purchase_timestamp"),
        "purchase_month":  F.month("order_purchase_timestamp"),
        "purchase_dow":    F.dayofweek("order_purchase_timestamp"),
        "purchase_hour":   F.hour("order_purchase_timestamp"),
        "purchase_ym":     F.date_format("order_purchase_timestamp", "yyyy-MM"),
    })

    # Delivery metrics
    df = df.withColumns({
        "estimated_days": (
            F.datediff("order_estimated_delivery_date", "order_purchase_timestamp")
        ),
        "actual_days": (
            F.datediff("order_delivered_customer_date", "order_purchase_timestamp")
        ),
    })
    df = df.withColumn(
        "delay_days",
        F.greatest(
            F.col("actual_days") - F.col("estimated_days"),
            F.lit(0)
        )
    )
    df = df.withColumn("is_late", (F.col("delay_days") > 0).cast("int"))

    # Approval speed
    df = df.withColumn(
        "approval_hours",
        (F.unix_timestamp("order_approved_at") - F.unix_timestamp("order_purchase_timestamp")) / 3600
    )

    # Data quality flags
    df = df.withColumns({
        "dq_missing_approval":   F.col("order_approved_at").isNull().cast("int"),
        "dq_missing_delivery":   F.col("order_delivered_customer_date").isNull().cast("int"),
        "dq_negative_delay":     (F.col("delay_days") < 0).cast("int"),
        "dq_extreme_delivery":   (F.col("actual_days") > 120).cast("int"),
    })

    dq_issues = df.filter(
        (F.col("dq_missing_approval") == 1) |
        (F.col("dq_negative_delay")   == 1) |
        (F.col("dq_extreme_delivery") == 1)
    ).count()
    logger.info(f"orders: {dq_issues:,} rows with DQ flags (kept, not dropped)")

    return df.drop("_ingestion_date", "_source_file", "_row_count")


def transform_order_items(spark: SparkSession, bronze_path: str) -> DataFrame:
    """Aggregate items to order level and add product category."""
    items    = spark.read.parquet(f"{bronze_path}/order_items")
    products = spark.read.parquet(f"{bronze_path}/products")
    cat_map  = spark.read.parquet(f"{bronze_path}/product_category")

    products = products.join(cat_map, on="product_category_name", how="left")

    items = items.join(
        products.select(
            "product_id",
            "product_category_name",
            "product_category_name_english",
            "product_weight_g",
        ),
        on="product_id",
        how="left",
    )

    # Aggregate to order level
    agg = items.groupBy("order_id").agg(
        F.count("order_item_id").alias("item_count"),
        F.sum("price").alias("total_price"),
        F.sum("freight_value").alias("total_freight"),
        F.countDistinct("seller_id").alias("distinct_sellers"),
        F.countDistinct("product_id").alias("distinct_products"),
        F.mean("product_weight_g").alias("avg_product_weight_g"),
    )

    # Main category = most frequent per order
    item_cat = (
        items.groupBy("order_id", "product_category_name_english")
        .count()
        .withColumnRenamed("count", "_cat_count")
    )
    window = (
        __import__("pyspark.sql.window", fromlist=["Window"])
        .Window.partitionBy("order_id")
        .orderBy(F.desc("_cat_count"))
    )
    main_cat = (
        item_cat
        .withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .select("order_id", F.col("product_category_name_english").alias("main_category"))
    )

    return agg.join(main_cat, on="order_id", how="left")


def transform_customers(spark: SparkSession, bronze_path: str) -> DataFrame:
    """Add region mapping to customers."""
    df = spark.read.parquet(f"{bronze_path}/customers")

    region_map = spark.createDataFrame(
        [(k, v) for k, v in BR_REGIONS.items()],
        ["customer_state", "customer_region"],
    )
    return df.join(region_map, on="customer_state", how="left")


def transform_payments(spark: SparkSession, bronze_path: str) -> DataFrame:
    """Aggregate payments per order."""
    df = spark.read.parquet(f"{bronze_path}/order_payments")

    agg = df.groupBy("order_id").agg(
        F.sum("payment_value").alias("payment_value"),
        F.max("payment_installments").alias("max_installments"),
        F.countDistinct("payment_type").alias("payment_type_count"),
    )

    # Dominant payment type
    dom = (
        df.groupBy("order_id", "payment_type")
        .agg(F.sum("payment_value").alias("_v"))
    )
    w = (
        __import__("pyspark.sql.window", fromlist=["Window"])
        .Window.partitionBy("order_id")
        .orderBy(F.desc("_v"))
    )
    dom = (
        dom.withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .select("order_id", F.col("payment_type").alias("main_payment_type"))
    )

    return agg.join(dom, on="order_id", how="left")


def transform_reviews(spark: SparkSession, bronze_path: str) -> DataFrame:
    """Keep latest review per order, add sentiment bucket."""
    df = spark.read.parquet(f"{bronze_path}/order_reviews")
    df = df.withColumn(
        "review_creation_date",
        F.to_timestamp("review_creation_date", "yyyy-MM-dd HH:mm:ss")
    )

    w = (
        __import__("pyspark.sql.window", fromlist=["Window"])
        .Window.partitionBy("order_id")
        .orderBy(F.desc("review_creation_date"))
    )
    df = (
        df.withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .select("order_id", "review_score")
    )

    df = df.withColumn(
        "review_sentiment",
        F.when(F.col("review_score") >= 4, "positive")
        .when(F.col("review_score") == 3, "neutral")
        .otherwise("negative")
    )
    return df


def build_silver_orders(spark: SparkSession, bronze_path: str, silver_path: str) -> None:
    """Join all silver tables into the main order-level silver table."""
    orders   = transform_orders(spark, bronze_path)
    items    = transform_order_items(spark, bronze_path)
    payments = transform_payments(spark, bronze_path)
    reviews  = transform_reviews(spark, bronze_path)
    customers= transform_customers(spark, bronze_path)

    silver = (
        orders
        .join(items,     on="order_id",    how="left")
        .join(payments,  on="order_id",    how="left")
        .join(reviews,   on="order_id",    how="left")
        .join(customers, on="customer_id", how="left")
    )

    # Freight ratio
    silver = silver.withColumn(
        "freight_ratio",
        F.when(
            F.col("total_price") > 0,
            (F.col("total_freight") / F.col("total_price")).cast(DoubleType())
        ).otherwise(0.0)
    )

    row_count = silver.count()
    logger.info(f"Silver orders: {row_count:,} rows, {len(silver.columns)} columns")

    (
        silver.write
        .mode("overwrite")
        .partitionBy("customer_state", "purchase_ym")
        .parquet(f"{silver_path}/orders")
    )


def run(
    bronze_path: str,
    silver_path: str,
    local: bool = False,
) -> None:
    spark = get_spark(local=local)
    build_silver_orders(spark, bronze_path, silver_path)

    # Also write sellers and geolocation to silver as-is (no enrichment needed)
    for table in ["sellers", "geolocation"]:
        df = spark.read.parquet(f"{bronze_path}/{table}")
        df.write.mode("overwrite").parquet(f"{silver_path}/{table}")
        logger.info(f"Passed {table} to silver: {df.count():,} rows")

    spark.stop()
    logger.info("Silver transform complete")


if __name__ == "__main__":
    if IS_GLUE:
        args = getResolvedOptions(sys.argv, ["JOB_NAME", "bronze_bucket", "silver_bucket"])
        job  = Job(GlueContext(SparkContext()))
        run(
            bronze_path=f"s3://{args['bronze_bucket']}",
            silver_path=f"s3://{args['silver_bucket']}",
        )
        job.commit()
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--local",         action="store_true")
        parser.add_argument("--bronze-path",   default="output/bronze")
        parser.add_argument("--silver-path",   default="output/silver")
        a = parser.parse_args()
        run(
            bronze_path=a.bronze_path,
            silver_path=a.silver_path,
            local=a.local,
        )
