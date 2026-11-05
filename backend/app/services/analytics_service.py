"""Sales, customer, and product analytics from the cleaned table."""

from __future__ import annotations

import uuid

import pandas as pd
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import User
from app.services.access import require_dataset
from app.services.frames import apply_filters, load_frame, require_version
from app.services.metrics import (
    breakdown,
    definitions,
    filter_period,
    monthly_series,
    period_summary,
    previous_bounds,
    product_table,
    quarterly_series,
    revenue_distribution,
    weekday_series,
    with_growth,
)
from app.utils.json_safe import json_safe


def _bounds(frame: pd.DataFrame, date_from: str | None, date_to: str | None) -> tuple[str | None, str | None]:
    valid = frame.loc[frame["is_valid"]]
    if valid.empty:
        return date_from, date_to
    minimum = valid["invoice_date"].min().date().isoformat()
    maximum = valid["invoice_date"].max().date().isoformat()
    return date_from or minimum, date_to or maximum


def _prepared(db: Session, user: User, dataset_id: uuid.UUID, product: str | None, country: str | None, customer: str | None):
    dataset = require_dataset(db, user, dataset_id)
    version = require_version(db, dataset)
    frame = apply_filters(load_frame(version, db.connection()), product=product, country=country, customer=customer)
    return dataset, frame


def sales_analytics(
    db: Session,
    user: User,
    dataset_id: uuid.UUID,
    *,
    date_from: str | None,
    date_to: str | None,
    product: str | None,
    country: str | None,
    customer: str | None,
) -> dict:
    dataset, frame = _prepared(db, user, dataset_id, product, country, customer)
    start, end = _bounds(frame, date_from, date_to)
    current = filter_period(frame, start, end)
    previous = None
    previous_period = None
    if start and end:
        prev_start, prev_end = previous_bounds(start, end)
        previous = period_summary(filter_period(frame, prev_start, prev_end))
        previous_period = {"date_from": prev_start, "date_to": prev_end}
    summary = period_summary(current)
    limitations = []
    if dataset.source_type == "sample":
        limitations.append("This dataset is a generated sample. It is not the UCI Online Retail II extract.")
    if current.empty:
        limitations.append("No valid rows match the selected period and filters.")
    if not frame.empty and frame["category"].dropna().empty:
        limitations.append("Category charts are unavailable until a category column is mapped.")
    if summary["profit"] is None:
        limitations.append(summary["profit_reason"])
    return json_safe(
        {
            "dataset_id": str(dataset.id),
            "period": {"date_from": start, "date_to": end, "previous": previous_period},
            "definitions": definitions(current),
            "kpis": with_growth(summary, previous),
            "monthly": monthly_series(current),
            "quarterly": quarterly_series(current),
            "weekday": weekday_series(current),
            "distribution": revenue_distribution(current),
            "countries": breakdown(current, "country"),
            "products": breakdown(current, "product"),
            "categories": breakdown(current, "category"),
            "limitations": limitations,
        }
    )


def filter_options(db: Session, user: User, dataset_id: uuid.UUID) -> dict:
    dataset, frame = _prepared(db, user, dataset_id, None, None, None)
    valid = frame.loc[frame["is_valid"]]
    countries = sorted({str(value) for value in valid["country"].dropna() if str(value).strip()})
    product_totals = (
        valid.assign(code=valid["stock_code"].fillna("Unknown"))
        .groupby("code")["revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(100)
    )
    return {
        "countries": countries,
        "products": [
            {"stock_code": str(code), "revenue": round(float(value), 2)} for code, value in product_totals.items()
        ],
        "min_date": None if valid.empty else valid["invoice_date"].min().date().isoformat(),
        "max_date": None if valid.empty else valid["invoice_date"].max().date().isoformat(),
        "category_available": bool(valid["category"].notna().any()) if not valid.empty else False,
        "cost_available": bool(valid["unit_cost"].notna().any()) if not valid.empty else False,
        "source_type": dataset.source_type,
    }


def _customer_table(frame: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    valid = frame.loc[frame["is_valid"] & frame["customer_id"].notna()].copy()
    if valid.empty:
        return valid
    grouped = valid.groupby("customer_id")
    table = grouped.agg(
        last_purchase=("invoice_date", "max"),
        first_purchase=("invoice_date", "min"),
        frequency=("invoice_id", "nunique"),
        historical_value=("revenue", "sum"),
        country=("country", lambda values: values.dropna().mode().iloc[0] if not values.dropna().empty else None),
    )
    table["frequency"] = table["frequency"].astype(int)
    table["recency_days"] = (snapshot - table["last_purchase"]).dt.days.astype(int)
    tenure_days = (table["last_purchase"] - table["first_purchase"]).dt.days.clip(lower=1)
    table["projected_12_month_value"] = table["historical_value"] / tenure_days * 365
    return table


def _cohorts(frame: pd.DataFrame) -> list[dict]:
    valid = frame.loc[frame["is_valid"] & frame["customer_id"].notna()].copy()
    if valid.empty:
        return []
    first = valid.groupby("customer_id")["invoice_date"].min().dt.to_period("M")
    valid["cohort"] = valid["customer_id"].map(first)
    valid["offset"] = valid["invoice_date"].dt.to_period("M").astype("int64") - valid["cohort"].astype("int64")
    rows = []
    for cohort, part in valid.groupby("cohort", sort=True):
        members = part.loc[part["offset"] == 0, "customer_id"].nunique()
        if members == 0:
            members = part["customer_id"].nunique()
        retention = []
        for month in range(6):
            active = part.loc[part["offset"] == month, "customer_id"].nunique()
            retention.append(round(active / members, 4) if members else None)
        rows.append({"cohort": str(cohort), "customers": int(members), "retention": retention})
    return rows[-8:]


def customer_analytics(
    db: Session,
    user: User,
    dataset_id: uuid.UUID,
    *,
    date_from: str | None,
    date_to: str | None,
    country: str | None,
) -> dict:
    dataset = require_dataset(db, user, dataset_id)
    version = require_version(db, dataset)
    frame = load_frame(version, db.connection())
    if frame["customer_id"].dropna().empty:
        return {
            "available": False,
            "reason": "Map a customer column and create a cleaned version before customer analytics.",
            "customers": [],
            "cohorts": [],
        }
    start, end = _bounds(frame, date_from, date_to)
    current = apply_filters(filter_period(frame, start, end), country=country)
    snapshot = pd.Timestamp(end) if end else current["invoice_date"].max()
    table = _customer_table(current, snapshot)
    if table.empty:
        return {
            "available": False,
            "reason": "No valid rows in this period have a customer ID.",
            "customers": [],
            "cohorts": [],
        }
    retention_rate = None
    retention_base = 0
    if start and end:
        prev_start, prev_end = previous_bounds(start, end)
        previous = apply_filters(filter_period(frame, prev_start, prev_end), country=country)
        previous_ids = set(previous.loc[previous["customer_id"].notna(), "customer_id"])
        current_ids = set(table.index)
        retention_base = len(previous_ids)
        if retention_base:
            retention_rate = round(len(previous_ids & current_ids) / retention_base, 4)
    ordered = table.sort_values("historical_value", ascending=False)
    cutoff = ordered["historical_value"].quantile(0.8) if len(ordered) >= 5 else ordered["historical_value"].max()
    high_value = ordered.loc[ordered["historical_value"] >= cutoff].head(10)
    inactive = ordered.loc[ordered["recency_days"] > 90].sort_values("recency_days", ascending=False).head(10)

    def listing(part: pd.DataFrame) -> list[dict]:
        rows = []
        for customer_id, row in part.iterrows():
            rows.append(
                {
                    "customer_id": str(customer_id),
                    "country": None if pd.isna(row.country) else str(row.country),
                    "frequency": int(row.frequency),
                    "historical_value": round(float(row.historical_value), 2),
                    "recency_days": int(row.recency_days),
                    "projected_12_month_value": round(float(row.projected_12_month_value), 2),
                }
            )
        return rows

    repeat = int((table["frequency"] >= 2).sum())
    return json_safe(
        {
            "available": True,
            "customer_count": int(len(table)),
            "repeat_customer_count": repeat,
            "repeat_rate": round(repeat / len(table), 4),
            "retention_rate": retention_rate,
            "retention_base": retention_base,
            "retention_definition": "Share of customers active in the previous period who are also active in the selected period.",
            "value_definition": "Historical value is the sum of revenue, including returns. The 12-month figure projects that pace and is not a predictive model.",
            "average_historical_value": round(float(table["historical_value"].mean()), 2),
            "high_value": listing(high_value),
            "inactive": listing(inactive),
            "customers": listing(ordered.head(50)),
            "cohorts": _cohorts(current),
            "limitations": [
                "Blank customer IDs stay in sales totals and are excluded here.",
                "Inactive means no purchase in the 90 days before the end of the selected period.",
            ],
        }
    )


def customer_detail(db: Session, user: User, dataset_id: uuid.UUID, customer_id: str) -> dict:
    dataset = require_dataset(db, user, dataset_id)
    version = require_version(db, dataset)
    frame = load_frame(version, db.connection())
    rows = frame.loc[frame["customer_id"].fillna("").astype(str) == customer_id]
    if rows.empty:
        raise AppError("not_found", "Customer not found in this dataset.", 404)
    valid = rows.loc[rows["is_valid"]]
    snapshot = valid["invoice_date"].max() if not valid.empty else rows["invoice_date"].max()
    table = _customer_table(valid if not valid.empty else rows, snapshot)
    if table.empty:
        raise AppError("not_found", "Customer not found in this dataset.", 404)
    row = table.iloc[0]
    recent = valid.sort_values("invoice_date", ascending=False).head(8)
    invoices = [
        {
            "invoice_id": None if pd.isna(item.invoice_id) else str(item.invoice_id),
            "invoice_date": item.invoice_date.date().isoformat(),
            "description": None if pd.isna(item.description) else str(item.description),
            "quantity": None if pd.isna(item.quantity) else float(item.quantity),
            "revenue": None if pd.isna(item.revenue) else round(float(item.revenue), 2),
            "transaction_type": str(item.transaction_type),
        }
        for item in recent.itertuples()
    ]
    return {
        "customer_id": customer_id,
        "country": None if pd.isna(row.country) else str(row.country),
        "frequency": int(row.frequency),
        "historical_value": round(float(row.historical_value), 2),
        "recency_days": int(row.recency_days),
        "projected_12_month_value": round(float(row.projected_12_month_value), 2),
        "recent_invoices": invoices,
        "note": "This summary uses the customer ID already present in the dataset. No name or contact details are added.",
    }


def product_analytics(
    db: Session,
    user: User,
    dataset_id: uuid.UUID,
    *,
    date_from: str | None,
    date_to: str | None,
    country: str | None,
) -> dict:
    dataset = require_dataset(db, user, dataset_id)
    version = require_version(db, dataset)
    frame = load_frame(version, db.connection())
    start, end = _bounds(frame, date_from, date_to)
    current = apply_filters(filter_period(frame, start, end), country=country)
    categories = breakdown(current, "category")
    return json_safe(
        {
            "products": product_table(current),
            "categories": categories,
            "category_available": bool(categories),
            "category_reason": None if categories else "Map a category column to group products.",
            "monthly": monthly_series(current),
        }
    )
