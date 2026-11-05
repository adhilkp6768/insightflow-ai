"""Cleaning jobs and the UCI import entry point."""

import time

import pandas as pd

from app.core.config import get_settings
from tests.conftest import register


def _auth(client):
    session = register(client)
    workspace = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    ).json()[0]
    return workspace, session["access_token"]


def test_inline_prepare_records_a_succeeded_job(client):
    workspace, token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(f"/api/v1/workspaces/{workspace['id']}/datasets/sample", headers=headers)
    prepared = client.post(
        f"/api/v1/datasets/{created.json()['id']}/prepare",
        headers=headers,
        json={"drop_exact_duplicates": False},
    )
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["has_processed"] is True
    jobs = client.get(f"/api/v1/workspaces/{workspace['id']}/jobs", headers=headers)
    assert any(item["job_type"] == "prepare" and item["status"] == "succeeded" for item in jobs.json())


def test_queued_prepare_can_finish_before_the_response(client, monkeypatch):
    monkeypatch.setenv("JOBS_INLINE", "false")
    get_settings.cache_clear()

    class Immediate:
        def __init__(self, target, args=(), daemon=None, name=None):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr("app.services.job_runner.threading.Thread", Immediate)
    workspace, token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(f"/api/v1/workspaces/{workspace['id']}/datasets/sample", headers=headers)
    prepared = client.post(
        f"/api/v1/datasets/{created.json()['id']}/prepare",
        headers=headers,
        json={"drop_exact_duplicates": False},
    )
    assert prepared.status_code == 200, prepared.text
    job = prepared.json()["job"]
    status = job["status"]
    for _ in range(40):
        if status in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
        status = client.get(f"/api/v1/jobs/{job['id']}", headers=headers).json()["status"]
    assert status == "succeeded"
    detail = client.get(f"/api/v1/datasets/{created.json()['id']}", headers=headers)
    assert detail.json()["has_processed"] is True
    get_settings.cache_clear()


def test_uci_import_uses_a_local_workbook(client, tmp_path, monkeypatch):
    workbook = tmp_path / "online_retail_II.xlsx"
    pd.DataFrame(
        {
            "Invoice": ["A1"],
            "StockCode": ["S1"],
            "Description": ["Hat"],
            "Quantity": [2],
            "InvoiceDate": ["2024-01-02"],
            "Price": [5.0],
            "Customer ID": [17850],
            "Country": ["United Kingdom"],
        }
    ).to_excel(workbook, index=False)
    monkeypatch.setattr("app.services.uci_data.ensure_uci_workbook", lambda progress=None: workbook)
    workspace, token = _auth(client)
    imported = client.post(
        f"/api/v1/workspaces/{workspace['id']}/datasets/uci",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert imported.status_code == 202, imported.text
    dataset = imported.json()["dataset"]
    assert dataset["source_type"] == "uci"
    assert dataset["row_count"] == 1
    assert dataset["name"] == "Online Retail II"
