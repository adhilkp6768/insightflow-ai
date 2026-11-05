"""PDF, Excel, and CSV renderers for a calculated report."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table


def _bars(rows: list[list], label_index: int = 0, value_index: int = 1) -> Drawing:
    drawing = Drawing(460, 140)
    numeric = []
    for row in rows[:6]:
        try:
            numeric.append(abs(float(row[value_index])))
        except (TypeError, ValueError):
            numeric.append(0)
    maximum = max(numeric) if numeric else 1
    maximum = maximum or 1
    for index, row in enumerate(rows[:6]):
        width = 280 * (numeric[index] / maximum)
        y = 110 - index * 20
        drawing.add(Rect(120, y, width, 12, fillColor=colors.HexColor("#1d4ed8"), strokeColor=None))
        drawing.add(String(0, y, str(row[label_index])[:22], fontSize=8))
    return drawing


def write_pdf(path: Path, report: dict) -> None:
    styles = getSampleStyleSheet()
    story = [
        Paragraph(report["title"], styles["Title"]),
        Paragraph(report["period"], styles["Normal"]),
        Spacer(1, 12),
    ]
    kpi_rows = [["Measure", "Value"]] + [[item["label"], item["value"]] for item in report["kpis"]]
    story.append(Table(kpi_rows, hAlign="LEFT"))
    story.append(Spacer(1, 12))
    for heading, key in (
        ("Findings", "findings"),
        ("Risks", "risks"),
        ("Recommendations (interpretation)", "recommendations"),
    ):
        story.append(Paragraph(heading, styles["Heading2"]))
        for item in report[key] or ["None calculated."]:
            story.append(Paragraph(item, styles["Normal"]))
        story.append(Spacer(1, 8))
    if report["table"]["rows"]:
        story.append(Paragraph(report["table"]["title"], styles["Heading2"]))
        story.append(_bars(report["table"]["rows"]))
        table_rows = [report["table"]["columns"]] + report["table"]["rows"][:12]
        story.append(Table(table_rows, hAlign="LEFT"))
    for note in report["notes"]:
        story.append(Spacer(1, 8))
        story.append(Paragraph(note, styles["Italic"]))
    SimpleDocTemplate(str(path), pagesize=letter).build(story)


def write_xlsx(path: Path, report: dict) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Summary"
    sheet.append(["Title", report["title"]])
    sheet.append(["Period", report["period"]])
    sheet.append([])
    sheet.append(["Measure", "Value"])
    for item in report["kpis"]:
        sheet.append([item["label"], item["value"]])
    sheet.append([])
    sheet.append(["Findings"])
    for item in report["findings"]:
        sheet.append([item])
    sheet.append([])
    sheet.append(["Risks"])
    for item in report["risks"]:
        sheet.append([item])
    sheet.append([])
    sheet.append(["Recommendations (interpretation)"])
    for item in report["recommendations"]:
        sheet.append([item])
    data = workbook.create_sheet("Table")
    data.append(report["table"]["columns"])
    for row in report["table"]["rows"]:
        data.append(row)
    if report["table"]["rows"]:
        chart = BarChart()
        chart.title = report["table"]["title"]
        chart.y_axis.title = report["table"]["columns"][1]
        chart.add_data(Reference(data, min_col=2, min_row=1, max_row=min(len(report["table"]["rows"]) + 1, 13)), titles_from_data=True)
        chart.set_categories(Reference(data, min_col=1, min_row=2, max_row=min(len(report["table"]["rows"]) + 1, 13)))
        chart.shape = 4
        data.add_chart(chart, "E2")
    workbook.save(path)


def write_csv(path: Path, report: dict) -> None:
    import csv

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(report["table"]["columns"])
        writer.writerows(report["table"]["rows"])
