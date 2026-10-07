"""OpenStreetMap / Overpass: döviz büroları, ATM'ler, bankalar, para transferi.

Her kategori AYRI sorgulanır ve ayrı dosyaya yazılır; Western Union gibi
para transferi noktaları döviz bürosuyla birleştirilmez.

Her kategori için iki sorgu yapılır:
  1. `out count`  — kapsam alanındaki TAM tarama sayısı (boş sonuç ile örneklem
                    ayrımını yapabilmek için).
  2. örnek        — en fazla --limit kayıt, `out center tags` (yollar/ilişkiler
                    için merkez noktası).

Kapsam:
  --scope paris   (varsayılan) Paris belediyesi sınırı: admin_level=8, ref:INSEE=75056.
  --scope bbox --buffer-km K   Paris sınır kutusu K km genişletilir (tampon
                    tasarımı için; K bu aşamada kesinleştirilmez, varsayılan yok).

Etiket eksikliği "hizmet yok" demek değildir: örn. currency:* etiketi olmayan
bir ATM yabancı para vermiyor anlamına gelmez, yalnızca bilinmiyordur.

Kullanım:
    python scripts/fetch_osm_overpass.py --limit 100
    python scripts/fetch_osm_overpass.py --scope bbox --buffer-km 2 --limit 50
    python scripts/fetch_osm_overpass.py --print-queries   # ağsız, yalnızca sorguları göster
"""
from __future__ import annotations

import argparse
import csv
import json
import sys

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today

ENDPOINT = "https://overpass-api.de/api/interpreter"

# kategori -> Overpass filtre(leri). Bir kategori birden çok filtre içerebilir.
CATEGORIES = {
    # Döviz bürosu (insanlı ofis/kiosk)
    "bureau_de_change": ['nwr["amenity"="bureau_de_change"]'],
    # Otomatik döviz makinesi adayları: OSM'de yerleşik tek etiket yok; araştırma amaçlı
    # birden çok aday filtre. Sonuçlar elle doğrulanmalıdır.
    "currency_exchange_machine_candidates": [
        'nwr["amenity"="bureau_de_change"]["self_service"="yes"]',
        'nwr["amenity"="bureau_de_change"]["automated"="yes"]',
        'nwr["amenity"="vending_machine"]["vending"~"currency|exchange|money",i]',
    ],
    # Bağımsız ATM nesneleri
    "atm_standalone": ['nwr["amenity"="atm"]'],
    # Başka bir nesne (çoğu banka) üzerinde ATM bilgisi — bağımsız ATM ile çifte sayım riski
    "atm_on_other_feature": ['nwr["atm"="yes"]["amenity"!="atm"]'],
    # Yabancı para veren ATM adayları: EUR dışında bir currency:* = yes
    "atm_foreign_currency_candidates": [
        'nwr["amenity"="atm"][~"^currency:(USD|GBP|CHF|JPY|CNY|CAD|AUD)$"~"^yes$"]',
    ],
    # Banka şubeleri (bağlam ve çifte sayım kontrolü için)
    "bank": ['nwr["amenity"="bank"]'],
    # Para transferi — AYRI kategori
    "money_transfer": ['nwr["amenity"="money_transfer"]', 'nwr["money_transfer"]["amenity"!="money_transfer"]'],
}

# Örnek kayıtlardan çıkarılacak alanlar (yalnızca kayıtta varsa doldurulur)
FIELDS = ["name", "brand", "operator", "addr:housenumber", "addr:street", "addr:postcode",
          "addr:city", "opening_hours", "access", "wheelchair", "indoor", "level",
          "atm", "cash_in", "cash_out", "drive_through", "fee", "self_service", "automated",
          "money_transfer", "vending", "website", "check_date", "survey:date"]

# Paris kutusu (WGS84) — yalnızca --scope bbox için tampon tabanı
PARIS_BBOX = (48.8155, 2.2242, 48.9022, 2.4699)  # güney, batı, kuzey, doğu


def area_clause(scope: str, buffer_km: float | None) -> tuple[str, str]:
    """(ön tanım, uzamsal filtre) döndürür."""
    if scope == "paris":
        pre = 'area["boundary"="administrative"]["admin_level"="8"]["ref:INSEE"="75056"]->.a;'
        return pre, "(area.a)"
    if buffer_km is None:
        raise SystemExit("--scope bbox için --buffer-km açıkça verilmelidir")
    dlat = buffer_km / 111.0
    dlon = buffer_km / 73.0  # ~48.86°K'de 1° boylam ≈ 73 km
    s, w, n, e = PARIS_BBOX
    return "", f"({s - dlat:.5f},{w - dlon:.5f},{n + dlat:.5f},{e + dlon:.5f})"


def build_query(filters: list[str], scope: str, buffer_km: float | None, mode: str, limit: int) -> str:
    pre, spatial = area_clause(scope, buffer_km)
    union = "".join(f"{f}{spatial};" for f in filters)
    out = "out count;" if mode == "count" else f"out center tags {limit};"
    return f"[out:json][timeout:180];{pre}({union});{out}"


def flatten(el: dict, category: str) -> dict:
    tags = el.get("tags", {})
    lat = el.get("lat", el.get("center", {}).get("lat"))
    lon = el.get("lon", el.get("center", {}).get("lon"))
    row = {"category": category, "osm_type": el["type"], "osm_id": el["id"], "lat": lat, "lon": lon,
           "amenity": tags.get("amenity", "")}
    for f in FIELDS:
        row[f] = tags.get(f, "")
    cur = sorted(k.split(":", 1)[1] for k, v in tags.items() if k.startswith("currency:") and v == "yes")
    row["currencies_yes"] = ";".join(cur)
    row["n_tags"] = len(tags)
    return row


def run(scope: str, buffer_km: float | None, limit: int, force: bool) -> None:
    sid = "C_osm_overpass"
    s = make_session()
    summary = []
    tag = scope if scope == "paris" else f"bbox_{buffer_km}km"
    for cat, filters in CATEGORIES.items():
        counts = {}
        for mode in ("count", "sample"):
            q = build_query(filters, scope, buffer_km, mode, limit)
            fname = f"overpass_{tag}_{cat}_{mode}.json"
            m = safe_step(sid, f"{cat}/{mode}", fetch_to_raw, s, sid, fname, ENDPOINT, "json",
                          force=force, method="POST", data={"data": q},
                          extra={"overpass_query": q, "scope": scope, "buffer_km": buffer_km,
                                 "category": cat})
            if not m or not m["validation"]["ok"]:
                continue
            obj = json.loads((RAW_DIR / sid / today() / fname).read_text(encoding="utf-8"))
            if obj.get("remark"):
                log_event(sid, f"{cat}/{mode}", "Uyarı", f"Overpass remark: {obj['remark']}")
            if mode == "count":
                t = (obj.get("elements") or [{}])[0].get("tags", {})
                counts = {k: int(v) for k, v in t.items() if v.isdigit()}
            else:
                rows = [flatten(e, cat) for e in obj.get("elements", [])]
                if rows:
                    out = RAW_DIR / sid / today() / f"sample_{tag}_{cat}.csv"
                    with out.open("w", newline="", encoding="utf-8") as f:
                        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                        w.writeheader()
                        w.writerows(rows)
                filled = {k: sum(1 for r in rows if r.get(k)) for k in
                          ("name", "operator", "opening_hours", "addr:street", "currencies_yes")}
                summary.append({"category": cat, "full_count": counts.get("total"),
                                "sample_n": len(rows), "sample_filled": filled})
    bdc = next((x for x in summary if x["category"] == "bureau_de_change"), None)
    if bdc and not bdc["full_count"]:
        log_event(sid, "makullük", "Uyarı",
                  "bureau_de_change tam sayımı 0: alan (area) çözümlemesi başarısız olmuş olabilir; "
                  "boş sonuç 'Paris'te döviz bürosu yok' anlamına gelmez")
    if not summary:
        log_event(sid, "özet", "Atlandı", "Hiçbir kategori indirilemedi; özet yazılmadı")
        return
    sp = RAW_DIR / sid / today() / f"summary_{tag}.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log_event(sid, "özet", "Yazıldı", f"{len(summary)} kategori", file=str(sp))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", choices=["paris", "bbox"], default="paris")
    ap.add_argument("--buffer-km", type=float)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--print-queries", action="store_true")
    a = ap.parse_args()
    if a.print_queries:
        for cat, filters in CATEGORIES.items():
            print(f"# {cat}\n{build_query(filters, a.scope, a.buffer_km, 'sample', a.limit)}\n")
        return 0
    run(a.scope, a.buffer_km, a.limit, a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
