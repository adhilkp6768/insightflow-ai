"""Churn models trained on purchases before an inactivity window.

The label is inferred: a customer with history on or before the cutoff is marked churned
when they have no transaction in the following window. That is not an observed cancellation.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

FEATURES = ["recency_days", "frequency", "monetary", "average_order_value", "distinct_products", "tenure_days"]
SCORE_NOTE = (
    "Customers are ranked by the selected model's score. "
    "The score is not a calibrated probability and is not a campaign conversion rate."
)


def _too_new(valid: pd.DataFrame, cutoff: pd.Timestamp) -> int:
    first_purchase = valid.groupby("customer_id")["invoice_date"].min()
    return int((first_purchase > cutoff).sum())


def _history_table(history: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    grouped = history.groupby("customer_id")
    table = grouped.agg(
        last_purchase=("invoice_date", "max"),
        first_purchase=("invoice_date", "min"),
        frequency=("invoice_id", "nunique"),
        monetary=("revenue", "sum"),
        distinct_products=("stock_code", "nunique"),
    )
    table["recency_days"] = (cutoff - table["last_purchase"]).dt.days.astype(float)
    table["tenure_days"] = (table["last_purchase"] - table["first_purchase"]).dt.days.astype(float)
    table["monetary"] = table["monetary"].astype(float)
    table["frequency"] = table["frequency"].replace(0, 1).astype(float)
    table["average_order_value"] = table["monetary"] / table["frequency"]
    table["distinct_products"] = table["distinct_products"].astype(float)
    return table[FEATURES]


def _scores(model, x_test, y_test) -> dict:
    predicted = model.predict(x_test)
    matrix = confusion_matrix(y_test, predicted, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in matrix.ravel())
    roc_auc = None
    if len(set(y_test)) > 1:
        roc_auc = round(float(roc_auc_score(y_test, model.predict_proba(x_test)[:, 1])), 4)
    return {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "precision": round(float(precision_score(y_test, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predicted, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predicted, zero_division=0)), 4),
        "roc_auc": roc_auc,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def train_churn(frame: pd.DataFrame, inactivity_days: int = 90) -> dict:
    if inactivity_days < 14 or inactivity_days > 365:
        raise ValueError("The inactivity window must be between 14 and 365 days.")
    valid = frame.loc[frame["is_valid"].astype(bool) & frame["customer_id"].notna()].copy()
    if valid.empty:
        return {"sufficient": False, "label_kind": "inferred", "reason": "No valid rows have a customer ID."}
    max_date = valid["invoice_date"].max()
    cutoff = max_date - pd.Timedelta(days=inactivity_days)
    history = valid.loc[valid["invoice_date"] <= cutoff]
    future = valid.loc[valid["invoice_date"] > cutoff]
    unlabeled = _too_new(valid, cutoff)
    if history["customer_id"].nunique() < 40:
        return {
            "sufficient": False,
            "label_kind": "inferred",
            "reason": "Fewer than 40 customers have a purchase on or before the cutoff.",
            "cutoff": cutoff.date().isoformat(),
            "inactivity_days": inactivity_days,
            "unlabeled_customers": unlabeled,
            "score_note": SCORE_NOTE,
        }
    features = _history_table(history, cutoff)
    active_later = set(future["customer_id"].dropna())
    features["churn"] = ~features.index.isin(active_later)
    churned = int(features["churn"].sum())
    retained = int((~features["churn"]).sum())
    if min(churned, retained) < 5:
        return {
            "sufficient": False,
            "label_kind": "inferred",
            "reason": "One class has fewer than five customers, so the metrics would not be meaningful.",
            "class_balance": {"churned": churned, "retained": retained},
            "cutoff": cutoff.date().isoformat(),
            "unlabeled_customers": unlabeled,
            "score_note": SCORE_NOTE,
        }
    x = features[FEATURES]
    y = features["churn"].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=42, stratify=y
    )
    scaler = StandardScaler().fit(x_train)
    train_x = scaler.transform(x_train)
    test_x = scaler.transform(x_test)
    models: list[tuple[str, object]] = [
        ("logistic_regression", LogisticRegression(max_iter=500, class_weight="balanced", random_state=42)),
        (
            "random_forest",
            RandomForestClassifier(
                n_estimators=80, max_depth=8, class_weight="balanced_subsample", random_state=42
            ),
        ),
    ]
    positive = max(int(y_train.sum()), 1)
    negative = max(int((y_train == 0).sum()), 1)
    try:
        from xgboost import XGBClassifier

        models.append(
            (
                "xgboost",
                XGBClassifier(
                    n_estimators=60,
                    max_depth=3,
                    learning_rate=0.1,
                    random_state=42,
                    scale_pos_weight=negative / positive,
                    eval_metric="logloss",
                ),
            )
        )
    except Exception as exc:  # pragma: no cover - dependency is installed in the supported environment
        xgboost_error = str(exc)
    else:
        xgboost_error = None

    results = []
    fitted = []
    for name, model in models:
        model.fit(train_x, y_train)
        score = _scores(model, test_x, y_test)
        score["algorithm"] = name
        results.append(score)
        fitted.append(model)
    ranked = sorted(results, key=lambda item: item["roc_auc"] if item["roc_auc"] is not None else -1, reverse=True)
    selected_name = ranked[0]["algorithm"]
    selected = fitted[results.index(next(item for item in results if item["algorithm"] == selected_name))]
    if selected_name == "logistic_regression":
        raw = [abs(float(value)) for value in selected.coef_[0]]
        method = "absolute logistic coefficient"
    else:
        raw = [float(value) for value in selected.feature_importances_]
        method = f"{selected_name} feature importance"
    total = sum(raw) or 1
    importance = [
        {"feature": feature, "importance": round(value / total, 4)}
        for feature, value in sorted(zip(FEATURES, raw, strict=True), key=lambda item: item[1], reverse=True)
    ]
    probabilities = selected.predict_proba(scaler.transform(x))[:, 1]
    at_risk = (
        features.assign(score=probabilities)
        .sort_values("score", ascending=False)
        .head(25)
    )
    return {
        "sufficient": True,
        "label_kind": "inferred",
        "label_definition": (
            f"A customer is labeled churned when they purchased on or before {cutoff.date().isoformat()} "
            f"and had no transaction in the next {inactivity_days} days. "
            "This is inferred inactivity, not an observed cancellation."
        ),
        "inactivity_days": inactivity_days,
        "cutoff": cutoff.date().isoformat(),
        "feature_cutoff": cutoff.date().isoformat(),
        "customers": int(len(features)),
        "class_balance": {"churned": churned, "retained": retained},
        "models": results,
        "selected_algorithm": selected_name,
        "feature_importance": importance,
        "importance_method": method,
        "shap": None,
        "unlabeled_customers": unlabeled,
        "score_note": SCORE_NOTE,
        "at_risk_preview": [
            {
                "rank": rank,
                "customer_id": str(customer_id),
                "score": round(float(row.score), 4),
            }
            for rank, (customer_id, row) in enumerate(at_risk.iterrows(), start=1)
        ],
        "limitations": [
            item
            for item in [
                "Features use only transactions on or before the cutoff.",
                "Customers whose first purchase is after the cutoff are excluded and are not scored.",
                "The holdout is a stratified random split of customers, not a split of future time.",
                SCORE_NOTE,
                "SHAP values are not computed. The ranking uses the selected model's own importance.",
                xgboost_error,
            ]
            if item
        ],
    }
