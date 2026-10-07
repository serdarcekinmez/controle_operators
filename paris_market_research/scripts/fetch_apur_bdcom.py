"""APUR BDCOM (Base de données des commerces parisiens).

Adımlar:
  1. APUR açık veri kataloğunu (ArcGIS Hub DCAT: opendata.apur.org/data.json)
     indirir ve başlığında/anahtar kelimelerinde BDCOM/commerce geçen veri
     setlerini listeler (sürüm yılı başlıktan okunur, tahmin edilmez).
  2. Seçilen veri setinin dağıtımlarından ArcGIS FeatureServer/MapServer
     katmanını bulur; katman meta verisini (alanlar + kod alanları/domain)
     indirir. Faaliyet kodu sözlüğü burada `domain.codedValues` içinde
     varsa dışa aktarılır. Yoksa sözlük ayrı belge olarak elle aranmalıdır;
     kodlar tahmin edilmez.
  3. En fazla --limit kayıt GeoJSON örneği indirir.
  4. Sözlükte otel / change / agence de voyage geçen kodları ARAR (yalnızca
     metin eşleşmesi; sonuç elle doğrulanmalıdır).

Kullanım:
    python scripts/fetch_apur_bdcom.py --limit 100
    python scripts/fetch_apur_bdcom.py --year 2023
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today

SID = "B_apur_bdcom"
CATALOG = "https://opendata.apur.org/data.json"
KEYWORDS = re.compile(r"bdcom|commerces? parisien|base de donn[ée]es des commerces", re.I)
SEARCH_TERMS = re.compile(r"h[ôo]tel|change|devise|voyage|tourisme|banque|transfert|distributeur", re.I)


def find_layer_url(dist: list[dict]) -> str | None:
    for d in dist:
        u = d.get("accessURL") or d.get("downloadURL") or ""
        m = re.search(r"(https?://[^?\s]+/(FeatureServer|MapServer)/\d+)", u)
        if m:
            return m.group(1)
    for d in dist:
        u = d.get("accessURL") or ""
        if re.search(r"/(FeatureServer|MapServer)/?$", u):
            return u.rstrip("/") + "/0"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--year", help="Belirli bir BDCOM yılı (ör. 2023). Verilmezse en büyük yıl.")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = make_session()
    day = RAW_DIR / SID / today()

    m = safe_step(SID, "DCAT katalog", fetch_to_raw, s, SID, "apur_catalog_data.json", CATALOG, "json",
                  force=a.force)
    if not m or not m["validation"]["ok"]:
        return 0
    cat = json.loads((day / "apur_catalog_data.json").read_text(encoding="utf-8"))
    hits = []
    for ds in cat.get("dataset", []):
        text = " ".join([ds.get("title", ""), ds.get("description", "")[:500], " ".join(ds.get("keyword", []))])
        if KEYWORDS.search(text):
            years = re.findall(r"(?:19|20)\d{2}", ds.get("title", ""))
            hits.append({"title": ds.get("title"), "identifier": ds.get("identifier"),
                         "modified": ds.get("modified"), "license": ds.get("license"),
                         "title_years": ";".join(years),
                         "layer_url": find_layer_url(ds.get("distribution", [])),
                         "distributions": ";".join(sorted({d.get("format") or d.get("mediaType") or "?"
                                                           for d in ds.get("distribution", [])}))})
    (day / "bdcom_catalog_hits.json").write_text(json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8")
    log_event(SID, "katalog eşleşmeleri", "Yazıldı", f"{len(hits)} veri seti", file=str(day / "bdcom_catalog_hits.json"))
    for h in hits:
        print("  ", h["title_years"] or "-", "|", h["title"], "|", h["modified"], "|", h["layer_url"])

    layered = [h for h in hits if h["layer_url"]]
    if a.year:
        layered = [h for h in layered if a.year in h["title_years"].split(";")]
    if not layered:
        log_event(SID, "katman seçimi", "Hata", "FeatureServer/MapServer katmanı bulunamadı; elle kontrol gerekli")
        return 0
    best = max(layered, key=lambda h: (max(h["title_years"].split(";")) if h["title_years"] else "", h["modified"] or ""))
    layer = best["layer_url"]
    log_event(SID, "katman seçimi", "Seçildi", f"{best['title']} → {layer}")

    lm = safe_step(SID, "katman meta", fetch_to_raw, s, SID, "layer_meta.json", layer, "json",
                   params={"f": "json"}, force=a.force, extra={"dataset_title": best["title"]})
    if lm and lm["validation"]["ok"]:
        meta = json.loads((day / "layer_meta.json").read_text(encoding="utf-8"))
        rows = []
        for fld in meta.get("fields", []):
            dom = fld.get("domain") or {}
            for cv in dom.get("codedValues", []) or []:
                rows.append({"field": fld["name"], "code": cv.get("code"), "label": cv.get("name")})
        fields_out = day / "layer_fields.csv"
        with fields_out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["name", "alias", "type", "has_domain"])
            for fld in meta.get("fields", []):
                w.writerow([fld.get("name"), fld.get("alias"), fld.get("type"), bool(fld.get("domain"))])
        if rows:
            dict_out = day / "activity_code_dictionary_from_domains.csv"
            with dict_out.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["field", "code", "label"])
                w.writeheader()
                w.writerows(rows)
            matches = [r for r in rows if SEARCH_TERMS.search(str(r["label"]))]
            (day / "activity_code_candidates.json").write_text(
                json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")
            log_event(SID, "kod sözlüğü", "Bulundu", f"{len(rows)} kod, {len(matches)} metin eşleşmesi (elle doğrula)")
        else:
            log_event(SID, "kod sözlüğü", "Bulunamadı",
                      "Katmanda coded-value domain yok; faaliyet sözlüğü ayrı belge olarak aranmalı")

    safe_step(SID, "örnek kayıtlar", fetch_to_raw, s, SID, f"sample_{a.limit}.geojson", layer + "/query", "geojson",
              params={"where": "1=1", "outFields": "*", "resultRecordCount": a.limit, "outSR": 4326, "f": "geojson"},
              force=a.force, extra={"dataset_title": best["title"]})
    safe_step(SID, "toplam sayım", fetch_to_raw, s, SID, "count.json", layer + "/query", "json",
              params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, force=a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
