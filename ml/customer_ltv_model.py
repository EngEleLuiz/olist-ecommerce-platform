"""Customer LTV Model — BG/NBD + Gamma-Gamma.

Predicts future purchase probability and expected revenue per customer
using the industry-standard probabilistic CLV framework.

Why BG/NBD instead of a neural net?
  - Requires only RFM data (recency, frequency, T) — no clickstream needed
  - Probabilistically sound: models dropout AND purchase rate separately
  - Interpretable: "this customer has a 73% chance of being still active"
  - Used in production at Shopify, iFood, and most serious e-commerce teams
  - Outperforms ML approaches when transaction data is sparse (< 5 orders)

Pipeline:
  1. BG/NBD model   → P(alive) + predicted repeat purchases (90d / 365d)
  2. Gamma-Gamma    → expected monetary value per future transaction
  3. LTV = predicted_purchases × predicted_monetary_value
  4. Outputs written to dbt_project/seeds/ltv_predictions.csv

Usage:
    from ml.customer_ltv_model import CustomerLTVModel
    model = CustomerLTVModel()
    predictions = model.train_and_predict(rfm_df)  # loader.customer_rfm()
"""

from __future__ import annotations

import os
from pathlib import Path

import mlflow
import pandas as pd
from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import calibration_and_holdout_data
from loguru import logger
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

MODEL_DIR = Path(os.getenv("MODEL_DIR", "ml/artifacts"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

_HERE = Path(__file__).resolve().parent.parent
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "mlruns")

SEED_PATH = Path("dbt_project/seeds/ltv_predictions.csv")

# Penalizer keeps BG/NBD from overfitting on customers with very few purchases
BGNBD_PENALIZER = 0.001
GAMMA_PENALIZER = 0.001


class CustomerLTVModel:
    """BG/NBD + Gamma-Gamma customer lifetime value model.

    Args:
        penalizer_coef: L2 regularisation for both sub-models.
    """

    def __init__(self, penalizer_coef: float = BGNBD_PENALIZER) -> None:
        self.penalizer = penalizer_coef
        self.bgf: BetaGeoFitter | None = None
        self.ggf: GammaGammaFitter | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def train_and_predict(
        self,
        rfm: pd.DataFrame,
        predict_days: list[int] | None = None,
        discount_rate: float = 0.01,  # monthly discount rate for CLV
    ) -> pd.DataFrame:
        """Fit BG/NBD + Gamma-Gamma and return per-customer LTV predictions.

        Args:
            rfm: Output of OlistLoader.customer_rfm() with columns:
                 frequency_repeat, recency_days, T_days, monetary_mean
            predict_days: Horizons to predict [90, 365] by default
            discount_rate: Monthly discount rate for present-value CLV

        Returns:
            DataFrame with customer_unique_id + LTV predictions,
            also written to dbt_project/seeds/ltv_predictions.csv
        """
        predict_days = predict_days or [90, 365]
        rfm = self._validate(rfm)

        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_LTV", "olist-customer-ltv"))
        with mlflow.start_run(run_name="customer_ltv_bgnbd"):
            mlflow.log_param("penalizer_coef", self.penalizer)
            mlflow.log_param("discount_rate", discount_rate)
            mlflow.log_param("n_customers", len(rfm))
            mlflow.log_param("repeat_buyer_pct", f"{(rfm['frequency_repeat'] > 0).mean():.2%}")

            # ── Step 1: BG/NBD — purchase frequency + churn ──────────────────
            self.bgf = BetaGeoFitter(penalizer_coef=self.penalizer)
            self.bgf.fit(
                frequency=rfm["frequency_repeat"],
                recency=rfm["recency_days"],
                T=rfm["T_days"],
            )
            logger.info("BG/NBD fitted ✓")
            logger.info(
                f"  r={self.bgf.params_['r']:.4f}  "
                f"α={self.bgf.params_['alpha']:.4f}  "
                f"a={self.bgf.params_['a']:.4f}  "
                f"b={self.bgf.params_['b']:.4f}"
            )

            # ── Step 2: Gamma-Gamma — monetary value ─────────────────────────
            # GGF requires only repeat buyers (frequency_repeat > 0)
            repeat_buyers = rfm[rfm["frequency_repeat"] > 0].copy()
            self.ggf = GammaGammaFitter(penalizer_coef=self.penalizer)
            self.ggf.fit(
                frequency=repeat_buyers["frequency_repeat"],
                monetary_value=repeat_buyers["monetary_mean"],
            )
            logger.info("Gamma-Gamma fitted ✓")
            logger.info(
                f"  p={self.ggf.params_['p']:.4f}  "
                f"q={self.ggf.params_['q']:.4f}  "
                f"v={self.ggf.params_['v']:.4f}"
            )

            # ── Step 3: Predictions ───────────────────────────────────────────
            predictions = rfm[["customer_unique_id"]].copy()

            for days in predict_days:
                col = f"predicted_purchases_{days}d"
                predictions[col] = self.bgf.conditional_expected_number_of_purchases_up_to_time(
                    t=days,
                    frequency=rfm["frequency_repeat"].values,
                    recency=rfm["recency_days"].values,
                    T=rfm["T_days"].values,
                ).values

            # P(alive) — probability customer hasn't churned
            predictions["p_alive"] = self.bgf.conditional_probability_alive(
                frequency=rfm["frequency_repeat"].values,
                recency=rfm["recency_days"].values,
                T=rfm["T_days"].values,
            ).values

            # Expected monetary value per transaction
            predictions["expected_avg_order_value"] = self.ggf.conditional_expected_average_profit(
                frequency=rfm["frequency_repeat"].values,
                monetary_value=rfm["monetary_mean"].values,
            ).values

            # LTV = predicted purchases × expected monetary value
            for days in predict_days:
                predictions[f"predicted_ltv_{days}d"] = (
                    predictions[f"predicted_purchases_{days}d"]
                    * predictions["expected_avg_order_value"]
                )

            # CLV with time-value-of-money (present value, monthly discounting)
            # lifetimes requires pandas Series with a clean integer index
            rfm_reset = rfm.reset_index(drop=True)
            clv_series = self.ggf.customer_lifetime_value(
                transaction_prediction_model=self.bgf,
                frequency=rfm_reset["frequency_repeat"],
                recency=rfm_reset["recency_days"],
                T=rfm_reset["T_days"],
                monetary_value=rfm_reset["monetary_mean"],
                time=12,
                discount_rate=discount_rate,
                freq="D",
            )
            predictions["clv_12m"] = clv_series.values

            # LTV segment
            predictions["ltv_segment"] = pd.qcut(
                predictions["clv_12m"],
                q=4,
                labels=["Bronze", "Silver", "Gold", "Platinum"],
                duplicates="drop",
            ).astype(str)

            # ── Step 4: Holdout evaluation ────────────────────────────────────
            metrics = self._evaluate(rfm)
            mlflow.log_metrics(metrics)

            # ── Step 5: Write to dbt seed ─────────────────────────────────────
            predictions["predicted_at"] = pd.Timestamp.now().date()
            self._write_seed(predictions)

            # Summary
            logger.info(
                f"LTV predictions complete — {len(predictions):,} customers\n"
                f"  Median 90d LTV:  R$ {predictions['predicted_ltv_90d'].median():.2f}\n"
                f"  Median 365d LTV: R$ {predictions['predicted_ltv_365d'].median():.2f}\n"
                f"  Median P(alive): {predictions['p_alive'].median():.2%}\n"
                f"  Platinum count:  {(predictions['ltv_segment'] == 'Platinum').sum():,}"
            )

        return predictions

    def segment_summary(self, predictions: pd.DataFrame) -> pd.DataFrame:
        """Aggregate predictions by LTV segment — for dashboard use."""
        return (
            predictions.groupby("ltv_segment")
            .agg(
                customer_count=("customer_unique_id", "count"),
                avg_p_alive=("p_alive", "mean"),
                avg_ltv_365d=("predicted_ltv_365d", "mean"),
                total_predicted_revenue=("predicted_ltv_365d", "sum"),
                avg_purchases_90d=("predicted_purchases_90d", "mean"),
            )
            .round(2)
            .reset_index()
            .sort_values("avg_ltv_365d", ascending=False)
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _validate(self, rfm: pd.DataFrame) -> pd.DataFrame:
        required = [
            "customer_unique_id",
            "frequency_repeat",
            "recency_days",
            "T_days",
            "monetary_mean",
        ]
        missing = [c for c in required if c not in rfm.columns]
        if missing:
            raise ValueError(f"RFM DataFrame missing columns: {missing}")

        # BG/NBD constraints
        rfm = rfm[
            (rfm["frequency_repeat"] >= 0)
            & (rfm["recency_days"] >= 0)
            & (rfm["T_days"] > 0)
            & (rfm["monetary_mean"] > 0)
            & (rfm["recency_days"] <= rfm["T_days"])
        ].copy()

        logger.info(f"Valid RFM rows: {len(rfm):,}")
        return rfm

    def _evaluate(self, rfm: pd.DataFrame) -> dict[str, float]:
        """Calibration-holdout evaluation using last 180 days as holdout."""
        try:
            # Need at least a year of data for a meaningful split
            if rfm["T_days"].max() < 365:
                logger.warning("Insufficient history for holdout eval — skipping")
                return {}

            summary = calibration_and_holdout_data(
                transactions=rfm.assign(
                    date=pd.Timestamp.now() - pd.to_timedelta(rfm["T_days"], unit="D"),
                    customer_id=rfm["customer_unique_id"],
                    monetary_value=rfm["monetary_mean"],
                ).rename(columns={"customer_unique_id": "customer_id"}),
                customer_id_col="customer_id",
                datetime_col="date",
                monetary_value_col="monetary_mean",
                calibration_period_end=pd.Timestamp.now() - pd.Timedelta(days=180),
            )

            actual = summary["frequency_holdout"].values
            predicted = self.bgf.predict(
                t=180,
                frequency=summary["frequency_cal"].values,
                recency=summary["recency_cal"].values,
                T=summary["T_cal"].values,
            )

            mae = mean_absolute_error(actual, predicted)
            mape = mean_absolute_percentage_error(actual + 1e-6, predicted + 1e-6)
            logger.info(f"Holdout eval — MAE: {mae:.4f}  MAPE: {mape:.4f}")
            return {"bgnbd_mae": float(mae), "bgnbd_mape": float(mape)}

        except Exception as e:
            logger.warning(f"Holdout evaluation failed: {e}")
            return {}

    def _write_seed(self, predictions: pd.DataFrame) -> None:
        """Write LTV predictions to dbt seed file."""
        cols = [
            "customer_unique_id",
            "predicted_ltv_90d",
            "predicted_ltv_365d",
            "predicted_purchases_90d",
            "predicted_at",
        ]
        out = predictions[cols].copy()
        out = out.round(4)

        SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(SEED_PATH, index=False)
        logger.info(f"LTV seed written → {SEED_PATH}  ({len(out):,} rows)")
