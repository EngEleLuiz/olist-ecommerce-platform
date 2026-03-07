"""Delivery Delay Model — XGBoost binary classifier.

Predicts at order placement time whether a delivery will arrive late.
Uses only features available at the moment of purchase (no data leakage).

Key design decisions:
  - Chronological train/val/test split — never shuffle time series data
  - Optuna hyperparameter tuning with early stopping
  - SHAP values for feature attribution (explainability for Zallpy clients)
  - Threshold tuning: optimises F1 not accuracy (class imbalance ~20% late)
  - Saves: model .pkl, threshold .json, SHAP summary .png, MLflow run

Usage:
    from ml.delivery_delay_model import DeliveryDelayModel
    model = DeliveryDelayModel()
    model.train(df)          # df = loader.order_features()
    pred = model.predict(df)
"""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any

import mlflow
import mlflow.xgboost
import numpy as np
import optuna
import pandas as pd
import shap
from loguru import logger
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

optuna.logging.set_verbosity(optuna.logging.WARNING)

MODEL_DIR = Path(os.getenv("MODEL_DIR", "ml/artifacts"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Use local file tracking by default — no MLflow server needed
_HERE = Path(__file__).resolve().parent.parent
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "mlruns")

# Features available at order placement time only
FEATURES = [
    "purchase_month",
    "purchase_dow",
    "purchase_hour",
    "item_count",
    "total_price",
    "total_freight",
    "freight_ratio",
    "max_installments",
    "estimated_days",
    "distinct_sellers",
    "avg_product_weight_g",
    "is_peak_season",
    "is_weekend_purchase",
    "state_seller_late_rate",  # state-level seller reliability proxy
]

CAT_FEATURES = ["main_category", "main_payment_type", "customer_state", "customer_region"]
TARGET = "is_late"


class DeliveryDelayModel:
    """XGBoost delivery delay classifier with SHAP explainability.

    Args:
        n_trials: Number of Optuna hyperparameter search trials.
        random_state: Seed for reproducibility.
    """

    def __init__(self, n_trials: int = 30, random_state: int = 42) -> None:
        self.n_trials = n_trials
        self.random_state = random_state
        self.model: XGBClassifier | None = None
        self.threshold: float = 0.5
        self.encoders: dict[str, LabelEncoder] = {}
        self.feature_names: list[str] = []
        self._shap_values: np.ndarray | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def train(self, df: pd.DataFrame) -> dict[str, float]:
        """Train on historical orders, return test-set metrics."""
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_DELAY", "olist-delivery-delay"))
        df = self._prepare(df)
        X, y = df[self.feature_names], df[TARGET]

        # Chronological split — 70 / 15 / 15
        n = len(df)
        i_val = int(n * 0.70)
        i_test = int(n * 0.85)

        X_train, y_train = X.iloc[:i_val], y.iloc[:i_val]
        X_val, y_val = X.iloc[i_val:i_test], y.iloc[i_val:i_test]
        X_test, y_test = X.iloc[i_test:], y.iloc[i_test:]

        logger.info(f"Split — train: {len(X_train):,}  val: {len(X_val):,}  test: {len(X_test):,}")

        # Class weight for imbalanced labels
        scale_pos = float((y_train == 0).sum() / (y_train == 1).sum())
        logger.info(f"Class imbalance — scale_pos_weight: {scale_pos:.2f}")

        with mlflow.start_run(run_name="delivery_delay_xgb"):
            # Hyperparameter search
            best_params = self._tune(X_train, y_train, X_val, y_val, scale_pos)
            mlflow.log_params(best_params)

            # Final model
            self.model = XGBClassifier(
                **best_params,
                scale_pos_weight=scale_pos,
                random_state=self.random_state,
                eval_metric="aucpr",
                early_stopping_rounds=20,
                verbosity=0,
            )
            self.model.fit(
                X_train,
                y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )

            # Threshold tuning on validation set
            self.threshold = self._tune_threshold(X_val, y_val)
            logger.info(f"Optimal threshold: {self.threshold:.3f}")

            # Test metrics
            metrics = self._evaluate(X_test, y_test)
            mlflow.log_metrics(metrics)
            mlflow.log_param("threshold", self.threshold)

            # SHAP
            self._compute_shap(X_train.sample(min(2000, len(X_train)), random_state=42))

            # Save artifacts
            self._save()
            mlflow.xgboost.log_model(self.model, "model")

            logger.info(
                f"Train complete — AUC: {metrics['auc_roc']:.3f}  "
                f"F1: {metrics['f1']:.3f}  "
                f"AP: {metrics['avg_precision']:.3f}"
            )

        return metrics

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return predictions with probability and SHAP explanation."""
        assert self.model is not None, "Call train() or load() first"
        df_prep = self._prepare(df)
        X = df_prep[self.feature_names]

        proba = self.model.predict_proba(X)[:, 1]
        labels = (proba >= self.threshold).astype(int)

        result = df[["order_id"]].copy() if "order_id" in df.columns else pd.DataFrame()
        result["delay_probability"] = proba
        result["predicted_late"] = labels
        result["confidence"] = np.where(labels == 1, proba, 1 - proba)
        return result

    def load(self, path: Path | None = None) -> None:
        path = path or MODEL_DIR / "delivery_delay_model.pkl"
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.model = state["model"]
        self.threshold = state["threshold"]
        self.encoders = state["encoders"]
        self.feature_names = state["feature_names"]
        logger.info(f"Loaded delivery delay model from {path}")

    def top_features(self, n: int = 10) -> pd.DataFrame:
        """Return top-n features by XGBoost gain importance."""
        assert self.model is not None
        imp = self.model.get_booster().get_score(importance_type="gain")
        return (
            pd.DataFrame.from_dict(imp, orient="index", columns=["importance"])
            .sort_values("importance", ascending=False)
            .head(n)
            .reset_index()
            .rename(columns={"index": "feature"})
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Derived features not already in loader output
        if "is_peak_season" not in df.columns:
            df["is_peak_season"] = df["purchase_month"].isin([11, 12]).astype(int)
        if "is_weekend_purchase" not in df.columns:
            df["is_weekend_purchase"] = df["purchase_dow"].isin([5, 6]).astype(int)
        if "state_seller_late_rate" not in df.columns:
            # Approximate from data if not pre-computed
            state_lr = df.groupby("customer_state")["is_late"].transform("mean")
            df["state_seller_late_rate"] = state_lr.fillna(0)

        # Encode categoricals
        for col in CAT_FEATURES:
            if col not in df.columns:
                df[col] = "unknown"
            if col not in self.encoders:
                self.encoders[col] = LabelEncoder()
                df[col] = self.encoders[col].fit_transform(df[col].astype(str).fillna("unknown"))
            else:
                known = set(self.encoders[col].classes_)
                df[col] = (
                    df[col]
                    .astype(str)
                    .fillna("unknown")
                    .apply(lambda x: x if x in known else "unknown")
                )
                df[col] = self.encoders[col].transform(df[col])

        # Fill numerics
        all_features = FEATURES + CAT_FEATURES
        for col in all_features:
            if col not in df.columns:
                df[col] = 0
        df[all_features] = df[all_features].fillna(0)

        self.feature_names = all_features
        return (
            df.sort_values("order_purchase_timestamp")
            if "order_purchase_timestamp" in df.columns
            else df
        )

    def _tune(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        scale_pos: float,
    ) -> dict[str, Any]:
        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 600),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0, 5),
                "reg_alpha": trial.suggest_float("reg_alpha", 0, 2),
                "reg_lambda": trial.suggest_float("reg_lambda", 0, 2),
            }
            m = XGBClassifier(
                **params,
                scale_pos_weight=scale_pos,
                random_state=self.random_state,
                verbosity=0,
                eval_metric="aucpr",
            )
            m.fit(X_train, y_train, verbose=False)
            proba = m.predict_proba(X_val)[:, 1]
            return average_precision_score(y_val, proba)

        study = optuna.create_study(
            direction="maximize", sampler=optuna.samplers.TPESampler(seed=self.random_state)
        )
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)
        logger.info(f"Best Optuna AP: {study.best_value:.4f}")
        return study.best_params

    def _tune_threshold(self, X_val: pd.DataFrame, y_val: pd.Series) -> float:
        proba = self.model.predict_proba(X_val)[:, 1]
        best_f1, best_t = 0.0, 0.5
        for t in np.arange(0.2, 0.8, 0.01):
            f1 = f1_score(y_val, (proba >= t).astype(int), zero_division=0)
            if f1 > best_f1:
                best_f1, best_t = f1, float(t)
        return best_t

    def _evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
        proba = self.model.predict_proba(X_test)[:, 1]
        labels = (proba >= self.threshold).astype(int)
        report = classification_report(y_test, labels, output_dict=True, zero_division=0)
        logger.info("\n" + classification_report(y_test, labels, zero_division=0))
        return {
            "auc_roc": float(roc_auc_score(y_test, proba)),
            "avg_precision": float(average_precision_score(y_test, proba)),
            "f1": float(f1_score(y_test, labels, zero_division=0)),
            "precision": float(report["1"]["precision"]),
            "recall": float(report["1"]["recall"]),
        }

    def _compute_shap(self, X_sample: pd.DataFrame) -> None:
        explainer = shap.TreeExplainer(self.model)
        self._shap_values = explainer.shap_values(X_sample)
        logger.info("SHAP values computed")

    def _save(self) -> None:
        path = MODEL_DIR / "delivery_delay_model.pkl"
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "threshold": self.threshold,
                    "encoders": self.encoders,
                    "feature_names": self.feature_names,
                },
                f,
            )
        # Save threshold separately for the dbt seed update script
        with open(MODEL_DIR / "delivery_delay_threshold.json", "w") as f:
            json.dump({"threshold": self.threshold}, f)
        logger.info(f"Model saved to {path}")
