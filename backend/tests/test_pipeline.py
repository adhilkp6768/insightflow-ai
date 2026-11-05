"""Dataset pipeline, analytics, models, assistant, and reports."""

import uuid

import pandas as pd

from app.domain.columns import suggest_mapping
from app.ml.churn_model import train_churn
from app.ml.forecasting_model import forecast_revenue
from app.services.metrics import period_summary
from app.utils.preprocessing import clean_transactions
from app.utils.sample_data import build_sample_frame
from tests.conftest import register


def _auth(client) -> tuple[dict, str]:
    session = register(client)
    workspace = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    ).json()[0]
    return workspace, session["access_token"]


def _ready(client, token: str, workspace_id: str) -> dict:
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/datasets/sample",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201, created.text
    dataset = created.json()
    prepared = client.post(
        f"/api/v1/datasets/{dataset['id']}/prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"drop_exact_duplicates": False},
    )
    assert prepared.status_code == 200, prepared.text
    return prepared.json()


def test_sample_revenue_matches_the_cleaning_rules(client):
    workspace, token = _auth(client)
    dataset = _ready(client, token, workspace["id"])
    sales = client.get(
        f"/api/v1/datasets/{dataset['id']}/analytics/sales",
        headers={"Authorization": f"Bearer {token}"},
        params={"date_from": dataset["min_date"], "date_to": dataset["max_date"]},
    )
    assert sales.status_code == 200, sales.text
    frame = build_sample_frame()
    cleaned, _ = clean_transactions(frame, suggest_mapping(list(frame.columns)), {})
    cleaned["invoice_date"] = pd.to_datetime(cleaned["invoice_date"])
    cleaned["is_valid"] = cleaned["is_valid"].astype(bool)
    expected = period_summary(cleaned)["revenue"]
    assert sales.json()["kpis"]["revenue"]["value"] == expected
    assert sales.json()["definitions"]["revenue"].startswith("Sum of quantity")


def test_upload_preview_and_other_user_cannot_see_it(client):
    workspace, token = _auth(client)
    csv_bytes = b"Invoice,InvoiceDate,Quantity,Price,Customer ID\nA1,2024-01-01,2,10,c1\n"
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace['id']}/datasets",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("shop.csv", csv_bytes, "text/csv")},
        data={"name": "Shop"},
    )
    assert uploaded.status_code == 201, uploaded.text
    dataset_id = uploaded.json()["id"]
    preview = client.get(
        f"/api/v1/datasets/{dataset_id}/preview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert preview.status_code == 200
    assert preview.json()["total"] == 1
    other = register(client, email="grace@example.com", full_name="Grace Hopper")
    hidden = client.get(
        f"/api/v1/datasets/{dataset_id}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert hidden.status_code == 404


def test_viewer_cannot_upload(client, db_session):
    workspace, _token = _auth(client)
    viewer = register(client, email="view@example.com", full_name="View User")
    from sqlalchemy import select

    from app.models import User, WorkspaceMembership

    user = db_session.scalar(select(User).where(User.email == "view@example.com"))
    db_session.add(
        WorkspaceMembership(workspace_id=uuid.UUID(workspace["id"]), user_id=user.id, role="viewer")
    )
    db_session.commit()
    denied = client.post(
        f"/api/v1/workspaces/{workspace['id']}/datasets/sample",
        headers={"Authorization": f"Bearer {viewer['access_token']}"},
    )
    assert denied.status_code == 403


def test_models_mark_inferred_churn_and_forecast_limits():
    frame = build_sample_frame()
    cleaned, _ = clean_transactions(frame, suggest_mapping(list(frame.columns)), {})
    cleaned["invoice_date"] = pd.to_datetime(cleaned["invoice_date"])
    cleaned["is_valid"] = cleaned["is_valid"].astype(bool)
    churn = train_churn(cleaned, 90)
    assert churn["sufficient"] is True
    assert churn["label_kind"] == "inferred"
    assert "not an observed cancellation" in churn["label_definition"]
    assert isinstance(churn["unlabeled_customers"], int)
    assert "not a calibrated probability" in churn["score_note"]
    assert churn["at_risk_preview"][0]["rank"] == 1
    assert {item["algorithm"] for item in churn["models"]} >= {"logistic_regression", "random_forest", "xgboost"}
    forecast = forecast_revenue(cleaned)
    assert forecast["sufficient"] is True
    assert 30 in forecast["horizons"]
    assert forecast["holdout_days"] < forecast["history_days"]


def test_assistant_uses_the_query_and_rejects_sql(client):
    workspace, token = _auth(client)
    dataset = _ready(client, token, workspace["id"])
    headers = {"Authorization": f"Bearer {token}"}
    sales = client.get(
        f"/api/v1/datasets/{dataset['id']}/analytics/sales",
        headers=headers,
        params={"date_from": dataset["min_date"], "date_to": dataset["max_date"]},
    ).json()
    answer = client.post(
        "/api/v1/assistant/messages",
        headers=headers,
        json={
            "dataset_id": dataset["id"],
            "question": "What is total revenue?",
            "date_from": dataset["min_date"],
            "date_to": dataset["max_date"],
        },
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()["message"]
    assert body["answer_kind"] == "data_backed"
    assert f"{sales['kpis']['revenue']['value']:,.2f}" in body["text"]
    blocked = client.post(
        "/api/v1/assistant/messages",
        headers=headers,
        json={"dataset_id": dataset["id"], "question": "What is revenue? DROP TABLE users"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["message"]["answer_kind"] == "error"


def test_report_downloads_pdf(client):
    workspace, token = _auth(client)
    dataset = _ready(client, token, workspace["id"])
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/reports",
        headers=headers,
        json={"dataset_id": dataset["id"], "report_type": "executive"},
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]
    download = client.get(f"/api/v1/reports/{report_id}/download", headers=headers, params={"file_format": "pdf"})
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
    sheet = client.get(f"/api/v1/reports/{report_id}/download", headers=headers, params={"file_format": "csv"})
    assert sheet.status_code == 200
    assert b"Period" in sheet.content or b"Product" in sheet.content or b"Cohort" in sheet.content
