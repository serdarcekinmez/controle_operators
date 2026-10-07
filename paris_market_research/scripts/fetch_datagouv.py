"""data.gouv.fr API'si üzerinden kaynak çözümleme ve indirme.

Kapsanan kaynaklar:
  A_atout_france  — Hébergements touristiques classés en France (Atout France)
  E_iris_contours — Contours IRIS (IGN/INSEE): varsayılan olarak yalnızca meta veri;
                    büyük arşiv --download-large ile indirilir.

İndirme bağlantıları elle yazılmaz; her çalıştırmada data.gouv API'sinden
güncel kaynak listesi alınır ve kayda geçer.

Kullanım:
    python scripts/fetch_datagouv.py                 # A + E meta
    python scripts/fetch_datagouv.py --only A_atout_france
    python scripts/fetch_datagouv.py --download-large  # IRIS arşivini de indir
"""
from __future__ import annotations

import argparse
import json
import sys

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today
from _profile import PARIS_POSTCODES, profile_df, read_table

API = "https://www.data.gouv.fr/api/1/datasets/{slug}/"

DATASETS = {
    "A_atout_france": "hebergements-touristiques-classes-en-france",
    "E_iris_contours": "contours-iris-r-2",
}


def resources_of(meta_path) -> list[dict]:
    d = json.loads(meta_path.read_text(encoding="utf-8"))
    return [{"title": r.get("title"), "format": (r.get("format") or "").lower(),
             "url": r.get("url"), "filesize": r.get("filesize"),
             "last_modified": r.get("last_modified"), "type": r.get("type")}
            for r in d.get("resources", [])]


def dataset_meta(session, sid: str, slug: str, force: bool):
    meta = fetch_to_raw(session, sid, "datagouv_dataset.json", API.format(slug=slug), "json",
                        force=force, extra={"dataset_slug": slug})
    return meta


def atout_france(session, force: bool) -> None:
    sid = "A_atout_france"
    m = safe_step(sid, "data.gouv meta veri", dataset_meta, session, sid, DATASETS[sid], force)
    if not m or not m["validation"]["ok"]:
        return
    meta_path = RAW_DIR / sid / today() / "datagouv_dataset.json"
    res = resources_of(meta_path)
    for r in res:
        print("  kaynak:", r["format"], r["last_modified"], r["title"], r["url"])
    # Ana dosya: en son güncellenen CSV (yoksa XLSX). Dosya ulusal ve küçük
    # olduğundan tamamı indirilir; Paris süzmesi yalnızca profilde yapılır.
    cands = [r for r in res if r["format"] in ("csv", "xlsx") and r["url"]]
    if not cands:
        log_event(sid, "kaynak seçimi", "Hata", "CSV/XLSX kaynak bulunamadı")
        return
    best = sorted(cands, key=lambda r: (r["format"] == "csv", r["last_modified"] or ""))[-1]
    fname = "atout_france_classes." + best["format"]
    dm = safe_step(sid, "toplu dosya", fetch_to_raw, session, sid, fname, best["url"],
                   best["format"], force=force,
                   extra={"resource_title": best["title"], "resource_last_modified": best["last_modified"]})
    if not dm or not dm["validation"]["ok"]:
        return
    df = read_table(RAW_DIR / sid / today() / fname)
    cp_col = next((c for c in df.columns if "postal" in c.lower()), None)
    paris_n = int(df[cp_col].astype(str).str.strip().str.zfill(5).isin(PARIS_POSTCODES).sum()) if cp_col else None
    p = profile_df(df, sid, fname, extra={
        "paris_filter": f"'{cp_col}' ∈ 75001–75020/75116 (yalnızca profil; ham veri süzülmedi)",
        "paris_rows": paris_n,
        "note": "Yalnızca Atout France sınıflandırmasındaki tesisler; sınıfsız oteller kapsam dışı.",
    })
    log_event(sid, "profil", "Profil yazıldı", f"{len(df)} satır, Paris={paris_n}", file=str(p))


def iris_contours(session, force: bool, download_large: bool) -> None:
    sid = "E_iris_contours"
    m = safe_step(sid, "data.gouv meta veri", dataset_meta, session, sid, DATASETS[sid], force)
    if not m or not m["validation"]["ok"]:
        return
    res = resources_of(RAW_DIR / sid / today() / "datagouv_dataset.json")
    for r in res:
        print("  kaynak:", r["format"], r["last_modified"], r["title"], r["url"])
    if not download_large:
        log_event(sid, "arşiv", "Atlandı", "Büyük arşiv indirilmedi (--download-large ile indirilir)")
        return
    # Metropol Fransa GPKG/SHP arşivlerinden en günceli; seçim başlık üzerinden yapılır
    # ve kayda geçer, elle yazılmış URL kullanılmaz.
    arch = [r for r in res if r["url"] and r["url"].lower().endswith((".7z", ".zip"))]
    if not arch:
        log_event(sid, "arşiv", "Hata", "Arşiv kaynağı bulunamadı")
        return
    pref = [r for r in arch if "gpkg" in r["url"].lower() and "fxx" in r["url"].lower()] or arch
    best = sorted(pref, key=lambda r: r["last_modified"] or "")[-1]
    ext = "7z" if best["url"].lower().endswith(".7z") else "zip"
    safe_step(sid, "arşiv", fetch_to_raw, session, sid, best["url"].rsplit("/", 1)[-1], best["url"],
              ext, force=force, extra={"resource_title": best["title"]})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=list(DATASETS))
    ap.add_argument("--force", action="store_true", help="önbelleği yok say")
    ap.add_argument("--download-large", action="store_true", help="IRIS arşivini indir")
    a = ap.parse_args()
    s = make_session()
    if a.only in (None, "A_atout_france"):
        atout_france(s, a.force)
    if a.only in (None, "E_iris_contours"):
        iris_contours(s, a.force, a.download_large)
    return 0


if __name__ == "__main__":
    sys.exit(main())
