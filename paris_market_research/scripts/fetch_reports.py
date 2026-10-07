"""Yalnızca rapor/bağlam kaynakları: Banque de France ve Paris je t'aime.

Sayfa HTML'i ve sayfada bağlantısı bulunan PDF/XLSX/CSV dosyaları indirilir.
Sayfada indirilebilir tablo bulunursa kaydedilir; bulunmazsa kaynak
"Yalnızca rapor/harita" olarak kalır. Görüntülenebilir bir harita, adres
düzeyinde veri veya API sayılmaz.

Paris geneli turizm sayıları mahalle düzeyinde ölçüm olarak kullanılmaz.

Kullanım:
    python scripts/fetch_reports.py
"""
from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import urljoin

from _common import RAW_DIR, fetch_to_raw, log_event, make_session, safe_step, today

PAGES = {
    "G_bdf_especes": "https://www.banque-france.fr/fr/publications-et-statistiques/publications/"
                     "acces-du-public-aux-especes-actualisation-de-letat-des-lieux-fin-2025",
    "I_paris_tourisme": "https://parisjetaime.com/professionnels/article/chiffres-cles-du-tourisme-parisien-a1299",
}
EXT = {".pdf": "pdf", ".xlsx": "xlsx", ".csv": "csv", ".zip": "zip"}
MAX_FILES = 6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = make_session()
    for sid, page in PAGES.items():
        m = safe_step(sid, "sayfa", fetch_to_raw, s, sid, "page.html", page, "html", force=a.force)
        if not m or not m["validation"]["ok"]:
            continue
        html = (RAW_DIR / sid / today() / "page.html").read_text(encoding="utf-8", errors="replace")
        links = sorted({urljoin(page, h) for h in re.findall(r'href="([^"]+)"', html)
                        if re.search(r"\.(pdf|xlsx|csv|zip)(\?|$)", h, re.I)})
        tables = [l for l in links if not l.lower().split("?")[0].endswith(".pdf")]
        log_event(sid, "bağlantılar", "Bulundu",
                  f"{len(links)} dosya bağlantısı; tablo biçiminde {len(tables)}: {links[:10]}")
        if not tables:
            log_event(sid, "veri durumu", "Yalnızca rapor/harita",
                      "Sayfada indirilebilir tablo bağlantısı yok (yalnızca PDF/HTML)")
        for url in links[:MAX_FILES]:
            ext = "." + url.lower().split("?")[0].rsplit(".", 1)[-1]
            name = url.split("?")[0].rsplit("/", 1)[-1]
            safe_step(sid, f"dosya {name}", fetch_to_raw, s, sid, name, url, EXT[ext], force=a.force,
                      extra={"page": page})
    return 0


if __name__ == "__main__":
    sys.exit(main())
