"""INSEE Filosofi — IRIS düzeyinde gelir ve yaşam düzeyi.

Sayfa HTML'i indirilir, içindeki `/fichier/<id>/...` bağlantıları çıkarılır
(dosya adları elle yazılmaz). IRIS CSV arşivleri indirilir, açılır ve
Paris IRIS'leri (kodu 751 ile başlayan, yani arrondissement kodları
75101–75120) sayılır.

Yayın tarihi ile verinin ait olduğu gelir yılı ayrı tutulur: veri yılı
sayfa başlığından ("... en 2021 (Iris)"), yayın tarihi sayfadaki
"Paru le" ifadesinden okunur.

Kullanım:
    python scripts/fetch_insee_filosofi.py
    python scripts/fetch_insee_filosofi.py --page-id 8229323
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from urllib.parse import urljoin

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today
from _profile import profile_df, read_table

SID = "D_insee_filosofi"
BASE = "https://www.insee.fr/fr/statistiques/{pid}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page-id", default="8229323", help="INSEE yayın sayfası kimliği (2021 IRIS: 8229323)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = make_session()
    day = RAW_DIR / SID / today()
    page = BASE.format(pid=a.page_id)

    m = safe_step(SID, "yayın sayfası", fetch_to_raw, s, SID, f"page_{a.page_id}.html", page, "html", force=a.force)
    if not m or not m["validation"]["ok"]:
        return 0
    html = (day / f"page_{a.page_id}.html").read_text(encoding="utf-8", errors="replace")
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    data_year = re.search(r"en (20\d{2}) \(Iris\)", html)
    paru = re.search(r"Paru le\s*:?\s*([0-9]{1,2}/[0-9]{2}/[0-9]{4})", html)
    geo = re.search(r"g[ée]ographie (?:au|en vigueur au) 1er janvier (20\d{2})", html, re.I)
    log_event(SID, "sayfa bilgisi", "Okundu",
              f"başlık={title.group(1).strip()[:120] if title else '?'}; veri_yılı={data_year.group(1) if data_year else '?'}; "
              f"yayın={paru.group(1) if paru else '?'}; coğrafya={geo.group(1) if geo else '?'}")

    links = sorted(set(re.findall(rf'href="([^"]*?/fichier/{a.page_id}/[^"]+)"', html)))
    log_event(SID, "dosya bağlantıları", "Bulundu", f"{len(links)} bağlantı: {links[:8]}")
    for href in links:
        url = urljoin(page, href)
        name = url.rsplit("/", 1)[-1]
        if not name.lower().endswith(".zip"):
            continue
        dm = safe_step(SID, f"arşiv {name}", fetch_to_raw, s, SID, name, url, "zip", force=a.force,
                       extra={"page": page})
        if not dm or not dm["validation"]["ok"]:
            continue
        with zipfile.ZipFile(day / name) as z:
            members = [n for n in z.namelist() if n.lower().endswith((".csv", ".xlsx"))]
        for mem in members:
            if "meta" in mem.lower():
                continue
            df = read_table(day / name, member=mem)
            iris_col = next((c for c in df.columns if c.upper() == "IRIS"), None)
            paris = int(df[iris_col].astype(str).str.startswith("751").sum()) if iris_col else None
            p = profile_df(df, SID, mem, extra={"archive": name, "paris_iris_rows": paris,
                                                "paris_filter": "IRIS kodu '751' ile başlar (75101–75120)"})
            log_event(SID, f"profil {mem}", "Profil yazıldı", f"{len(df)} satır, Paris IRIS={paris}", file=str(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
