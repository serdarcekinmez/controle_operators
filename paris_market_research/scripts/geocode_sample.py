"""IGN Géoplateforme geocoding — yalnızca birkaç örnek adresle uç nokta testi.

Koordinatı zaten olan kayıtlar yeniden geocode EDİLMEZ. Bu script yalnızca
servisin çalıştığını, yanıt biçimini ve skor alanını doğrular.
Servis sınırı (belgelere göre IP başına ~50 istek/sn) çok altında kalınır.

Kullanım:
    python scripts/geocode_sample.py
    python scripts/geocode_sample.py --address "18 rue de Dunkerque 75010 Paris"
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today
from _profile import in_paris_bbox

SID = "H_geoplateforme_geocodage"
ENDPOINT = "https://data.geopf.fr/geocodage/search"

# Kamuya açık, bilinen yerlerin adresleri (kişisel veri değildir)
SAMPLES = [
    "18 rue de Dunkerque 75010 Paris",        # Gare du Nord
    "Place de l'Hôtel de Ville 75004 Paris",  # Hôtel de Ville
    "5 avenue Anatole France 75007 Paris",    # Tour Eiffel çevresi
    "99 rue de Rivoli 75001 Paris",           # Louvre çevresi
    "20 boulevard Diderot 75012 Paris",       # Gare de Lyon
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--address", action="append", help="test adresi (birden çok verilebilir)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = make_session()
    rows = []
    for i, q in enumerate(a.address or SAMPLES, 1):
        fname = f"geocode_{i:02d}_{re.sub(r'[^a-z0-9]+', '_', q.lower())[:40]}.json"
        m = safe_step(SID, f"adres {i}", fetch_to_raw, s, SID, fname, ENDPOINT, "json",
                      params={"q": q, "limit": 1, "index": "address"}, force=a.force)
        row = {"query": q, "label": "", "score": "", "lon": "", "lat": "", "citycode": "", "in_paris_bbox": ""}
        if m and m["validation"]["ok"]:
            obj = json.loads((RAW_DIR / SID / today() / fname).read_text(encoding="utf-8"))
            feats = obj.get("features", [])
            if feats:
                p, (lon, lat) = feats[0]["properties"], feats[0]["geometry"]["coordinates"]
                row.update(label=p.get("label"), score=p.get("score"), lon=lon, lat=lat,
                           citycode=p.get("citycode"), in_paris_bbox=in_paris_bbox(lon, lat))
        rows.append(row)
    if not any(r["lon"] != "" for r in rows):
        log_event(SID, "özet", "Atlandı", "Hiçbir adres çözülemedi; özet yazılmadı")
        return 0
    out = RAW_DIR / SID / today() / "geocode_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log_event(SID, "özet", "Yazıldı", f"{sum(1 for r in rows if r['lon'] != '')}/{len(rows)} adres çözüldü",
              file=str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
