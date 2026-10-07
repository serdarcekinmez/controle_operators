"""Tüm kaynak sunucularına hafif bir erişim testi yapar.

Yalnızca "sunucuya ulaşılabiliyor mu ve ne tür içerik dönüyor" sorusunu
cevaplar; bir sayfanın açılması veri erişiminin doğrulandığı anlamına gelmez.

Çıktı: logs/access_check_<tarih>.csv

Kullanım:
    python scripts/check_access.py
"""
from __future__ import annotations

import csv
import sys

import requests

from _common import LOG_DIR, FetchError, http_get, make_session, today, utc_now

# (kaynak_id, açıklama, url)
PROBES = [
    ("A_atout_france", "data.gouv API — Atout France veri seti",
     "https://www.data.gouv.fr/api/1/datasets/hebergements-touristiques-classes-en-france/"),
    ("B_apur_bdcom", "APUR BDCOM sayfası",
     "https://www.apur.org/fr/open-data-cartes/open-data/base-donnees-commerces-parisiens"),
    ("B_apur_bdcom", "APUR açık veri kataloğu (DCAT)", "https://opendata.apur.org/data.json"),
    ("C_osm_overpass", "Overpass API durum", "https://overpass-api.de/api/status"),
    ("C_osm_overpass", "OSM wiki", "https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dbureau_de_change"),
    ("C_osm_overpass", "Taginfo API", "https://taginfo.openstreetmap.org/api/4/tag/stats?key=amenity&value=bureau_de_change"),
    ("D_insee_filosofi", "INSEE Filosofi 2021 IRIS sayfası", "https://www.insee.fr/fr/statistiques/8229323"),
    ("E_iris_contours", "data.gouv API — Contours IRIS", "https://www.data.gouv.fr/api/1/datasets/contours-iris-r-2/"),
    ("E_iris_contours", "IGN Géoplateforme indirme", "https://data.geopf.fr/telechargement/resource/CONTOURS-IRIS"),
    ("F1_sncf_frequentation", "SNCF Explore API", "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/frequentation-gares"),
    ("F2_idfm_validations", "IDFM Explore API katalog", "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets?limit=1"),
    ("G_bdf_especes", "Banque de France sayfası",
     "https://www.banque-france.fr/fr/publications-et-statistiques/publications/acces-du-public-aux-especes-actualisation-de-letat-des-lieux-fin-2025"),
    ("H_geoplateforme_geocodage", "Géoplateforme geocodage", "https://data.geopf.fr/geocodage/search?q=Paris&limit=1"),
    ("I_paris_tourisme", "Paris je t'aime chiffres clés", "https://parisjetaime.com/professionnels/article/chiffres-cles-du-tourisme-parisien-a1299"),
    ("J_paris_arrondissements", "Paris Open Data — arrondissements", "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements"),
]


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = LOG_DIR / f"access_check_{today()}.csv"
    s = make_session()
    rows = []
    for sid, label, url in PROBES:
        row = {"checked_at_utc": utc_now(), "source_id": sid, "label": label, "url": url,
               "http_status": "", "content_type": "", "result": "", "detail": ""}
        try:
            r = http_get(s, url)
            row.update(http_status=r.status_code, content_type=r.headers.get("Content-Type", ""),
                       result="Sunucuya erişildi", detail=f"{len(r.content)} bayt")
        except FetchError as e:
            row.update(http_status=e.http_status or "", result=e.status, detail=str(e)[:300])
        except requests.RequestException as e:
            row.update(result="Hata", detail=f"{type(e).__name__}: {str(e)[:250]}")
        print(f"{sid:28s} {row['result']:20s} {row['http_status']!s:5s} {label}")
        rows.append(row)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nYazıldı: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
