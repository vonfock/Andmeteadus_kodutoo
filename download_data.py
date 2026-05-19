"""Download raw yearly inspection CSVs into data/raw/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.data_loader import YEAR_URLS

import requests

RAW_DIR = Path(__file__).parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

CHUNK = 1024 * 1024  # 1 MB

for year, url in sorted(YEAR_URLS.items()):
    dest = RAW_DIR / f"{year}.csv"
    if dest.exists():
        print(f"[{year}] already exists, skipping.")
        continue
    print(f"[{year}] downloading...", flush=True)
    try:
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"  {pct:.0f}%  ({downloaded // (1024*1024)} MB)", end="\r", flush=True)
        mb = dest.stat().st_size / (1024 * 1024)
        print(f"[{year}] done — {mb:.1f} MB          ")
    except Exception as e:
        print(f"[{year}] FAILED: {e}")
        if dest.exists():
            dest.unlink()

print("\nAll done.")
