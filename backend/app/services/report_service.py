"""Build reports from the same calculations as the dashboard."""

from __future__ import annotations

import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Report, User
from app.services.access import record_activity, require_dataset
from app.services.analytics_service import _cohorts, _customer_table
from app.services.frames import data_root, load_frame, require_version
from app.services.metrics import monthly_series, period_summary, product_table, quarterly_series
from app.services.prediction_service import latest_model
from app.services.report_files import write_csv, write_pdf, write_xlsx
from app.utils.json_safe import json_safe

REPORT_TYPES = {
    "monthly_sales": "Monthly sales",
    "quarterly": "Quarterly performance",
    "customer": "Customer analytics",
    "product": "Product analytics",
    "predictive": "Predictive summary",
    "executive": "Executive summary",
}


def _change_sentence(rows: list[dict], label: str) -> str | None:
    if len(rows) < 2 or not rows[-2]["revenue"]:
        return None
    latest, prior = rows[-1], rows[-2]
    change = (latest["revenue"] - prior["revenue"]) / abs(prior["revenue"])
    direction = "higher" if change > 0 else "lower" if change < 0 else "unchanged"
    return (
        f"{latest['period']} {label} is {latest['revenue']:.2f}, {direction} than "
        f"{prior['period']} ({prior['revenue']:.2f}, {change:.1%} change)."
    )


def build_document(frame: pd.DataFrame, report_type: str, dataset_name: str, runs: dict) -> dict:
    summary = period_summary(frame)
    months = monthly_series(frame)
    quarters = quarterly_series(frame)
    products = product_table(frame, limit=10)
    dated = frame.loc[frame["is_valid"], "invoice_date"]
    period = "All cleaned dates"
    if not dated.empty:
        period = f"{dated.min().date().isoformat()} to {dated.max().date().isoformat()}"
    findings = [item for item in (_change_sentence(months, "revenue"), _change_sentence(quarters, "revenue")) if item]
    if products:
        findings.append(
            f"{products[0]['description'] or products[0]['stock_code']} leads product revenue at {products[0]['revenue']:.2f}."
        )
    risks = []
    recommendations = []
    valid = frame.loc[frame["is_valid"] & frame["customer_id"].notna()]
    inactive_count = 0
    if not valid.empty:
        snapshot = valid["invoice_date"].max()
        customers = _customer_table(valid, snapshot)
        inactive_count = int((customers["recency_days"] > 90).sum()) if not customers.empty else 0
        if inactive_count:
            risks.append(f"{inactive_count} customers have no purchase in the 90 days before {snapshot.date().isoformat()}.")
            recommendations.append(
                "Review the inactive customer list before treating it as a campaign audience. "
                "The count is calculated from purchase dates, not from a churn model."
            )
    if report_type == "predictive":
        for model_type, run in runs.items():
            if run is None or not run.summary.get("sufficient"):
                findings.append(f"No usable {model_type} model is saved, so this report does not invent one.")
            elif model_type == "forecast":
                state = "reliable" if run.summary.get("reliable") else "not reliable"
                findings.append(f"The saved forecast is {state}. Horizons: {run.summary.get('horizons')}.")
            elif model_type == "churn":
                findings.append(run.summary.get("label_definition") or "A churn model is saved.")
            else:
                findings.append(
                    f"Segmentation selected k={run.summary.get('k')} with silhouette {run.summary.get('silhouette')}."
                )
    if not findings:
        findings.append("The cleaned dataset does not contain enough periods for a comparison.")
    if summary["profit"] is None:
        risks.append(summary["profit_reason"])
    table = {"title": "Monthly revenue", "columns": ["Period", "Revenue", "Orders"], "rows": []}
    source = months
    if report_type == "quarterly":
        source = quarters
        table["title"] = "Quarterly revenue"
    elif report_type == "product":
        table = {
            "title": "Products",
            "columns": ["Product", "Revenue", "Units sold", "Units returned"],
            "rows": [
                [item["description"] or item["stock_code"], item["revenue"], item["units_sold"], item["units_returned"]]
                for item in products
            ],
        }
        source = []
    elif report_type == "customer":
        table = {
            "title": "Cohorts",
            "columns": ["Cohort", "Customers", "Month 1 retention"],
            "rows": [
                [item["cohort"], item["customers"], item["retention"][1] if len(item["retention"]) > 1 else None]
                for item in _cohorts(frame)
            ],
        }
        source = []
    if source:
        table["rows"] = [[item["period"], item["revenue"], item["orders"]] for item in source]
    kpis = [
        {"label": "Revenue", "value": f"{summary['revenue']:.2f}"},
        {"label": "Orders", "value": str(summary["orders"])},
        {"label": "Customers", "value": str(summary["customers"])},
        {
            "label": "Average order value",
            "value": "—" if summary["average_order_value"] is None else f"{summary['average_order_value']:.2f}",
        },
    ]
    if summary["profit"] is not None:
        kpis.append({"label": "Profit", "value": f"{summary['profit']:.2f}"})
    return {
        "title": f"{REPORT_TYPES[report_type]} — {dataset_name}",
        "period": period,
        "kpis": kpis,
        "findings": findings,
        "risks": risks or ["No concentration risk was calculated from the current rows."],
        "recommendations": recommendations or ["No recommendation is attached because no supporting pattern was calculated."],
        "table": table,
        "notes": [
            "Figures are calculated from the cleaned dataset. Invalid rows are excluded.",
            "Returns and cancellations remain in revenue.",
            "Recommendations are interpretations of those figures.",
        ],
        "inactive_customers": inactive_count,
    }


def create_report(db: Session, user: User, dataset_id: uuid.UUID, report_type: str) -> dict:
    if report_type not in REPORT_TYPES:
        raise ValueError("Unknown report type")
    dataset = require_dataset(db, user, dataset_id, write=True)
    version = require_version(db, dataset)
    frame = load_frame(version, db.connection())
    runs = {model_type: latest_model(db, dataset.id, model_type) for model_type in ("churn", "segments", "forecast")}
    document = build_document(frame, report_type, dataset.name, runs)
    report = Report(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.id,
        version_id=version.id,
        report_type=report_type,
        title=document["title"][:160],
        status="ready",
        summary=json_safe(document),
        pdf_path="",
        xlsx_path="",
        csv_path="",
        created_by=user.id,
    )
    db.add(report)
    db.flush()
    directory = data_root() / "reports" / report.id.hex
    directory.mkdir(parents=True, exist_ok=True)
    pdf_path = directory / "report.pdf"
    xlsx_path = directory / "report.xlsx"
    csv_path = directory / "report.csv"
    write_pdf(pdf_path, document)
    write_xlsx(xlsx_path, document)
    write_csv(csv_path, document)
    report.pdf_path = str(pdf_path)
    report.xlsx_path = str(xlsx_path)
    report.csv_path = str(csv_path)
    record_activity(
        db,
        workspace_id=dataset.workspace_id,
        user=user,
        action="report.created",
        resource_type="report",
        resource_id=str(report.id),
        context={"report_type": report_type, "title": report.title},
    )
    db.commit()
    db.refresh(report)
    return serialize_report(report)


def serialize_report(report: Report) -> dict:
    return {
        "id": str(report.id),
        "dataset_id": str(report.dataset_id),
        "report_type": report.report_type,
        "title": report.title,
        "status": report.status,
        "created_at": report.created_at.isoformat(),
        "summary": report.summary,
    }


def list_reports(db: Session, user: User, workspace_id: uuid.UUID) -> list[dict]:
    from app.services.access import require_workspace

    require_workspace(db, user, workspace_id)
    rows = db.scalars(
        select(Report).where(Report.workspace_id == workspace_id).order_by(Report.created_at.desc())
    ).all()
    return [serialize_report(report) for report in rows]


def get_report_file(db: Session, user: User, report_id: uuid.UUID, file_format: str):
    from pathlib import Path

    from app.services.access import require_workspace

    report = db.get(Report, report_id)
    if report is None:
        from app.core.exceptions import AppError

        raise AppError("not_found", "Report not found.", 404)
    require_workspace(db, user, report.workspace_id)
    path = {"pdf": report.pdf_path, "xlsx": report.xlsx_path, "csv": report.csv_path}.get(file_format)
    if path is None:
        from app.core.exceptions import AppError

        raise AppError("invalid_format", "Choose pdf, xlsx, or csv.", 422)
    file_path = Path(path).resolve()
    file_path.relative_to(data_root())
    return file_path, f"{report.report_type}.{file_format}"
