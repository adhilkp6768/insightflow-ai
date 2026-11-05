"""Customer segmentation from recency, frequency, and monetary value."""

from __future__ import annotations

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def _customer_table(frame: pd.DataFrame) -> pd.DataFrame:
    valid = frame.loc[frame["is_valid"].astype(bool) & frame["customer_id"].notna()].copy()
    if valid.empty:
        return valid
    snapshot = valid["invoice_date"].max()
    grouped = valid.groupby("customer_id")
    table = grouped.agg(
        last_purchase=("invoice_date", "max"),
        frequency=("invoice_id", "nunique"),
        monetary=("revenue", "sum"),
    )
    missing_invoice = table["frequency"].eq(0)
    if missing_invoice.any():
        table.loc[missing_invoice, "frequency"] = grouped.size().loc[missing_invoice]
    table["recency_days"] = (snapshot - table["last_purchase"]).dt.days.astype(float)
    table["monetary"] = table["monetary"].astype(float)
    table["frequency"] = table["frequency"].astype(float)
    return table


def _label(recency: float, frequency: float, monetary: float, medians: dict[str, float]) -> str:
    valuable = monetary >= medians["monetary"]
    recent = recency <= medians["recency_days"]
    frequent = frequency >= medians["frequency"]
    if valuable and recent:
        return "High-value active"
    if valuable and not recent:
        return "High-value inactive"
    if frequent and recent:
        return "Frequent recent buyers"
    if recent:
        return "Recent lower spend"
    return "Inactive lower spend"


def segment_customers(frame: pd.DataFrame) -> dict:
    table = _customer_table(frame)
    if len(table) < 15:
        return {
            "sufficient": False,
            "reason": f"{len(table)} customers have an ID. At least 15 are required to fit clusters.",
        }
    features = table[["recency_days", "frequency", "monetary"]]
    scaled = StandardScaler().fit_transform(features)
    max_k = min(8, len(table) // 5)
    if max_k < 2:
        return {"sufficient": False, "reason": "There are not enough customers to compare cluster counts."}
    best = None
    for k in range(2, max_k + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = model.fit_predict(scaled)
        score = float(silhouette_score(scaled, labels))
        if best is None or score > best["silhouette"]:
            best = {"k": k, "silhouette": score, "labels": labels, "centers": model.cluster_centers_}
    assert best is not None
    table = table.copy()
    table["cluster"] = best["labels"]
    medians = {
        "recency_days": float(table["recency_days"].median()),
        "frequency": float(table["frequency"].median()),
        "monetary": float(table["monetary"].median()),
    }
    clusters = []
    for cluster_id, part in table.groupby("cluster"):
        recency = float(part["recency_days"].mean())
        frequency = float(part["frequency"].mean())
        monetary = float(part["monetary"].mean())
        clusters.append(
            {
                "id": int(cluster_id),
                "size": int(len(part)),
                "label": _label(recency, frequency, monetary, medians),
                "avg_recency_days": round(recency, 1),
                "avg_frequency": round(frequency, 2),
                "avg_monetary": round(monetary, 2),
                "customer_ids": [str(item) for item in part.index[:50]],
            }
        )
    clusters.sort(key=lambda item: item["avg_monetary"], reverse=True)
    return {
        "sufficient": True,
        "k": int(best["k"]),
        "silhouette": round(float(best["silhouette"]), 4),
        "scaled_features": ["recency_days", "frequency", "monetary"],
        "selection": "Highest silhouette among k=2 through the largest k with at least five customers per cluster.",
        "clusters": clusters,
        "customers": int(len(table)),
    }
