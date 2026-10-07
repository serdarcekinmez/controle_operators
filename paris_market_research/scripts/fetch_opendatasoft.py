"""Opendatasoft (Explore API v2.1) portallarından veri.

  F1_sncf_frequentation  — SNCF "frequentation-gares": yıllık gar yolcu sayısı.
                           Küçük ulusal tablo → tamamı CSV olarak dışa aktarılır.
  F2_idfm_validations    — IDFM portalında "validations" geçen veri setleri
                           keşfedilir; ferré ağı günlük sayıları, saatlik
                           profiller ve gar/istasyon konumları için meta veri +
                           --limit kayıt örneği alınır.
  J_paris_arrondissements — Paris Open Data arrondissement sınırları (20 poligon,
                           tamamı GeoJSON).

Değişken anlamları farklıdır: SNCF = yıllık "voyageurs" tahmini; IDFM =
bilet doğrulama (validation) sayısı veya saatlik pay. Bunlar turist veya
yaya sayısı değildir.

Kullanım:
    python scripts/fetch_opendatasoft.py --limit 100
    python scripts/fetch_opendatasoft.py --only F2_idfm_validations
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today
from _profile import profile_df, read_table

PORTALS = {
    "F1_sncf_frequentation": "https://ressources.data.sncf.com",
    "F2_idfm_validations": "https://data.iledefrance-mobilites.fr",
    "J_paris_arrondissements": "https://opendata.paris.fr",
}
API = "{base}/api/explore/v2.1"

# IDFM keşfinde aranacak veri seti kalıpları
IDFM_PATTERNS = {
    "daily_counts_rail": re.compile(r"validations.*ferr.*nombre.*jour", re.I),
    "hourly_profiles_rail": re.compile(r"validations.*ferr.*profil", re.I),
    "station_locations": re.compile(r"emplacement.*gares|arrets.*(lignes|reseau)|zones?-d-arrets", re.I),
}


def ds_meta(s, sid, base, ds, force):
    return fetch_to_raw(s, sid, f"{ds}__meta.json", f"{API.format(base=base)}/catalog/datasets/{ds}", "json",
                        force=force)


def sncf(s, limit, force):
    sid, base, ds = "F1_sncf_frequentation", PORTALS["F1_sncf_frequentation"], "frequentation-gares"
    safe_step(sid, "meta", ds_meta, s, sid, base, ds, force)
    m = safe_step(sid, "tam CSV", fetch_to_raw, s, sid, f"{ds}.csv",
                  f"{API.format(base=base)}/catalog/datasets/{ds}/exports/csv", "csv",
                  params={"delimiter": ";"}, force=force)
    if m and m["validation"]["ok"]:
        df = read_table(RAW_DIR / sid / today() / f"{ds}.csv")
        cp = next((c for c in df.columns if "postal" in c.lower()), None)
        paris = int(df[cp].astype(str).str.startswith("75").sum()) if cp else None
        p = profile_df(df, sid, f"{ds}.csv", extra={"paris_rows_by_postcode_75": paris,
                       "note": "75 posta kodu = Paris belediyesi; çevre garlar tampon için ayrıca alınabilir"})
        log_event(sid, "profil", "Profil yazıldı", f"{len(df)} satır, Paris={paris}", file=str(p))


def idfm(s, limit, force):
    sid, base = "F2_idfm_validations", PORTALS["F2_idfm_validations"]
    m = safe_step(sid, "katalog araması", fetch_to_raw, s, sid, "catalog_search.json",
                  f"{API.format(base=base)}/catalog/datasets", "json",
                  params={"where": '"validations" OR "gares" OR "arrets"', "limit": 100,
                          "select": "dataset_id,metas"}, force=force)
    if not m or not m["validation"]["ok"]:
        return
    res = json.loads((RAW_DIR / sid / today() / "catalog_search.json").read_text(encoding="utf-8"))
    ids = [r["dataset_id"] for r in res.get("results", [])]
    log_event(sid, "katalog", "Bulundu", f"{len(ids)} veri seti: {ids[:30]}")
    for kind, pat in IDFM_PATTERNS.items():
        chosen = sorted(i for i in ids if pat.search(i))
        if not chosen:
            log_event(sid, kind, "Bulunamadı", "Katalogda eşleşen veri seti yok; elle kontrol edin")
            continue
        for ds in chosen[:3]:
            safe_step(sid, f"{kind}/{ds} meta", ds_meta, s, sid, base, ds, force)
            safe_step(sid, f"{kind}/{ds} örnek", fetch_to_raw, s, sid, f"{ds}__sample{limit}.json",
                      f"{API.format(base=base)}/catalog/datasets/{ds}/records", "json",
                      params={"limit": min(limit, 100)}, force=force)


def arrondissements(s, limit, force):
    sid, base, ds = "J_paris_arrondissements", PORTALS["J_paris_arrondissements"], "arrondissements"
    safe_step(sid, "meta", ds_meta, s, sid, base, ds, force)
    m = safe_step(sid, "GeoJSON", fetch_to_raw, s, sid, f"{ds}.geojson",
                  f"{API.format(base=base)}/catalog/datasets/{ds}/exports/geojson", "geojson", force=force)
    if m and m["validation"]["ok"]:
        gj = json.loads((RAW_DIR / sid / today() / f"{ds}.geojson").read_text(encoding="utf-8"))
        n = len(gj.get("features", []))
        log_event(sid, "makullük", "OK" if n == 20 else "Uyarı", f"{n} poligon (beklenen 20)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=list(PORTALS))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = make_session()
    for sid, fn in (("F1_sncf_frequentation", sncf), ("F2_idfm_validations", idfm),
                    ("J_paris_arrondissements", arrondissements)):
        if a.only in (None, sid):
            fn(s, a.limit, a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
