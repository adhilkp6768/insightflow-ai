"""Dataset quality profile.

Score = 100 × (0.30 completeness + 0.20 uniqueness + 0.30 validity + 0.20 consistency).

Completeness weights date 0.30, quantity 0.25, price 0.25, and customer 0.20.
Uniqueness is one minus the share of exact duplicate rows.
Validity is the share of rows with a parseable date, numeric quantity, non-negative price,
and a non-empty invoice when those columns are mapped.
Consistency is the share of rows whose quantity and price are both numeric and whose price
is not negative. Returns remain consistent.
Outliers are reported with the interquartile rule and do not change the score.
"""

from __future__ import annotations

import pandas as pd

from app.domain.columns import clean_mapping
from app.utils.preprocessing import _blank, _parse_dates


def _present(series: pd.Series) -> pd.Series:
    return series.map(_blank).notna()


def _mapped(frame: pd.DataFrame, mapping: dict[str, str | None], role: str) -> pd.Series | None:
    column = mapping.get(role)
    if not column or column not in frame.columns:
        return None
    return frame[column]


def _outlier_summary(series: pd.Series | None) -> dict:
    if series is None:
        return {"count": 0, "method": "iqr", "note": "This column is not mapped."}
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric) < 8:
        return {"count": 0, "method": "iqr", "note": "Too few numeric values to estimate outliers."}
    q1 = float(numeric.quantile(0.25))
    q3 = float(numeric.quantile(0.75))
    iqr = q3 - q1
    if iqr == 0:
        return {"count": 0, "method": "iqr", "low": q1, "high": q3, "note": "The interquartile range is zero."}
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    count = int(((numeric < low) | (numeric > high)).sum())
    return {"count": count, "method": "iqr", "low": low, "high": high}


def _infer_type(series: pd.Series) -> str:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.8:
        return "number"
    if _parse_dates(series).notna().mean() > 0.8:
        return "date"
    return "text"


def quality_report(frame: pd.DataFrame, mapping: dict[str, str | None] | None) -> dict:
    roles = clean_mapping(mapping)
    row_count = int(len(frame))
    if row_count == 0:
        return {
            "score": 0.0,
            "formula": "100 × (0.30 completeness + 0.20 uniqueness + 0.30 validity + 0.20 consistency)",
            "completeness": 0.0,
            "uniqueness": 0.0,
            "validity": 0.0,
            "consistency": 0.0,
            "row_count": 0,
            "column_count": int(len(frame.columns)),
            "duplicate_rows": 0,
            "missing_values": 0,
            "columns": [],
            "outliers": {},
            "notes": ["The file has no rows."],
        }

    weights = {"invoice_date": 0.30, "quantity": 0.25, "unit_price": 0.25, "customer_id": 0.20}
    completeness = 0.0
    for role, weight in weights.items():
        series = _mapped(frame, roles, role)
        completeness += 0.0 if series is None else float(_present(series).mean()) * weight

    duplicate_rows = int(frame.duplicated().sum())
    uniqueness = 1 - (duplicate_rows / row_count)

    valid = pd.Series(True, index=frame.index)
    date_series = _mapped(frame, roles, "invoice_date")
    quantity_series = _mapped(frame, roles, "quantity")
    price_series = _mapped(frame, roles, "unit_price")
    invoice_series = _mapped(frame, roles, "invoice_id")
    if date_series is not None:
        valid &= _parse_dates(date_series).notna()
    if quantity_series is not None:
        valid &= pd.to_numeric(quantity_series, errors="coerce").notna()
    if price_series is not None:
        numeric_price = pd.to_numeric(price_series, errors="coerce")
        valid &= numeric_price.notna() & (numeric_price >= 0)
    if invoice_series is not None:
        valid &= _present(invoice_series)
    validity = float(valid.mean())

    if quantity_series is not None and price_series is not None:
        quantity = pd.to_numeric(quantity_series, errors="coerce")
        price = pd.to_numeric(price_series, errors="coerce")
        consistency = float((quantity.notna() & price.notna() & (price >= 0)).mean())
    else:
        consistency = 0.0

    score = 100 * (0.30 * completeness + 0.20 * uniqueness + 0.30 * validity + 0.20 * consistency)
    role_by_column = {column: role for role, column in roles.items() if column}
    columns = []
    missing_values = 0
    for ordinal, name in enumerate(frame.columns):
        series = frame[name]
        null_count = int((~_present(series)).sum())
        missing_values += null_count
        columns.append(
            {
                "name": str(name),
                "ordinal": ordinal,
                "inferred_type": _infer_type(series),
                "semantic_role": role_by_column.get(str(name)),
                "null_count": null_count,
                "distinct_count": int(series.map(_blank).nunique(dropna=True)),
            }
        )

    return {
        "score": round(score, 1),
        "formula": "100 × (0.30 completeness + 0.20 uniqueness + 0.30 validity + 0.20 consistency)",
        "completeness": round(completeness, 4),
        "uniqueness": round(uniqueness, 4),
        "validity": round(validity, 4),
        "consistency": round(consistency, 4),
        "row_count": row_count,
        "column_count": int(len(frame.columns)),
        "duplicate_rows": duplicate_rows,
        "missing_values": missing_values,
        "columns": columns,
        "outliers": {
            "quantity": _outlier_summary(quantity_series),
            "unit_price": _outlier_summary(price_series),
        },
        "notes": [
            "Returns and cancellations remain valid because they change revenue.",
            "Outliers are reported and are not removed.",
            "A missing customer ID lowers completeness and does not by itself invalidate a sale.",
        ],
    }
