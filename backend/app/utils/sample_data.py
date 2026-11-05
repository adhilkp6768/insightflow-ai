"""Generated retail transactions used to exercise the product without the UCI file.

This is a demonstration fixture. It is not the UCI Online Retail II dataset.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


def build_sample_frame(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = date(2023, 1, 1)
    products = [
        ("A100", "Ceramic mug", "Kitchen"),
        ("B200", "Notebook", "Stationery"),
        ("C300", "Wool scarf", "Apparel"),
        ("D400", "Desk lamp", "Home"),
        ("E500", None, "Home"),
    ]
    countries = ["United Kingdom", "France", "Germany", "Spain"]
    rows: list[dict] = []
    invoice_number = 1000
    for customer_index in range(40):
        last_day = 40 if customer_index >= 30 else 200
        day = 0
        while day <= last_day:
            day += int(rng.integers(10, 18))
            if day > last_day:
                break
            stock, description, category = products[int(rng.integers(0, len(products)))]
            invoice_number += 1
            rows.append(
                {
                    "Invoice": str(invoice_number),
                    "InvoiceDate": (start + timedelta(days=int(day))).isoformat(),
                    "StockCode": stock,
                    "Description": description,
                    "Quantity": int(rng.integers(1, 5)),
                    "Price": float(rng.choice([4.5, 8.0, 15.0, 24.0])),
                    "Customer ID": f"C{customer_index:03d}",
                    "Country": countries[customer_index % len(countries)],
                    "Category": category,
                }
            )
            if customer_index % 9 == 0 and day > 20:
                invoice_number += 1
                rows.append(
                    {
                        "Invoice": str(invoice_number),
                        "InvoiceDate": (start + timedelta(days=int(day))).isoformat(),
                        "StockCode": stock,
                        "Description": description,
                        "Quantity": -1,
                        "Price": 8.0,
                        "Customer ID": f"C{customer_index:03d}",
                        "Country": countries[customer_index % len(countries)],
                        "Category": category,
                    }
                )
    rows.append(dict(rows[0]))
    rows.append(
        {
            "Invoice": "C9000",
            "InvoiceDate": "2023-03-15",
            "StockCode": "A100",
            "Description": "Ceramic mug",
            "Quantity": -1,
            "Price": 15.0,
            "Customer ID": "C001",
            "Country": "France",
            "Category": "Kitchen",
        }
    )
    rows.append(
        {
            "Invoice": "1099",
            "InvoiceDate": "2023-04-02",
            "StockCode": "B200",
            "Description": "Notebook",
            "Quantity": 2,
            "Price": 8.0,
            "Customer ID": None,
            "Country": "Germany",
            "Category": "Stationery",
        }
    )
    rows.append(
        {
            "Invoice": "",
            "InvoiceDate": "not-a-date",
            "StockCode": "Z9",
            "Description": "Broken row",
            "Quantity": 1,
            "Price": 5.0,
            "Customer ID": "C002",
            "Country": "Spain",
            "Category": "Home",
        }
    )
    return pd.DataFrame(rows)
