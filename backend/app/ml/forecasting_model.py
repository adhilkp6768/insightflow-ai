"""Daily revenue forecast with a chronological holdout."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.evaluation import regression_scores


def _daily(frame: pd.DataFrame) -> pd.Series:
    valid = frame.loc[frame["is_valid"].astype(bool)].copy()
    if valid.empty:
        return pd.Series(dtype=float)
    revenue = pd.to_numeric(valid["revenue"], errors="coerce").fillna(0)
    daily = revenue.groupby(valid["invoice_date"].dt.normalize()).sum()
    daily.index = pd.DatetimeIndex(daily.index)
    return daily.sort_index().asfreq("D", fill_value=0.0).astype(float)


def _seasonal_naive(train: pd.Series, horizon: int) -> np.ndarray:
    period = 7 if len(train) >= 14 else 1
    history = [float(value) for value in train.to_numpy()]
    predictions = []
    for _ in range(horizon):
        predictions.append(history[-period])
        history.append(predictions[-1])
    return np.asarray(predictions, dtype=float)


def _smooth(train: pd.Series, horizon: int) -> tuple[np.ndarray | None, str | None, float | None, str | None]:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        seasonal = len(train) >= 28
        model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add" if seasonal else None,
            seasonal_periods=7 if seasonal else None,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True)
        forecast = np.asarray(fit.forecast(horizon), dtype=float)
        residual = np.nanstd(np.asarray(fit.resid, dtype=float))
        name = "holt_winters_weekly" if seasonal else "holt_linear"
        return forecast, name, float(residual), None
    except Exception as exc:
        return None, None, None, f"The smoothing model did not fit: {exc.__class__.__name__}."


def forecast_revenue(frame: pd.DataFrame) -> dict:
    series = _daily(frame)
    history_days = int(len(series))
    if history_days < 45:
        return {
            "sufficient": False,
            "reliable": False,
            "history_days": history_days,
            "reason": f"The daily series has {history_days} points. At least 45 are required before a forecast is calculated.",
        }
    test_len = max(14, history_days // 5)
    if history_days - test_len < 30:
        test_len = history_days - 30
    train = series.iloc[:-test_len]
    test = series.iloc[-test_len:]
    baseline = _seasonal_naive(train, len(test))
    model_test, model_name, residual_std, model_error = _smooth(train, len(test))
    comparison = []
    for index, (day, actual) in enumerate(test.items()):
        comparison.append(
            {
                "date": pd.Timestamp(day).date().isoformat(),
                "actual": round(float(actual), 2),
                "baseline": round(float(baseline[index]), 2),
                "model": None if model_test is None else round(float(model_test[index]), 2),
            }
        )
    horizons = [days for days in (30, 60, 90) if history_days >= days * 2]
    omitted = [
        {"days": days, "reason": f"At least {days * 2} daily points are required for a {days}-day horizon."}
        for days in (30, 60, 90)
        if days not in horizons
    ]
    forward = []
    if horizons:
        horizon = max(horizons)
        future_model, future_name, future_std, future_error = _smooth(series, horizon)
        future_base = _seasonal_naive(series, horizon)
        chosen = future_model if future_model is not None else future_base
        chosen_name = future_name or "seasonal_naive_7"
        spread = future_std if future_std is not None else residual_std
        if future_error and model_error is None:
            model_error = future_error
        start = series.index.max() + pd.Timedelta(days=1)
        for index, value in enumerate(chosen):
            day = start + pd.Timedelta(days=index)
            lower = None if spread is None else round(float(value - 1.96 * spread), 2)
            upper = None if spread is None else round(float(value + 1.96 * spread), 2)
            forward.append(
                {
                    "date": day.date().isoformat(),
                    "value": round(float(value), 2),
                    "lower": lower,
                    "upper": upper,
                    "within_horizon": [days for days in horizons if index < days],
                }
            )
        interval_method = "1.96 times the residual standard deviation" if spread is not None else None
    else:
        chosen_name = None
        interval_method = None
    model_metrics = None if model_test is None else regression_scores(test.to_numpy(), model_test)
    mape = None if model_metrics is None else model_metrics["mape"]
    reliable = history_days >= 180 and mape is not None and mape < 35
    return {
        "sufficient": True,
        "reliable": reliable,
        "history_days": history_days,
        "holdout_days": int(len(test)),
        "horizons": horizons,
        "omitted_horizons": omitted,
        "baseline": {"name": "seasonal_naive_7" if len(train) >= 14 else "naive", **regression_scores(test.to_numpy(), baseline)},
        "model": None
        if model_metrics is None
        else {"name": model_name, **model_metrics},
        "comparison": comparison[-60:],
        "forecast": forward,
        "forward_model": chosen_name,
        "interval_method": interval_method,
        "limitations": [
            item
            for item in [
                "Error metrics use the last portion of the series. Those days are not used to fit the evaluated models.",
                "The forward forecast is fit on the full history after that evaluation.",
                "Intervals are residual bands, not a formal prediction interval from the model.",
                None
                if reliable
                else "This forecast is not marked reliable. The history is shorter than 180 days or the holdout MAPE is 35% or higher.",
                model_error,
            ]
            if item
        ],
    }
