"""Download the UCI Online Retail II workbook.

The file is stored under data/uci and is not committed.
Citation: Chen, Daqing. Online Retail II. UCI Machine Learning Repository, 2019.
https://archive.ics.uci.edu/dataset/502/online+retail+ii
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from urllib.request import urlopen

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
DESTINATION = Path(__file__).resolve().parents[1] / "data" / "uci"


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    archive_path = DESTINATION / "online-retail-ii.zip"
    print(f"Downloading {URL}")
    with urlopen(URL, timeout=120) as response, archive_path.open("wb") as handle:
        handle.write(response.read())
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(DESTINATION)
    print(f"Extracted into {DESTINATION}")
    print("Upload the workbook from Data Management. It is not copied into git.")


if __name__ == "__main__":
    main()
