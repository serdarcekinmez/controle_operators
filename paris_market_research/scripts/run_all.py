"""Aşama 2 toplama scriptlerinin hepsini sırayla çalıştırır.

Bir kaynak başarısız olursa kaydedilir ve diğerleriyle devam edilir.
Sonuçlar: data/raw/<kaynak>/<tarih>/..., logs/collection_log.jsonl,
logs/access_check_<tarih>.csv

Kullanım:
    python scripts/run_all.py
    python scripts/run_all.py --limit 50
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", default="100")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    force = ["--force"] if a.force else []
    steps = [
        ["check_access.py"],
        ["fetch_datagouv.py", *force],
        ["fetch_apur_bdcom.py", "--limit", a.limit, *force],
        ["fetch_osm_overpass.py", "--limit", a.limit, *force],
        ["fetch_insee_filosofi.py", *force],
        ["fetch_opendatasoft.py", "--limit", a.limit, *force],
        ["geocode_sample.py", *force],
        ["fetch_reports.py", *force],
    ]
    failed = []
    for st in steps:
        print(f"\n===== {' '.join(st)} =====", flush=True)
        rc = subprocess.call([sys.executable, str(HERE / st[0]), *st[1:]], cwd=HERE)
        if rc != 0:
            failed.append(st[0])
    print("\nTamamlandı. Script hatası:", failed or "yok",
          "(kaynak bazlı engeller logs/collection_log.jsonl içinde)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
