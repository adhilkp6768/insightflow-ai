"""Error metrics. MAPE ignores actual values of zero."""

from __future__ import annotations

import numpy as np


def regression_scores(actual, predicted) -> dict[str, float | None]:
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)
    error = predicted_array - actual_array
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    nonzero = actual_array != 0
    mape = None
    if nonzero.any():
        mape = float(np.mean(np.abs(error[nonzero] / actual_array[nonzero])) * 100)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": None if mape is None else round(mape, 4)}
