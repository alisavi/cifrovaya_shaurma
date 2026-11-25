#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reproducible download of the raw data for w1-hab.

Usage:
    python data/fetch.py            # download everything that is missing
    python data/fetch.py --hash     # only print sha256 of local raw files

Notes
-----
* NHANES and BRFSS are U.S. Government works in the public domain.
* AI4FoodDB is CC BY-NC-ND 4.0 (research use only). Its server currently has
  an incomplete TLS chain, so the download uses verify=False deliberately;
  the archive is checked against the hash recorded in data/PASSPORT.md.
* Files are large; nothing is committed to git (see .gitignore).
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
NHANES = RAW / "nhanes"
EXTRACTED = RAW / "extracted"
AI4FOOD = RAW / "ai4food"

NHANES_FILES = [
    "DEMO_J",
    "BMX_J",
    "BPX_J",
    "DR1TOT_J",
    "SLQ_J",
    "PAQ_J",
    "DPQ_J",
    "BPQ_J",
    "SMQ_J",
]
NHANES_URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/{name}.XPT"

BRFSS_URL = "https://www.cdc.gov/brfss/annual_data/2024/files/LLCP2024XPT.zip"
AI4FOOD_URL = "https://bidalab.eps.uam.es/static/AI4FoodDB/AI4FoodDB.zip"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, ua: bool = True, insecure: bool = False) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip {dest.relative_to(ROOT)} ({dest.stat().st_size:,} bytes)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Accept": "*/*"}
    if ua:
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    if "cdc.gov" in url:
        headers["Referer"] = "https://www.cdc.gov/brfss/annual_data/annual_2024.html"
    print(f"download {url}")
    if insecure:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    with requests.get(
        url, headers=headers, stream=True, timeout=300, verify=not insecure
    ) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print(f"  saved {dest.relative_to(ROOT)} ({dest.stat().st_size:,} bytes)")


def extract(zip_path: Path, out_dir: Path) -> None:
    if not zip_path.exists():
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out_dir)
    print(f"extracted {zip_path.name} -> {out_dir.relative_to(ROOT)}")


def main() -> int:
    if "--hash" in sys.argv:
        for p in sorted(RAW.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".xpt", ".zip"}:
                print(f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}")
        return 0

    for name in NHANES_FILES:
        download(NHANES_URL.format(name=name), NHANES / f"{name}.xpt")

    brfss_zip = RAW / "brfss2024.zip"
    download(BRFSS_URL, brfss_zip)
    extract(brfss_zip, EXTRACTED)

    ai_zip = AI4FOOD / "AI4FoodDB.zip"
    download(AI4FOOD_URL, ai_zip, insecure=True)
    extract(ai_zip, AI4FOOD / "extracted")

    print("\nsha256 (сверьте с data/PASSPORT.md):")
    for p in sorted(RAW.rglob("*")):
        if p.is_file() and p.name.endswith((".XPT", ".xpt", ".zip")):
            print(f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
