"""Answer questions from query results. The model may choose a plan, never a number."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import AssistantConversation, AssistantMessage, User
from app.services.access import require_dataset
from app.services.frames import require_version
from app.services.prediction_service import latest_model
from app.services.sql_guard import validate_select, validate_table_name
from app.utils.json_safe import json_safe

OPERATIONS = {"kpi", "breakdown", "timeseries", "forecast", "churn", "segments", "unsupported"}


class Plan(BaseModel):
    operation: str
    kind: str
    metric: str | None = None
    dimension: str | None = None


def plan_question(question: str) -> dict[str, Any]:
    text_value = " ".join(question.lower().split())
    blocked = ("drop table", "delete from", "insert into", "alter table", "update ", ";")
    if any(token in text_value for token in blocked):
        return {"operation": "unsupported", "kind": "error"}
    if any(token in text_value for token in ("forecast", "next month", "next quarter", "predict revenue")):
        return {"operation": "forecast", "kind": "prediction"}
    if "churn" in text_value or "likely to leave" in text_value:
        return {"operation": "churn", "kind": "prediction"}
    if "segment" in text_value or "cluster" in text_value:
        return {"operation": "segments", "kind": "prediction"}
    interpretive = any(token in text_value for token in ("why", "recommend", "should we"))
    if "product" in text_value and any(token in text_value for token in ("top", "best", "highest", "which")):
        plan = {"operation": "breakdown", "dimension": "product", "kind": "data_backed"}
    elif "categor" in text_value:
        plan = {"operation": "breakdown", "dimension": "category", "kind": "data_backed"}
    elif any(token in text_value for token in ("country", "region")):
        plan = {"operation": "breakdown", "dimension": "country", "kind": "data_backed"}
    elif any(token in text_value for token in ("trend", "over time", "monthly", "each month")):
        plan = {"operation": "timeseries", "kind": "data_backed"}
    elif "average order" in text_value or "aov" in text_value:
        plan = {"operation": "kpi", "metric": "aov", "kind": "data_backed"}
    elif any(token in text_value for token in ("how many customer", "number of customer", "customer count")):
        plan = {"operation": "kpi", "metric": "customers", "kind": "data_backed"}
    elif "order" in text_value and "revenue" not in text_value:
        plan = {"operation": "kpi", "metric": "orders", "kind": "data_backed"}
    elif any(token in text_value for token in ("revenue", "sales", "spend")):
        plan = {"operation": "kpi", "metric": "revenue", "kind": "data_backed"}
    else:
        return {"operation": "unsupported", "kind": "error"}
    if interpretive:
        plan["kind"] = "interpretation"
    return plan


def maybe_llm_plan(question: str) -> tuple[dict[str, Any] | None, str | None]:
    settings = get_settings()
    if not settings.insightflow_llm_api_key:
        return None, None
    schema = (
        '{"operation":"kpi|breakdown|timeseries|forecast|churn|segments|unsupported",'
        '"kind":"data_backed|prediction|interpretation|error","metric":"revenue|orders|customers|aov|null",'
        '"dimension":"country|product|category|null"}'
    )
    try:
        response = httpx.post(
            f"{settings.insightflow_llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.insightflow_llm_api_key}"},
            json={
                "model": settings.insightflow_llm_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Choose an analytical plan. Return only JSON matching "
                            f"{schema}. Do not include numbers, SQL, or code."
                        ),
                    },
                    {"role": "user", "content": question[:2000]},
                ],
            },
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        plan = Plan.model_validate_json(content)
        if plan.operation not in OPERATIONS:
            raise ValidationError.from_exception_data("Plan", [])
        return plan.model_dump(), None
    except Exception:
        return None, "The language model did not return a usable plan, so the fixed interpreter was used."


def month_expression(dialect: str) -> str:
    if dialect == "postgresql":
        return "substring(invoice_date from 1 for 7)"
    return "substr(invoice_date, 1, 7)"


def compile_plan(plan: dict, table: str, date_from: str | None, date_to: str | None, dialect: str) -> tuple[str, dict]:
    validate_table_name(table)
    where = ["is_valid = 1"]
    params: dict[str, Any] = {}
    if date_from:
        where.append("invoice_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where.append("invoice_date <= :date_to")
        params["date_to"] = date_to
    clause = " AND ".join(where)
    operation = plan["operation"]
    if operation == "kpi" and plan.get("metric") == "orders":
        sql = f"SELECT COUNT(DISTINCT invoice_id) AS value FROM {table} WHERE {clause} AND transaction_type = 'sale'"
    elif operation == "kpi" and plan.get("metric") == "customers":
        sql = f"SELECT COUNT(DISTINCT customer_id) AS value FROM {table} WHERE {clause} AND customer_id IS NOT NULL"
    elif operation == "kpi" and plan.get("metric") == "aov":
        sql = (
            f"SELECT CASE WHEN COUNT(DISTINCT invoice_id) = 0 THEN NULL ELSE "
            f"SUM(revenue) * 1.0 / COUNT(DISTINCT invoice_id) END AS value "
            f"FROM {table} WHERE {clause} AND transaction_type = 'sale'"
        )
    elif operation == "kpi":
        sql = f"SELECT COALESCE(SUM(revenue), 0) AS value FROM {table} WHERE {clause}"
    elif operation == "breakdown":
        column = {"country": "country", "product": "description", "category": "category"}[plan["dimension"]]
        sql = (
            f"SELECT COALESCE({column}, 'Unknown') AS key, SUM(revenue) AS revenue "
            f"FROM {table} WHERE {clause} GROUP BY 1 ORDER BY revenue DESC LIMIT :row_limit"
        )
        params["row_limit"] = 10
    elif operation == "timeseries":
        sql = (
            f"SELECT {month_expression(dialect)} AS period, SUM(revenue) AS revenue "
            f"FROM {table} WHERE {clause} GROUP BY 1 ORDER BY 1"
        )
    else:
        raise ValueError("This question does not compile to a dataset query.")
    return validate_select(sql, table), params


def execute_select(sql: str, params: dict, table: str, connection) -> list[dict]:
    statement = validate_select(sql, table)
    settings = get_settings()
    if connection.dialect.name == "postgresql":
        connection.execute(text(f"SET LOCAL statement_timeout = {int(settings.assistant_timeout_ms)}"))
    result = connection.execute(text(statement), params)
    rows = [dict(row._mapping) for row in result.fetchmany(settings.assistant_row_limit)]
    return json_safe(rows)


def _money(value: object) -> str:
    if value is None:
        return "not available"
    return f"{float(value):,.2f}"


def _answer_from_rows(plan: dict, rows: list[dict], period: str) -> tuple[str, dict | None]:
    if plan["operation"] == "kpi":
        value = rows[0]["value"] if rows else None
        label = {"revenue": "Revenue", "orders": "Orders", "customers": "Customers", "aov": "Average order value"}.get(
            plan.get("metric") or "revenue", "Value"
        )
        number = _money(value) if plan.get("metric") in {None, "revenue", "aov"} else f"{int(value or 0):,}"
        text_value = f"{label} for {period} is {number}. This figure is calculated from the cleaned dataset."
        chart = None
    elif plan["operation"] == "breakdown":
        if not rows:
            return f"No rows match {period}.", None
        top = rows[0]
        text_value = (
            f"The highest {plan['dimension']} by revenue in {period} is {top['key']} "
            f"at {_money(top['revenue'])}."
        )
        chart = {"type": "bar", "x": "key", "y": "revenue", "data": rows}
    else:
        if not rows:
            return f"No rows match {period}.", None
        last = rows[-1]
        text_value = f"The latest month in {period} is {last['period']} with revenue {_money(last['revenue'])}."
        chart = {"type": "line", "x": "period", "y": "revenue", "data": rows}
    if plan["kind"] == "interpretation" and rows:
        text_value += " This is an interpretation of that calculated result, not a separate measurement."
        if plan["operation"] == "breakdown" and rows[0].get("revenue") not in (None, 0):
            total = sum(float(row["revenue"] or 0) for row in rows)
            if total:
                share = float(rows[0]["revenue"]) / total
                text_value += f" It accounts for {share:.0%} of the returned groups."
    return text_value, chart


def _prediction_answer(db: Session, dataset_id: uuid.UUID, operation: str) -> tuple[str, dict | None]:
    model_type = {"forecast": "forecast", "churn": "churn", "segments": "segments"}[operation]
    run = latest_model(db, dataset_id, model_type)
    if run is None or not run.summary.get("sufficient"):
        reason = None if run is None else run.summary.get("reason")
        detail = f" {reason}" if reason else ""
        return (
            f"No usable {model_type} result is saved for this dataset.{detail} "
            "I will not estimate a number without that calculation.",
            None,
        )
    result = run.summary
    if model_type == "forecast":
        reliable = "marked reliable" if result.get("reliable") else "not marked reliable"
        horizons = ", ".join(str(item) for item in result.get("horizons") or []) or "none"
        text_value = (
            f"The saved forecast is {reliable}. Available horizons: {horizons} days. "
            "The chart uses the saved holdout, not a new estimate."
        )
        return text_value, {
            "type": "line",
            "x": "date",
            "y": "actual",
            "y2": "model",
            "data": result.get("comparison") or [],
        }
    if model_type == "churn":
        selected = next(
            (item for item in result.get("models", []) if item.get("algorithm") == result.get("selected_algorithm")),
            None,
        )
        if selected is None:
            return "A churn run is saved, but it has no selected model.", None
        unlabeled = result.get("unlabeled_customers")
        excluded = f" {unlabeled} customers were too new to score." if isinstance(unlabeled, int) else ""
        return (
            f"The saved churn label is inferred. {result.get('label_definition')} "
            f"The selected {selected['algorithm']} model has ROC-AUC {selected.get('roc_auc')} "
            f"and F1 {selected.get('f1')} on its holdout.{excluded} "
            f"{result.get('score_note') or 'The customer list is a rank, not a calibrated probability.'}",
            None,
        )
    clusters = result.get("clusters") or []
    if not clusters:
        return "A segmentation run is saved, but it has no clusters.", None
    largest = max(clusters, key=lambda item: item["size"])
    return (
        f"The saved segmentation uses k={result.get('k')} with silhouette {result.get('silhouette')}. "
        f"The largest cluster is {largest['label']} with {largest['size']} customers.",
        {"type": "bar", "x": "label", "y": "size", "data": clusters},
    )


def answer_question(
    db: Session,
    user: User,
    *,
    dataset_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    cleaned = " ".join(question.split())
    if not cleaned:
        raise AppError("invalid_question", "Enter a question.", 422)
    if len(cleaned) > 2000:
        raise AppError("invalid_question", "Questions are limited to 2000 characters.", 422)
    dataset = require_dataset(db, user, dataset_id)
    version = require_version(db, dataset)
    if conversation_id is None:
        conversation = AssistantConversation(
            workspace_id=dataset.workspace_id,
            dataset_id=dataset.id,
            created_by=user.id,
        )
        db.add(conversation)
        db.flush()
    else:
        conversation = db.get(AssistantConversation, conversation_id)
        if conversation is None or conversation.dataset_id != dataset.id or conversation.created_by != user.id:
            raise AppError("not_found", "Conversation not found.", 404)
    rule_plan = plan_question(cleaned)
    llm_plan, llm_note = maybe_llm_plan(cleaned)
    plan = llm_plan or rule_plan
    if plan["operation"] == "unsupported":
        plan = rule_plan
    limitations = [llm_note] if llm_note else []
    chart = None
    rows: list[dict] = []
    if plan["operation"] in {"forecast", "churn", "segments"}:
        text_value, chart = _prediction_answer(db, dataset.id, plan["operation"])
        kind = "prediction"
    elif plan["operation"] == "unsupported":
        text_value = (
            "I can answer revenue, orders, customers, average order value, trends, products, regions, "
            "and saved predictions. I don't have a grounded result for this question."
        )
        kind = "error"
    else:
        connection = db.connection()
        sql, params = compile_plan(plan, version.table_name or "", date_from, date_to, connection.dialect.name)
        rows = execute_select(sql, params, version.table_name or "", connection)
        period = f"{date_from or 'the start'} to {date_to or 'the end'}"
        text_value, chart = _answer_from_rows(plan, rows, period)
        kind = "interpretation" if plan.get("kind") == "interpretation" else "data_backed"
        limitations.append("The number comes from a read-only query on the selected cleaned dataset.")
    message = AssistantMessage(
        conversation_id=conversation.id,
        question=cleaned,
        answer_kind=kind,
        answer_text=text_value,
        payload=json_safe({"rows": rows, "chart": chart, "limitations": [item for item in limitations if item]}),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return {
        "conversation_id": str(conversation.id),
        "message": {
            "id": str(message.id),
            "question": message.question,
            "answer_kind": message.answer_kind,
            "text": message.answer_text,
            "rows": message.payload.get("rows", []),
            "chart": message.payload.get("chart"),
            "limitations": message.payload.get("limitations", []),
        },
    }
