"""Olist Data Loader.

Single entry point for all data access across notebooks, ML models,
and the dashboard. Reads from the local CSV files via DuckDB in dev,
and from Redshift in production (USE_DUCKDB=false).

Usage:
    from data_loader import OlistLoader
    loader = OlistLoader()
    orders = loader.orders()
    features = loader.order_features()
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

USE_DUCKDB = os.getenv("USE_DUCKDB", "true").lower() == "true"

# Resolve DATA_DIR relative to this file's location (project root/data/)
# so it works regardless of where Python / Jupyter is launched from.
_HERE = Path(__file__).resolve().parent
_ENV_DATA_DIR = os.getenv("DATA_DIR")
if _ENV_DATA_DIR:
    DATA_DIR = Path(_ENV_DATA_DIR)
    if not DATA_DIR.is_absolute():
        DATA_DIR = (_HERE / DATA_DIR).resolve()
else:
    DATA_DIR = (_HERE / "data").resolve()

# Canonical Olist CSV filenames
OLIST_FILES = {
    "orders":            "olist_orders_dataset.csv",
    "order_items":       "olist_order_items_dataset.csv",
    "order_payments":    "olist_order_payments_dataset.csv",
    "order_reviews":     "olist_order_reviews_dataset.csv",
    "customers":         "olist_customers_dataset.csv",
    "sellers":           "olist_sellers_dataset.csv",
    "products":          "olist_products_dataset.csv",
    "product_category":  "product_category_name_translation.csv",
    "geolocation":       "olist_geolocation_dataset.csv",
}


class OlistLoader:
    """Unified data access layer for the Olist e-commerce dataset.

    All heavy joins are done once and cached in-process. Call
    `loader.order_features()` to get the fully-joined analysis table.
    """

    def __init__(self) -> None:
        self._con = duckdb.connect(":memory:") if USE_DUCKDB else None
        self._available = self._scan_available_files()
        logger.info(
            f"OlistLoader ready — {len(self._available)}/{len(OLIST_FILES)} "
            f"CSV files found in {DATA_DIR}"
        )

    # ── Raw table accessors ───────────────────────────────────────────────────

    @cache
    def orders(self) -> pd.DataFrame:
        df = self._read("orders")
        ts_cols = [
            "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
        for col in ts_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    @cache
    def order_items(self) -> pd.DataFrame:
        return self._read("order_items")

    @cache
    def order_payments(self) -> pd.DataFrame:
        return self._read("order_payments")

    @cache
    def order_reviews(self) -> pd.DataFrame:
        return self._read("order_reviews")

    @cache
    def customers(self) -> pd.DataFrame:
        return self._read("customers")

    @cache
    def sellers(self) -> pd.DataFrame:
        return self._read("sellers")

    @cache
    def products(self) -> pd.DataFrame:
        df = self._read("products")
        cat = self._read("product_category")
        return df.merge(cat, on="product_category_name", how="left")

    @cache
    def geolocation(self) -> pd.DataFrame:
        df = self._read("geolocation")
        # Keep one row per zip prefix to avoid fan-out in joins
        return df.groupby("geolocation_zip_code_prefix").first().reset_index()

    # ── Joined / enriched tables ──────────────────────────────────────────────

    @cache
    def order_features(self) -> pd.DataFrame:
        """Fully joined order-level analysis table.

        Joins: orders + items + payments + reviews + customers + sellers
        + products + geolocation.

        Returns one row per order with all features needed for ML models
        and dashboard KPIs.
        """
        logger.info("Building order_features table...")

        orders   = self.orders()
        items    = self.order_items()
        payments = self.order_payments()
        reviews  = self.order_reviews()
        customers= self.customers()
        sellers  = self.sellers()
        products = self.products()

        # ── Aggregate items per order ─────────────────────────────────────────
        items_agg = items.groupby("order_id").agg(
            item_count       =("order_item_id",  "count"),
            total_price      =("price",           "sum"),
            total_freight    =("freight_value",   "sum"),
            distinct_sellers =("seller_id",       "nunique"),
            distinct_products=("product_id",      "nunique"),
        ).reset_index()

        # Most frequent category per order
        item_cat = (
            items.merge(products[["product_id", "product_category_name_english"]], on="product_id", how="left")
            .groupby("order_id")["product_category_name_english"]
            .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "unknown")
            .reset_index()
            .rename(columns={"product_category_name_english": "main_category"})
        )
        items_agg = items_agg.merge(item_cat, on="order_id", how="left")

        # ── Aggregate payments per order ──────────────────────────────────────
        pay_agg = payments.groupby("order_id").agg(
            payment_value    =("payment_value",        "sum"),
            max_installments =("payment_installments", "max"),
            payment_types    =("payment_type",         "nunique"),
        ).reset_index()

        # Most used payment type
        pay_type = (
            payments.sort_values("payment_value", ascending=False)
            .groupby("order_id")["payment_type"].first().reset_index()
            .rename(columns={"payment_type": "main_payment_type"})
        )
        pay_agg = pay_agg.merge(pay_type, on="order_id", how="left")

        # ── Latest review per order ───────────────────────────────────────────
        rev_agg = (
            reviews.sort_values("review_creation_date", ascending=False)
            .groupby("order_id")
            .agg(review_score=("review_score", "first"))
            .reset_index()
        )

        # ── Seller state per order (via items → sellers) ──────────────────────
        seller_per_order = (
            items[["order_id", "seller_id"]]
            .drop_duplicates("order_id")          # one seller per order (first)
            .merge(sellers[["seller_id", "seller_state"]], on="seller_id", how="left")
            [["order_id", "seller_state"]]
        )

        # ── Join everything onto orders ───────────────────────────────────────
        df = (
            orders
            .merge(items_agg,        on="order_id",   how="left")
            .merge(pay_agg,          on="order_id",   how="left")
            .merge(rev_agg,          on="order_id",   how="left")
            .merge(customers,        on="customer_id", how="left")
            .merge(seller_per_order, on="order_id",   how="left")
        )

        # ── Derived columns ───────────────────────────────────────────────────
        df["purchase_year"]  = df["order_purchase_timestamp"].dt.year
        df["purchase_month"] = df["order_purchase_timestamp"].dt.month
        df["purchase_dow"]   = df["order_purchase_timestamp"].dt.dayofweek
        df["purchase_hour"]  = df["order_purchase_timestamp"].dt.hour
        df["purchase_ym"]    = df["order_purchase_timestamp"].dt.to_period("M").astype(str)

        df["estimated_days"] = (
            df["order_estimated_delivery_date"] - df["order_purchase_timestamp"]
        ).dt.days

        df["actual_days"] = (
            df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
        ).dt.days

        df["delay_days"] = (df["actual_days"] - df["estimated_days"]).clip(lower=0)
        df["is_late"]    = (df["delay_days"] > 0).astype(int)

        df["freight_ratio"] = (
            df["total_freight"] / df["total_price"].replace(0, float("nan"))
        ).fillna(0).clip(0, 1)

        logger.info(f"order_features: {len(df):,} rows, {len(df.columns)} columns")
        return df

    @cache
    def customer_rfm(self) -> pd.DataFrame:
        """RFM table per customer — input to the BG/NBD LTV model."""
        df = self.order_features()
        df = df[df["order_status"] == "delivered"].copy()

        snapshot_date = df["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

        rfm = df.groupby("customer_unique_id").agg(
            frequency     =("order_id",                "count"),
            recency_days  =("order_purchase_timestamp", lambda x: (snapshot_date - x.max()).days),
            T_days        =("order_purchase_timestamp", lambda x: (snapshot_date - x.min()).days),
            monetary_mean =("payment_value",            "mean"),
            total_spend   =("payment_value",            "sum"),
        ).reset_index()

        rfm["frequency_repeat"] = (rfm["frequency"] - 1).clip(lower=0)
        return rfm

    @cache
    def demand_series(self) -> pd.DataFrame:
        """Weekly order counts by state and category — input to LightGBM."""
        df = self.order_features()
        df = df[df["order_status"] == "delivered"].copy()
        df["week_start"] = df["order_purchase_timestamp"].dt.to_period("W").dt.start_time

        demand = (
            df.groupby(["week_start", "customer_state", "main_category"])
            .agg(order_count=("order_id", "count"))
            .reset_index()
            .rename(columns={"main_category": "category"})
        )
        return demand

    # ── Source stats ──────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Quick stats for dashboard sidebar."""
        orders = self.orders()
        if orders.empty or "order_status" not in orders.columns:
            return {
                "total_orders": 0, "delivered": 0,
                "date_range": ("N/A", "N/A"), "files_loaded": len(self._available),
            }
        return {
            "total_orders":    len(orders),
            "delivered":       int((orders["order_status"] == "delivered").sum()),
            "date_range":      (
                str(orders["order_purchase_timestamp"].min().date()),
                str(orders["order_purchase_timestamp"].max().date()),
            ),
            "files_loaded":    len(self._available),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _scan_available_files(self) -> dict[str, Path]:
        available = {}
        for key, fname in OLIST_FILES.items():
            path = DATA_DIR / fname
            if path.exists():
                available[key] = path
            else:
                logger.warning(f"Missing: {path}")
        return available

    def _read(self, key: str) -> pd.DataFrame:
        if key not in self._available:
            logger.warning(f"File for '{key}' not found — returning empty DataFrame")
            return pd.DataFrame()
        path = self._available[key]
        df = pd.read_csv(path, low_memory=False)
        logger.debug(f"Loaded {key}: {len(df):,} rows from {path.name}")
        return df
