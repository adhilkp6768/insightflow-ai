"""Locate or download the UCI Online Retail II workbook.

Citation: Chen, Daqing. Online Retail II. UCI Machine Learning Repository, 2019.
https://archive.ics.uci.edu/dataset/502/online+retail+ii
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.request import urlopen

from app.services.frames import data_root

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"


def _directories() -> list[Path]:
    repo_copy = Path(__file__).resolve().parents[3] / "data" / "uci"
    ordered = [data_root() / "uci", repo_copy]
    unique: list[Path] = []
    for path in ordered:
        if path not in unique:
            unique.append(path)
    return unique


def find_workbook() -> Path | None:
    for directory in _directories():
        if not directory.exists():
            continue
        matches = sorted(directory.rglob("*.xlsx"))
        if matches:
            return matches[0]
    return None


def ensure_uci_workbook(progress: Callable[[str], None] | None = None) -> Path:
    found = find_workbook()
    if found is not None:
        if progress:
            progress(f"Using the workbook already stored at {found.name}.")
        return found
    destination = data_root() / "uci"
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / "online-retail-ii.zip"
    if progress:
        progress("Downloading Online Retail II from the UCI repository.")
    with urlopen(URL, timeout=180) as response, archive_path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if progress:
        progress("Extracting the workbook.")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination)
    found = find_workbook()
    if found is None:
        raise ValueError("The UCI archive did not contain an Excel workbook.")
    return found
