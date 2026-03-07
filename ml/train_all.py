"""Train all three Olist ML models in sequence.

Entry point for the Step Functions pipeline and for local re-training.

Usage:
    python -m ml.train_all                      # train all
    python -m ml.train_all --model delay        # train one
    python -m ml.train_all --model ltv
    python -m ml.train_all --model demand
"""

from __future__ import annotations

import argparse
import os

import mlflow
from dotenv import load_dotenv
from loguru import logger

from data_loader import OlistLoader
from ml.customer_ltv_model import CustomerLTVModel
from ml.delivery_delay_model import DeliveryDelayModel
from ml.demand_forecast_model import DemandForecastModel

load_dotenv()

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def train_delay(loader: OlistLoader) -> dict:
    logger.info("━━━ Training: Delivery Delay Model (XGBoost) ━━━")
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_DELAY", "olist/delivery-delay"))
    df = loader.order_features()
    df = df[df["order_status"] == "delivered"].dropna(subset=["is_late"])
    model = DeliveryDelayModel(n_trials=30)
    metrics = model.train(df)
    logger.info(f"Delay model — {metrics}")
    return metrics


def train_ltv(loader: OlistLoader) -> dict:
    logger.info("━━━ Training: Customer LTV Model (BG/NBD + Gamma-Gamma) ━━━")
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_LTV", "olist/customer-ltv"))
    rfm = loader.customer_rfm()
    model = CustomerLTVModel()
    predictions = model.train_and_predict(rfm)
    logger.info(f"LTV model — {len(predictions):,} customers predicted")
    return {"n_customers": len(predictions)}


def train_demand(loader: OlistLoader) -> dict:
    logger.info("━━━ Training: Demand Forecast Model (LightGBM) ━━━")
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_DEMAND", "olist/demand-forecast"))
    demand = loader.demand_series()
    model = DemandForecastModel(forecast_horizon=4, n_splits=5)
    forecast = model.train_and_forecast(demand)
    logger.info(f"Demand model — {len(forecast):,} forecast rows")
    return {"n_forecast_rows": len(forecast)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Olist ML models")
    parser.add_argument(
        "--model",
        choices=["delay", "ltv", "demand", "all"],
        default="all",
        help="Which model to train (default: all)",
    )
    args = parser.parse_args()

    mlflow.set_tracking_uri(MLFLOW_URI)
    loader = OlistLoader()

    trainers = {
        "delay":  train_delay,
        "ltv":    train_ltv,
        "demand": train_demand,
    }

    targets = list(trainers.keys()) if args.model == "all" else [args.model]

    results = {}
    for name in targets:
        try:
            results[name] = trainers[name](loader)
        except Exception as e:
            logger.error(f"Failed to train {name}: {e}")
            raise

    logger.info("━━━ All models trained ━━━")
    for name, metrics in results.items():
        logger.info(f"  {name}: {metrics}")


if __name__ == "__main__":
    main()
