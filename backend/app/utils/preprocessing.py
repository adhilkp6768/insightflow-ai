"""Cleaning rules for a retail transaction file.

The uploaded file is never changed. These functions return a new frame.
"""

from __future__ import annotations

import warnings
from typing import Any

import pandas as pd

from app.domain.columns import REQUIRED_FOR_SALES, clean_mapping


def _blank(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        return None
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text == "" or text.lower() in {"nan", "none", "<na>"}:
        return None
    return text


def _column(frame: pd.DataFrame, mapping: dict[str, str | None], role: str) -> pd.Series:
    column = mapping.get(role)
    if not column or column not in frame.columns:
        return pd.Series([pd.NA] * len(frame), index=frame.index, dtype="object")
    return frame[column]


def _parse_dates(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        primary = pd.to_datetime(series, errors="coerce", format="mixed")
        secondary = pd.to_datetime(series, errors="coerce", dayfirst=True, format="mixed")
    if secondary.notna().sum() > primary.notna().sum():
        return secondary
    return primary


def clean_transactions(
    frame: pd.DataFrame,
    mapping: dict[str, str | None] | None,
    options: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    options = options or {}
    roles = clean_mapping(mapping)
    missing = [role for role in REQUIRED_FOR_SALES if not roles.get(role)]
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"Map these columns before cleaning: {names}.")
    for role, column in roles.items():
        if column and column not in frame.columns:
            raise ValueError(f"The mapped column for {role} is not in the file.")

    work = frame.copy()
    removed_duplicates = 0
    if options.get("drop_exact_duplicates"):
        before = len(work)
        work = work.drop_duplicates()
        removed_duplicates = before - len(work)

    invoice = _column(work, roles, "invoice_id").map(_blank)
    dates = _parse_dates(_column(work, roles, "invoice_date"))
    quantity = pd.to_numeric(_column(work, roles, "quantity"), errors="coerce")
    price = pd.to_numeric(_column(work, roles, "unit_price"), errors="coerce")
    cost = pd.to_numeric(_column(work, roles, "unit_cost"), errors="coerce")
    stock = _column(work, roles, "stock_code").map(_blank)
    description = _column(work, roles, "description").map(_blank)
    customer = _column(work, roles, "customer_id").map(_blank)
    country = _column(work, roles, "country").map(_blank)
    category = _column(work, roles, "category").map(_blank)

    invoice_missing = invoice.isna()
    invalid = invoice_missing | dates.isna() | quantity.isna() | price.isna() | (price < 0)
    starts_with_c = invoice.fillna("").str.upper().str.startswith("C")
    negative_quantity = quantity < 0

    transaction_type = pd.Series("sale", index=work.index)
    transaction_type = transaction_type.mask(negative_quantity & ~starts_with_c, "return")
    transaction_type = transaction_type.mask(starts_with_c & ~invalid, "cancellation")
    transaction_type = transaction_type.mask(invalid, "invalid")
    revenue = quantity * price

    cleaned = pd.DataFrame(
        {
            "invoice_id": invoice,
            "invoice_date": dates.dt.strftime("%Y-%m-%d"),
            "stock_code": stock,
            "description": description,
            "quantity": quantity,
            "unit_price": price,
            "customer_id": customer,
            "country": country,
            "category": category,
            "unit_cost": cost,
            "revenue": revenue.where(~invalid),
            "transaction_type": transaction_type,
            "is_valid": (~invalid).astype(int),
        }
    )
    valid = cleaned["is_valid"].astype(bool)
    decisions = {
        "rows_in": int(len(frame)),
        "rows_out": int(len(cleaned)),
        "exact_duplicates_removed": int(removed_duplicates),
        "invalid_rows": int((~valid).sum()),
        "sales": int((cleaned["transaction_type"] == "sale").sum()),
        "returns": int((cleaned["transaction_type"] == "return").sum()),
        "cancellations": int((cleaned["transaction_type"] == "cancellation").sum()),
        "missing_customer_id": int(cleaned["customer_id"].isna().sum()),
        "missing_description": int(cleaned["description"].isna().sum()),
        "positive_cancellation_quantity": int((starts_with_c & (quantity > 0) & ~invalid).sum()),
        "raw_file_unchanged": True,
        "rules": [
            "Revenue is quantity multiplied by unit price.",
            "Invoices that start with C are cancellations and stay in the data.",
            "Negative quantities on other invoices are returns and stay in the data.",
            "Rows with an empty invoice, unparseable date, missing quantity, missing price, or negative price are invalid.",
            "Invalid rows stay in the cleaned version and are excluded from KPIs.",
            "Missing customer IDs stay in sales results and are excluded from customer models.",
            "Missing descriptions stay in the data and are counted in the profile.",
            "Exact duplicates are removed only when that option is selected, and only from the cleaned copy.",
        ],
    }
    return cleaned, decisions
