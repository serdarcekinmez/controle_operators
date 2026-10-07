"""Ortak yardımcılar: HTTP oturumu, tekrar deneme, hız sınırı, önbellek,
içerik doğrulama ve kaynak bilgisi (provenance) kaydı.

Kurallar:
- Ham dosyalar indirildiği gibi saklanır, hiçbir zaman yerinde değiştirilmez.
- Her ham dosyanın yanına <dosya>.meta.json yazılır (URL, parametreler,
  çekim zamanı, HTTP durumu, içerik türü, boyut, sha256, doğrulama sonucu).
- Kimlik bilgisi dosyaya yazılmaz. İletişim e-postası istenirse yalnızca
  ortam değişkeninden (CONTACT_EMAIL) User-Agent'a eklenir.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
LOG_DIR = ROOT / "logs"

TIMEOUT = (15, 120)          # (bağlantı, okuma) saniye
MAX_RETRIES = 3              # toplam deneme = 1 + MAX_RETRIES
MIN_INTERVAL_PER_HOST = 1.5  # aynı sunucuya iki istek arası en az bekleme (sn)

_last_call: dict[str, float] = {}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return dt.date.today().isoformat()


def user_agent() -> str:
    ua = "paris-market-research/0.2 (phase-2 source verification; python-requests)"
    contact = os.environ.get("CONTACT_EMAIL")
    if contact:
        ua += f" contact:{contact}"
    return ua


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = user_agent()
    return s


class FetchError(Exception):
    def __init__(self, message: str, status: str = "Engellendi", http_status: int | None = None):
        super().__init__(message)
        self.status = status
        self.http_status = http_status


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    wait = MIN_INTERVAL_PER_HOST - (time.monotonic() - _last_call.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.monotonic()


def http_get(session: requests.Session, url: str, params: dict | None = None,
             method: str = "GET", data: dict | None = None) -> requests.Response:
    """Zaman aşımı, sınırlı tekrar ve Retry-After desteğiyle istek.

    Ağ/proxy reddi (bağlantı kurulamadı) tekrar denenmez: bu bir politika
    engelidir, geçici hata değildir.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        _throttle(url)
        try:
            r = session.request(method, url, params=params, data=data, timeout=TIMEOUT)
        except requests.exceptions.ProxyError as e:
            raise FetchError(f"Proxy/ağ politikası bağlantıyı reddetti: {e}") from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exc = e
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code in (429, 502, 503, 504):
            retry_after = r.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt + 2)
            last_exc = FetchError(f"HTTP {r.status_code}", http_status=r.status_code)
            time.sleep(min(delay, 60))
            continue
        if r.status_code >= 400:
            status = ("Engellendi" if r.status_code in (401, 403, 407, 451)
                      else "Bulunamadı" if r.status_code in (404, 410) else "Hata")
            raise FetchError(f"HTTP {r.status_code} — {url}", status=status,
                             http_status=r.status_code)
        return r
    raise FetchError(f"Tekrar denemeler tükendi: {last_exc}")


# --------------------------------------------------------------------------
# İçerik doğrulama: "CSV beklerken HTML hata sayfası" başarı sayılmaz.
# --------------------------------------------------------------------------
def looks_like_html(blob: bytes) -> bool:
    head = blob[:2048].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<html" in head[:512]


def validate_content(blob: bytes, expected: str) -> dict:
    """expected: csv | json | geojson | zip | 7z | pdf | xlsx | html"""
    res = {"expected": expected, "ok": False, "detail": ""}
    if not blob:
        res["detail"] = "boş yanıt"
        return res
    if expected != "html" and looks_like_html(blob):
        res["detail"] = "HTML sayfası döndü (veri değil)"
        return res
    try:
        if expected in ("json", "geojson"):
            obj = json.loads(blob.decode("utf-8"))
            if expected == "geojson":
                n = len(obj.get("features", [])) if isinstance(obj, dict) else 0
                res["ok"] = isinstance(obj, dict) and obj.get("type") == "FeatureCollection"
                res["detail"] = f"FeatureCollection, {n} feature"
            else:
                res["ok"] = True
                res["detail"] = f"JSON kök tipi: {type(obj).__name__}"
        elif expected == "csv":
            text = blob[:200_000].decode("utf-8-sig", errors="replace")
            lines = [l for l in text.splitlines() if l.strip()]
            sep = max([";", ",", "\t"], key=lambda c: lines[0].count(c)) if lines else ","
            ncol = lines[0].count(sep) + 1 if lines else 0
            res["ok"] = len(lines) >= 2 and ncol >= 2
            res["detail"] = f"ayraç='{sep}', sütun={ncol}, ilk 200KB'de satır={len(lines)}"
        elif expected in ("zip", "xlsx"):
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                names = z.namelist()
            res["ok"] = bool(names)
            res["detail"] = f"{len(names)} arşiv üyesi: {names[:10]}"
        elif expected == "7z":
            res["ok"] = blob[:6] == b"7z\xbc\xaf\x27\x1c"
            res["detail"] = "7z imzası" + (" doğru" if res["ok"] else " YOK")
        elif expected == "pdf":
            res["ok"] = blob[:5] == b"%PDF-"
            res["detail"] = "PDF imzası" + (" doğru" if res["ok"] else " YOK")
        elif expected == "html":
            res["ok"] = looks_like_html(blob)
            res["detail"] = "HTML sayfa (yalnızca rapor/bağlam)"
        else:
            res["detail"] = f"bilinmeyen beklenen tür: {expected}"
    except Exception as e:  # noqa: BLE001 — doğrulama hatası kayda geçer
        res["detail"] = f"açılamadı: {type(e).__name__}: {e}"
    return res


# --------------------------------------------------------------------------
# Kayıt
# --------------------------------------------------------------------------
def run_dir(source_id: str) -> Path:
    d = RAW_DIR / source_id / today()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_raw(source_id: str, filename: str, blob: bytes, *, url: str, params: dict | None,
             expected: str, http_status: int | None, content_type: str | None,
             extra: dict | None = None) -> dict:
    """Ham içeriği olduğu gibi yazar ve yanına meta.json koyar."""
    out = run_dir(source_id) / filename
    out.write_bytes(blob)
    meta = {
        "source_id": source_id,
        "file": out.name,
        "url": url,
        "params": params or {},
        "fetched_at_utc": utc_now(),
        "http_status": http_status,
        "content_type": content_type,
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "validation": validate_content(blob, expected),
    }
    if extra:
        meta.update(extra)
    out.with_name(out.name + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def cached(source_id: str, filename: str) -> Path | None:
    """Bugün aynı dosya zaten indirildiyse yeniden indirmeyelim (önbellek)."""
    p = RAW_DIR / source_id / today() / filename
    meta = p.with_name(p.name + ".meta.json")
    if p.exists() and meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if m.get("validation", {}).get("ok"):
            return p
    return None


def fetch_to_raw(session, source_id: str, filename: str, url: str, expected: str,
                 params: dict | None = None, force: bool = False, extra: dict | None = None,
                 method: str = "GET", data: dict | None = None) -> dict:
    hit = None if force else cached(source_id, filename)
    if hit:
        m = json.loads(hit.with_name(hit.name + ".meta.json").read_text(encoding="utf-8"))
        m["from_cache"] = True
        return m
    r = http_get(session, url, params=params, method=method, data=data)
    meta = save_raw(source_id, filename, r.content, url=r.url if method == "GET" else url,
                    params=params if method == "GET" else data, expected=expected,
                    http_status=r.status_code, content_type=r.headers.get("Content-Type"),
                    extra=extra)
    return meta


def log_event(source_id: str, step: str, status: str, detail: str = "", **kw) -> dict:
    """logs/collection_log.jsonl dosyasına bir satır ekler ve ekrana yazar."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts_utc": utc_now(), "source_id": source_id, "step": step,
           "status": status, "detail": detail, **kw}
    with (LOG_DIR / "collection_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{source_id}] {step}: {status} — {detail}")
    return rec


def safe_step(source_id: str, step: str, fn, *args, **kwargs):
    """Bir adım başarısız olursa kaydeder ve None döner; diğer adımlar sürer."""
    try:
        meta = fn(*args, **kwargs)
        ok = (meta or {}).get("validation", {}).get("ok", True) if isinstance(meta, dict) else True
        status = "Veri indirildi ve açıldı" if ok else "İndirildi ama doğrulanamadı"
        detail = (meta or {}).get("validation", {}).get("detail", "") if isinstance(meta, dict) else ""
        log_event(source_id, step, status, detail,
                  url=(meta or {}).get("url") if isinstance(meta, dict) else None)
        return meta
    except FetchError as e:
        log_event(source_id, step, e.status, str(e), http_status=e.http_status)
    except Exception as e:  # noqa: BLE001
        log_event(source_id, step, "Hata", f"{type(e).__name__}: {e}")
    return None
