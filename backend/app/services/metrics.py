"""KPI calculations shared by the dashboard, assistant, and reports."""

from __future__ import annotations

import pandas as pd


def _valid(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.loc[frame["is_valid"].astype(bool)].copy()


def _number(value: float) -> float:
    return round(float(value), 2)


def _growth(current: float, previous: float | None) -> float | None:
    if previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous), 4)


def period_summary(frame: pd.DataFrame) -> dict:
    valid = _valid(frame)
    sales = valid.loc[valid["transaction_type"] == "sale"] if not valid.empty else valid
    revenue = 0.0 if valid.empty else float(pd.to_numeric(valid["revenue"], errors="coerce").fillna(0).sum())
    sale_revenue = 0.0 if sales.empty else float(pd.to_numeric(sales["revenue"], errors="coerce").fillna(0).sum())
    orders = 0 if sales.empty else int(sales["invoice_id"].dropna().nunique())
    if not sales.empty and sales["invoice_id"].dropna().empty:
        orders = int(len(sales))
    customers = 0 if valid.empty else int(valid["customer_id"].dropna().nunique())
    average_order_value = None if orders == 0 else sale_revenue / orders
    profit = None
    profit_reason = "Map a unit cost column to calculate profit."
    if not valid.empty and valid["unit_cost"].notna().any():
        cost = pd.to_numeric(valid["unit_cost"], errors="coerce")
        price = pd.to_numeric(valid["unit_price"], errors="coerce")
        quantity = pd.to_numeric(valid["quantity"], errors="coerce")
        covered = cost.notna() & price.notna() & quantity.notna()
        profit = float(((price - cost) * quantity).where(covered, 0).sum())
        coverage = float(covered.mean()) if len(covered) else 0
        profit_reason = f"Profit uses rows with a unit cost ({coverage:.0%} of valid rows)."
    return {
        "revenue": _number(revenue),
        "orders": orders,
        "customers": customers,
        "average_order_value": None if average_order_value is None else _number(average_order_value),
        "sale_revenue": _number(sale_revenue),
        "profit": None if profit is None else _number(profit),
        "profit_reason": profit_reason,
    }


def with_growth(current: dict, previous: dict | None) -> dict:
    previous = previous or {}

    def metric(name: str, reason: str | None = None) -> dict:
        value = current.get(name)
        prior = previous.get(name)
        growth = None if value is None or prior is None else _growth(float(value), float(prior))
        payload = {"value": value, "previous": prior, "growth": growth}
        if reason:
            payload["reason"] = reason
        return payload

    return {
        "revenue": metric("revenue"),
        "orders": metric("orders"),
        "customers": metric("customers"),
        "average_order_value": metric("average_order_value"),
        "profit": metric("profit", current.get("profit_reason")),
    }


def definitions(frame: pd.DataFrame) -> dict[str, str]:
    orders = "Distinct invoices whose transaction type is sale."
    if not frame.empty and frame["invoice_id"].dropna().empty:
        orders = "Sale rows, because no invoice column is mapped."
    return {
        "revenue": "Sum of quantity × unit price for valid rows, including returns and cancellations.",
        "orders": orders,
        "customers": "Distinct customer IDs on valid rows. Blank customer IDs are excluded.",
        "average_order_value": "Sale revenue divided by sale invoices.",
        "profit": "Sum of (unit price − unit cost) × quantity where unit cost is present.",
    }


def _grouped_period(frame: pd.DataFrame, freq: str) -> list[dict]:
    valid = _valid(frame)
    if valid.empty:
        return []
    periods = valid["invoice_date"].dt.to_period(freq)
    rows = []
    for period, part in valid.groupby(periods, sort=True):
        summary = period_summary(part)
        rows.append(
            {
                "period": str(period),
                "revenue": summary["revenue"],
                "orders": summary["orders"],
                "customers": summary["customers"],
            }
        )
    return rows


def monthly_series(frame: pd.DataFrame) -> list[dict]:
    return _grouped_period(frame, "M")


def quarterly_series(frame: pd.DataFrame) -> list[dict]:
    return _grouped_period(frame, "Q")


def weekday_series(frame: pd.DataFrame) -> list[dict]:
    valid = _valid(frame)
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if valid.empty:
        return [{"weekday": name, "revenue": 0} for name in names]
    totals = valid.groupby(valid["invoice_date"].dt.day_of_week)["revenue"].sum()
    return [{"weekday": names[index], "revenue": _number(float(totals.get(index, 0)))} for index in range(7)]


def revenue_distribution(frame: pd.DataFrame) -> list[dict]:
    import numpy as np

    valid = _valid(frame)
    sales = valid.loc[valid["transaction_type"] == "sale"] if not valid.empty else valid
    if sales.empty:
        return []
    values = pd.to_numeric(sales["revenue"], errors="coerce").dropna()
    if values.empty:
        return []
    counts, edges = np.histogram(values, bins=min(8, max(1, int(values.nunique()))))
    rows = []
    for index, count in enumerate(counts):
        rows.append({"from": round(float(edges[index]), 2), "to": round(float(edges[index + 1]), 2), "count": int(count)})
    return rows


def breakdown(frame: pd.DataFrame, dimension: str, limit: int = 12) -> list[dict]:
    valid = _valid(frame)
    if valid.empty:
        return []
    if dimension == "country":
        key = valid["country"].fillna("Unknown")
    elif dimension == "category":
        if valid["category"].dropna().empty:
            return []
        key = valid["category"].fillna("Uncategorized")
    else:
        description = valid["description"].fillna("")
        stock = valid["stock_code"].fillna("")
        key = description.where(description != "", stock).where(
            description.where(description != "", stock) != "", "Unnamed product"
        )
    total = float(pd.to_numeric(valid["revenue"], errors="coerce").fillna(0).sum())
    grouped = valid.assign(_key=key, _revenue=pd.to_numeric(valid["revenue"], errors="coerce").fillna(0))
    table = grouped.groupby("_key", dropna=False).agg(
        revenue=("_revenue", "sum"),
        orders=("_key", "size"),
    )
    table = table.sort_values("revenue", ascending=False).head(limit)
    rows = []
    for name, row in table.iterrows():
        revenue = float(row["revenue"])
        rows.append(
            {
                "key": str(name),
                "revenue": _number(revenue),
                "rows": int(row["orders"]),
                "share": None if total == 0 else round(revenue / total, 4),
            }
        )
    return rows


def product_table(frame: pd.DataFrame, limit: int = 50) -> list[dict]:
    valid = _valid(frame)
    if valid.empty:
        return []
    work = valid.copy()
    work["stock_code"] = work["stock_code"].fillna("Unknown")
    work["description"] = work["description"].fillna("")
    rows = []
    for (stock, description), part in work.groupby(["stock_code", "description"], dropna=False):
        sales = part.loc[part["transaction_type"] == "sale"]
        returns = part.loc[part["transaction_type"].isin(["return", "cancellation"])]
        revenue = float(pd.to_numeric(part["revenue"], errors="coerce").fillna(0).sum())
        units_sold = float(pd.to_numeric(sales["quantity"], errors="coerce").fillna(0).sum()) if not sales.empty else 0
        units_returned = float(pd.to_numeric(returns["quantity"], errors="coerce").fillna(0).abs().sum()) if not returns.empty else 0
        rows.append(
            {
                "stock_code": str(stock),
                "description": str(description) or None,
                "revenue": _number(revenue),
                "units_sold": round(units_sold, 2),
                "units_returned": round(units_returned, 2),
            }
        )
    rows.sort(key=lambda item: item["revenue"], reverse=True)
    total = sum(item["revenue"] for item in rows)
    for item in rows:
        item["share"] = None if total == 0 else round(item["revenue"] / total, 4)
    return rows[:limit]


def filter_period(frame: pd.DataFrame, date_from: str | None, date_to: str | None) -> pd.DataFrame:
    if frame.empty:
        return frame
    selected = frame
    if date_from:
        selected = selected.loc[selected["invoice_date"] >= pd.Timestamp(date_from)]
    if date_to:
        selected = selected.loc[selected["invoice_date"] <= pd.Timestamp(date_to)]
    return selected.copy()


def previous_bounds(date_from: str, date_to: str) -> tuple[str, str]:
    start = pd.Timestamp(date_from)
    end = pd.Timestamp(date_to)
    length = max((end - start).days, 0)
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=length)
    return prev_start.date().isoformat(), prev_end.date().isoformat()
