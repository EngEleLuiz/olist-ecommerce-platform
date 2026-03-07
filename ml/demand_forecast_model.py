"""Demand Forecast Model — LightGBM with time-series features.

Forecasts weekly order volume by Brazilian state + product category.
Horizon: 4 weeks ahead.

Design decisions:
  - Walk-forward validation (expanding window) — correct for time series
  - Lag features (1w, 2w, 4w, 8w) + rolling stats (4w, 8w mean/std)
  - Brazilian public holidays as binary features
  - Quantile regression: predicts p10/p50/p90 for uncertainty bands
  - LightGBM over ARIMA: handles 27 states × 70+ categories simultaneously
    without fitting a separate model per series

Usage:
    from ml.demand_forecast_model import DemandForecastModel
    model = DemandForecastModel()
    forecast = model.train_and_forecast(demand_df)  # loader.demand_series()
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from loguru import logger
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error
from sklearn.preprocessing import LabelEncoder

MODEL_DIR = Path(os.getenv("MODEL_DIR", "ml/artifacts"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

_HERE = Path(__file__).resolve().parent.parent
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "mlruns")

FORECAST_HORIZON = 4  # weeks ahead

# Brazilian public holidays (month-day tuples) — major shopping events
BR_HOLIDAYS = {
    (1, 1),   # Ano Novo
    (2, 13),  # Carnaval (approx)
    (4, 21),  # Tiradentes
    (5, 1),   # Dia do Trabalho
    (9, 7),   # Independência
    (10, 12), # Nossa Senhora Aparecida
    (11, 2),  # Finados
    (11, 15), # Proclamação da República
    (11, 28), # Black Friday (approx)
    (12, 25), # Natal
}


class DemandForecastModel:
    """LightGBM weekly demand forecast with walk-forward validation.

    Args:
        forecast_horizon: Number of weeks ahead to forecast (default 4).
        n_splits: Number of walk-forward CV folds.
    """

    def __init__(
        self,
        forecast_horizon: int = FORECAST_HORIZON,
        n_splits: int = 5,
    ) -> None:
        self.horizon   = forecast_horizon
        self.n_splits  = n_splits
        self.models:   dict[str, LGBMRegressor] = {}  # one per quantile
        self.encoders: dict[str, LabelEncoder]  = {}
        self.feature_cols: list[str] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def train_and_forecast(self, demand: pd.DataFrame) -> pd.DataFrame:
        """Train on historical demand and return 4-week-ahead forecast.

        Args:
            demand: Output of OlistLoader.demand_series() with columns:
                    week_start, customer_state, category, order_count

        Returns:
            DataFrame with state × category × forecast_week + p10/p50/p90
        """
        demand = demand.copy()
        demand["week_start"] = pd.to_datetime(demand["week_start"])

        logger.info(
            f"Demand series — {len(demand):,} rows  "
            f"{demand['week_start'].min().date()} → {demand['week_start'].max().date()}"
        )

        with mlflow.start_run(run_name="demand_forecast_lgbm"):
            mlflow.set_tracking_uri(MLFLOW_URI)
            mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_DEMAND", "olist-demand-forecast"))
            mlflow.log_params({
                "horizon_weeks": self.horizon,
                "n_splits":      self.n_splits,
                "n_series":      demand.groupby(["customer_state", "category"]).ngroups,
            })

            # Build feature matrix
            df = self._build_features(demand)

            # Walk-forward CV
            cv_metrics = self._walk_forward_cv(df)
            mlflow.log_metrics({f"cv_{k}": v for k, v in cv_metrics.items()})
            logger.info(f"CV — MAE: {cv_metrics['mae']:.2f}  MAPE: {cv_metrics['mape']:.2%}")

            # Train final models on all data
            self._train_final(df)

            # Generate forecast
            forecast = self._forecast(demand)
            mlflow.log_param("forecast_rows", len(forecast))

            self._save()
            logger.info(
                f"Forecast complete — "
                f"{len(forecast):,} rows × {self.horizon} weeks ahead"
            )

        return forecast

    def load(self, path: Path | None = None) -> None:
        path = path or MODEL_DIR / "demand_forecast_model.pkl"
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.models       = state["models"]
        self.encoders     = state["encoders"]
        self.feature_cols = state["feature_cols"]
        logger.info(f"Loaded demand forecast model from {path}")

    def top_features(self, quantile: str = "p50", n: int = 15) -> pd.DataFrame:
        model = self.models.get(quantile)
        if model is None:
            raise ValueError(f"No model for quantile {quantile}")
        imp = model.feature_importances_
        return (
            pd.DataFrame({"feature": self.feature_cols, "importance": imp})
            .sort_values("importance", ascending=False)
            .head(n)
            .reset_index(drop=True)
        )

    # ── Feature engineering ───────────────────────────────────────────────────

    def _build_features(self, demand: pd.DataFrame) -> pd.DataFrame:
        """Add lags, rolling stats, time features, and holidays."""
        # Ensure complete grid (fill missing weeks with 0)
        demand = self._fill_grid(demand)
        demand = demand.sort_values(["customer_state", "category", "week_start"])

        grp = demand.groupby(["customer_state", "category"])

        # Lag features
        for lag in [1, 2, 4, 8]:
            demand[f"lag_{lag}w"] = grp["order_count"].shift(lag)

        # Rolling stats (on lag-1 to avoid leakage)
        for window in [4, 8]:
            demand[f"roll_mean_{window}w"] = (
                grp["order_count"].shift(1).transform(
                    lambda x: x.rolling(window, min_periods=1).mean()
                )
            )
            demand[f"roll_std_{window}w"] = (
                grp["order_count"].shift(1).transform(
                    lambda x: x.rolling(window, min_periods=1).std().fillna(0)
                )
            )

        # Trend: slope over last 4 weeks
        def rolling_slope(series: pd.Series, w: int = 4) -> pd.Series:
            out = series.copy() * 0.0
            for i in range(w, len(series)):
                y = series.iloc[i - w:i].values
                if np.std(y) > 0:
                    out.iloc[i] = np.polyfit(range(w), y, 1)[0]
            return out

        demand["trend_4w"] = grp["order_count"].transform(
            lambda x: rolling_slope(x.shift(1).fillna(0))
        )

        # Time features
        demand["week_of_year"] = demand["week_start"].dt.isocalendar().week.astype(int)
        demand["month"]        = demand["week_start"].dt.month
        demand["quarter"]      = demand["week_start"].dt.quarter
        demand["year"]         = demand["week_start"].dt.year

        # Holiday flag
        demand["is_holiday_week"] = demand["week_start"].apply(
            lambda d: int(any(
                (d + pd.Timedelta(days=i)).month == m and
                (d + pd.Timedelta(days=i)).day   == day
                for i in range(7)
                for m, day in BR_HOLIDAYS
            ))
        )

        # Peak season (Nov-Dec)
        demand["is_peak_season"] = demand["month"].isin([11, 12]).astype(int)

        # Encode categoricals
        for col in ["customer_state", "category"]:
            if col not in self.encoders:
                self.encoders[col] = LabelEncoder()
                demand[f"{col}_enc"] = self.encoders[col].fit_transform(demand[col].astype(str))
            else:
                demand[f"{col}_enc"] = self.encoders[col].transform(demand[col].astype(str))

        return demand.dropna(subset=["lag_1w"])

    def _fill_grid(self, demand: pd.DataFrame) -> pd.DataFrame:
        """Fill missing week × state × category combinations with 0."""
        weeks      = demand["week_start"].unique()
        states     = demand["customer_state"].unique()
        categories = demand["category"].unique()

        full_idx = pd.MultiIndex.from_product(
            [weeks, states, categories],
            names=["week_start", "customer_state", "category"],
        )
        grid = pd.DataFrame(index=full_idx).reset_index()
        return grid.merge(
            demand[["week_start", "customer_state", "category", "order_count"]],
            on=["week_start", "customer_state", "category"],
            how="left",
        ).fillna({"order_count": 0})

    # ── Training ──────────────────────────────────────────────────────────────

    @property
    def _feature_cols(self) -> list[str]:
        return [
            "lag_1w", "lag_2w", "lag_4w", "lag_8w",
            "roll_mean_4w", "roll_std_4w", "roll_mean_8w", "roll_std_8w",
            "trend_4w", "week_of_year", "month", "quarter",
            "is_holiday_week", "is_peak_season",
            "customer_state_enc", "category_enc",
        ]

    def _walk_forward_cv(self, df: pd.DataFrame) -> dict[str, float]:
        """Expanding-window cross-validation."""
        weeks  = sorted(df["week_start"].unique())
        n      = len(weeks)
        fold_size = n // (self.n_splits + 1)

        all_mae, all_mape = [], []

        for fold in range(self.n_splits):
            cutoff_idx = fold_size * (fold + 1)
            if cutoff_idx + self.horizon >= n:
                break

            train_end = weeks[cutoff_idx]
            val_start = weeks[cutoff_idx]
            val_end   = weeks[min(cutoff_idx + self.horizon, n - 1)]

            X_train = df[df["week_start"] <  train_end][self._feature_cols].fillna(0)
            y_train = df[df["week_start"] <  train_end]["order_count"]
            X_val   = df[(df["week_start"] >= val_start) & (df["week_start"] <= val_end)][self._feature_cols].fillna(0)
            y_val   = df[(df["week_start"] >= val_start) & (df["week_start"] <= val_end)]["order_count"]

            if len(X_train) < 100 or len(X_val) == 0:
                continue

            m = LGBMRegressor(
                n_estimators=200, learning_rate=0.05,
                num_leaves=31, min_child_samples=20,
                random_state=42, verbose=-1,
            )
            m.fit(X_train, y_train)
            preds = np.clip(m.predict(X_val), 0, None)

            all_mae.append(mean_absolute_error(y_val, preds))
            all_mape.append(mean_absolute_percentage_error(y_val + 1e-6, preds + 1e-6))

        return {
            "mae":  float(np.mean(all_mae))  if all_mae  else 0.0,
            "mape": float(np.mean(all_mape)) if all_mape else 0.0,
        }

    def _train_final(self, df: pd.DataFrame) -> None:
        """Train p10 / p50 / p90 quantile models on full data."""
        X = df[self._feature_cols].fillna(0)
        y = df["order_count"]
        self.feature_cols = self._feature_cols

        quantile_params = {
            "p10": {"objective": "quantile", "alpha": 0.10},
            "p50": {"objective": "quantile", "alpha": 0.50},
            "p90": {"objective": "quantile", "alpha": 0.90},
        }

        for name, extra in quantile_params.items():
            m = LGBMRegressor(
                n_estimators=300,
                learning_rate=0.05,
                num_leaves=63,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1,
                **extra,
            )
            m.fit(X, y)
            self.models[name] = m
            logger.info(f"Trained {name} quantile model ✓")

    # ── Forecasting ───────────────────────────────────────────────────────────

    def _forecast(self, demand: pd.DataFrame) -> pd.DataFrame:
        """Generate future predictions by iteratively appending forecasts."""
        df = self._build_features(demand.copy())
        last_week = df["week_start"].max()
        forecasts = []

        for step in range(1, self.horizon + 1):
            next_week = last_week + pd.Timedelta(weeks=step)

            # Build a row for each state × category for next_week
            states     = demand["customer_state"].unique()
            categories = demand["category"].unique()
            next_rows  = pd.DataFrame([
                {"week_start": next_week, "customer_state": s, "category": c, "order_count": 0}
                for s in states for c in categories
            ])

            # Append to current and recompute features
            extended = pd.concat([demand, next_rows[["week_start", "customer_state", "category", "order_count"]]], ignore_index=True)
            extended_feats = self._build_features(extended)
            pred_rows = extended_feats[extended_feats["week_start"] == next_week].copy()

            if pred_rows.empty:
                continue

            X_pred = pred_rows[self.feature_cols].fillna(0)
            for q in ["p10", "p50", "p90"]:
                pred_rows[f"forecast_{q}"] = np.clip(self.models[q].predict(X_pred), 0, None)

            pred_rows["forecast_week"] = step
            pred_rows["forecast_date"] = next_week
            forecasts.append(pred_rows[["customer_state", "category", "forecast_date",
                                         "forecast_week", "forecast_p10", "forecast_p50",
                                         "forecast_p90"]])

            # Feed p50 back for next step
            demand = pd.concat([demand, pred_rows[["week_start", "customer_state",
                                                     "category"]].assign(
                order_count=pred_rows["forecast_p50"].values
            )], ignore_index=True)

        return pd.concat(forecasts, ignore_index=True) if forecasts else pd.DataFrame()

    def _save(self) -> None:
        path = MODEL_DIR / "demand_forecast_model.pkl"
        with open(path, "wb") as f:
            pickle.dump({
                "models":       self.models,
                "encoders":     self.encoders,
                "feature_cols": self.feature_cols,
            }, f)
        logger.info(f"Model saved to {path}")
