"""Cleaning rules and the documented quality score."""

import pandas as pd

from app.domain.columns import suggest_mapping
from app.ml.evaluation import regression_scores
from app.services.sql_guard import validate_select
from app.utils.preprocessing import clean_transactions
from app.utils.profiling import quality_report


def retail_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Invoice": ["A1", "A2", "C3", "A4"],
            "InvoiceDate": ["2024-01-01", "2024-01-02", "2024-01-03", "bad"],
            "Quantity": [2, -1, -1, 5],
            "Price": [10, 4, 10, 3],
            "Customer ID": ["c1", "c1", "c1", "c1"],
            "Description": ["Mug", "Mug", "Mug", None],
            "Country": ["France", "France", "France", "France"],
        }
    )


def test_revenue_keeps_returns_and_excludes_invalid_rows():
    frame = retail_frame()
    cleaned, decisions = clean_transactions(frame, suggest_mapping(list(frame.columns)), {})
    valid = cleaned.loc[cleaned["is_valid"] == 1]
    assert valid["revenue"].sum() == 20 - 4 - 10
    assert set(valid["transaction_type"]) == {"sale", "return", "cancellation"}
    assert decisions["invalid_rows"] == 1
    assert decisions["raw_file_unchanged"] is True


def test_exact_duplicates_stay_unless_requested():
    frame = retail_frame()
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    mapping = suggest_mapping(list(duplicated.columns))
    kept, kept_decisions = clean_transactions(duplicated, mapping, {})
    removed, removed_decisions = clean_transactions(duplicated, mapping, {"drop_exact_duplicates": True})
    assert len(kept) == len(duplicated)
    assert kept_decisions["exact_duplicates_removed"] == 0
    assert len(removed) == len(duplicated) - 1
    assert removed_decisions["exact_duplicates_removed"] == 1


def test_quality_score_uses_the_documented_weights():
    frame = pd.DataFrame(
        {
            "Invoice": ["A", "A"],
            "InvoiceDate": ["2024-01-01", "2024-01-01"],
            "Quantity": [1, 1],
            "Price": [5, 5],
            "Customer ID": ["c1", "c1"],
        }
    )
    report = quality_report(frame, suggest_mapping(list(frame.columns)))
    assert report["formula"].startswith("100 ×")
    assert report["duplicate_rows"] == 1
    assert report["uniqueness"] == 0.5
    assert report["completeness"] == 1
    assert report["validity"] == 1
    assert report["consistency"] == 1
    assert report["score"] == 90


def test_mape_ignores_zero_actuals():
    scores = regression_scores([0, 10], [5, 12])
    assert scores["mape"] == 20


def test_sql_guard_rejects_writes_and_other_tables():
    table = "ds_" + "a" * 32
    other = "ds_" + "b" * 32
    allowed = validate_select(f"SELECT SUM(revenue) AS value FROM {table}", table)
    assert allowed.startswith("SELECT")
    for statement in (
        f"DROP TABLE {table}",
        f"SELECT * FROM {table}; DROP TABLE {table}",
        f"SELECT * FROM {other}",
        f"DELETE FROM {table}",
    ):
        try:
            validate_select(statement, table)
        except ValueError:
            continue
        raise AssertionError(statement)
