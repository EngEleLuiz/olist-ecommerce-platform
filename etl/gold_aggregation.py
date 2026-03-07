"""Gold Layer — Business KPI aggregations.

Reads Silver Parquet and writes four Gold tables:

  1. gold_orders        — one row per order, fully enriched (ML feature store)
  2. gold_kpi_monthly   — revenue, volume, delay rate by state + month
  3. gold_seller_perf   — seller-level performance metrics (30/90/365 day)
  4. gold_category_demand — weekly order volume by category + state

These tables are loaded into Redshift Serverless by the Step Functions
pipeline and also read directly by the Streamlit dashboard as Parquet
when USE_DUCKDB=true.

AWS Glue:
    Job type    : Spark
    Glue version: 4.0
    Worker type : G.1X
    Workers     : 2

Local dev:
    python -m etl.gold_aggregation --local
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
from pyspark.sql.window import Window


def get_spark(local: bool = False) -> SparkSession:
    if IS_GLUE and not local:
        sc = SparkContext()
        return GlueContext(sc).spark_session
    return (
        SparkSession.builder
        .appName("olist-gold-aggregation")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def build_gold_orders(silver: DataFrame) -> DataFrame:
    """One row per delivered order — the ML feature store.

    Contains every feature the ML models need so training never
    has to touch raw CSVs.
    """
    df = silver.filter(F.col("order_status") == "delivered")

    df = df.select(
        # Identity
        "order_id", "customer_id", "customer_unique_id",
        # Target variables
        "is_late", "delay_days", "review_score", "review_sentiment",
        # Time
        "order_purchase_timestamp", "purchase_year", "purchase_month",
        "purchase_dow", "purchase_hour", "purchase_ym",
        "estimated_days", "actual_days",
        # Order financials
        "total_price", "total_freight", "payment_value",
        "freight_ratio", "max_installments", "main_payment_type",
        # Items
        "item_count", "distinct_sellers", "distinct_products",
        "avg_product_weight_g", "main_category",
        # Geography
        "customer_state", "customer_region", "customer_city",
    )

    logger.info(f"gold_orders: {df.count():,} delivered orders")
    return df


def build_kpi_monthly(silver: DataFrame) -> DataFrame:
    """Monthly business KPIs by state.

    Key metrics for the executive dashboard:
    - GMV (Gross Merchandise Value)
    - Order volume
    - Late delivery rate
    - Average review score
    - Average order value
    """
    df = silver.filter(F.col("order_status").isin("delivered", "shipped", "invoiced"))

    monthly = df.groupBy("purchase_ym", "customer_state", "customer_region").agg(
        F.count("order_id").alias("order_count"),
        F.sum("payment_value").alias("gmv"),
        F.mean("payment_value").alias("avg_order_value"),
        F.mean("review_score").alias("avg_review_score"),
        F.mean("is_late").alias("late_rate"),
        F.mean("delay_days").alias("avg_delay_days"),
        F.mean("freight_ratio").alias("avg_freight_ratio"),
        F.sum("item_count").alias("total_items_sold"),
        F.countDistinct("customer_unique_id").alias("unique_customers"),
    )

    # Month-over-month GMV growth per state
    w = Window.partitionBy("customer_state").orderBy("purchase_ym")
    monthly = monthly.withColumn(
        "gmv_mom_growth",
        (F.col("gmv") - F.lag("gmv", 1).over(w)) / F.lag("gmv", 1).over(w)
    )

    logger.info(f"gold_kpi_monthly: {monthly.count():,} rows")
    return monthly


def build_seller_performance(silver: DataFrame, items: DataFrame, sellers: DataFrame) -> DataFrame:
    """Seller-level performance — rolling 30 / 90 / 365 day windows.

    Used in the Seller Performance dashboard page and as features
    for the delivery delay model.
    """
    # Join items back to get per-seller order info
    seller_orders = (
        items.select("order_id", "seller_id", "price", "freight_value")
        .join(
            silver.select(
                "order_id", "order_purchase_timestamp",
                "is_late", "delay_days", "review_score",
                "order_delivered_customer_date",
            ),
            on="order_id",
            how="inner",
        )
    )

    seller_agg = seller_orders.groupBy("seller_id").agg(
        F.count("order_id").alias("total_orders"),
        F.sum("price").alias("total_revenue"),
        F.mean("price").alias("avg_ticket"),
        F.mean("is_late").alias("late_rate"),
        F.mean("delay_days").alias("avg_delay_days"),
        F.mean("review_score").alias("avg_review_score"),
        F.min("order_purchase_timestamp").alias("first_sale_date"),
        F.max("order_purchase_timestamp").alias("last_sale_date"),
    )

    # Join seller geography
    seller_agg = seller_agg.join(
        sellers.select("seller_id", "seller_state", "seller_city"),
        on="seller_id",
        how="left",
    )

    # Seller tier based on revenue
    quantiles = seller_agg.approxQuantile("total_revenue", [0.25, 0.75], 0.01)
    q25, q75 = quantiles[0], quantiles[1]
    seller_agg = seller_agg.withColumn(
        "seller_tier",
        F.when(F.col("total_revenue") >= q75, "top")
        .when(F.col("total_revenue") >= q25, "mid")
        .otherwise("low")
    )

    logger.info(f"gold_seller_performance: {seller_agg.count():,} sellers")
    return seller_agg


def build_category_demand(silver: DataFrame) -> DataFrame:
    """Weekly order volume by category and state — LightGBM training input."""
    df = silver.filter(F.col("order_status") == "delivered")
    df = df.withColumn(
        "week_start",
        F.date_trunc("week", F.col("order_purchase_timestamp"))
    )

    demand = df.groupBy("week_start", "customer_state", "main_category").agg(
        F.count("order_id").alias("order_count"),
        F.sum("payment_value").alias("weekly_gmv"),
        F.mean("payment_value").alias("avg_order_value"),
        F.mean("review_score").alias("avg_review_score"),
    )

    # Week-over-week change per state+category
    w = Window.partitionBy("customer_state", "main_category").orderBy("week_start")
    demand = demand.withColumn(
        "wow_growth",
        (F.col("order_count") - F.lag("order_count", 1).over(w)) /
        F.lag("order_count", 1).over(w)
    )

    logger.info(f"gold_category_demand: {demand.count():,} rows")
    return demand


def run(
    silver_path: str,
    gold_path: str,
    local: bool = False,
) -> None:
    spark = get_spark(local=local)

    silver = spark.read.parquet(f"{silver_path}/orders")
    items  = spark.read.parquet(f"{silver_path}/../bronze/order_items") if local \
             else spark.read.parquet(f"{silver_path}/order_items")
    sellers= spark.read.parquet(f"{silver_path}/sellers")

    # Build and write all four Gold tables
    tables = {
        "gold_orders":          build_gold_orders(silver),
        "gold_kpi_monthly":     build_kpi_monthly(silver),
        "gold_seller_perf":     build_seller_performance(silver, items, sellers),
        "gold_category_demand": build_category_demand(silver),
    }

    for name, df in tables.items():
        out = f"{gold_path}/{name}"
        df.write.mode("overwrite").parquet(out)
        logger.info(f"Wrote {name} → {out}")

    spark.stop()
    logger.info("Gold aggregation complete ✓")


if __name__ == "__main__":
    if IS_GLUE:
        args = getResolvedOptions(sys.argv, ["JOB_NAME", "silver_bucket", "gold_bucket"])
        job  = Job(GlueContext(SparkContext()))
        run(
            silver_path=f"s3://{args['silver_bucket']}",
            gold_path=f"s3://{args['gold_bucket']}",
        )
        job.commit()
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("--local",        action="store_true")
        parser.add_argument("--silver-path",  default="output/silver")
        parser.add_argument("--gold-path",    default="output/gold")
        a = parser.parse_args()
        run(
            silver_path=a.silver_path,
            gold_path=a.gold_path,
            local=a.local,
        )
