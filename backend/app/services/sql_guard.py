"""Guards for analytical SQL generated inside the application."""

from __future__ import annotations

import re

TABLE_NAME = re.compile(r"^ds_[0-9a-f]{32}$")
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|copy|grant|revoke|create|replace|truncate|into|vacuum)\b",
    re.IGNORECASE,
)


def validate_table_name(table: str) -> str:
    if not TABLE_NAME.fullmatch(table):
        raise ValueError("The dataset table is not authorized.")
    return table


def validate_select(sql: str, table: str) -> str:
    statement = sql.strip().rstrip(";")
    if not statement or ";" in statement:
        raise ValueError("Only one read-only statement is allowed.")
    if not re.match(r"(?is)^(select|with)\b", statement):
        raise ValueError("Only a SELECT query is allowed.")
    if FORBIDDEN.search(statement):
        raise ValueError("That statement is not allowed.")
    if "--" in statement or "/*" in statement:
        raise ValueError("Comments are not allowed.")
    referenced = set(re.findall(r"\bds_[0-9a-f]{32}\b", statement))
    if referenced != {validate_table_name(table)}:
        raise ValueError("The query must use only the selected dataset.")
    return statement
