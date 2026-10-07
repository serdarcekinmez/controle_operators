"""Ağdan bağımsız altyapı testleri (kaynaklara bağlanmaz).

Yerel bir HTTP sunucusu (127.0.0.1) üzerinden indirme, içerik doğrulama,
önbellek ve meta kaydını sınar. Gerçek kaynak erişimini KANITLAMAZ.

Çalıştırma:  python -m unittest discover -s tests -v
"""
import http.server
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import _common  # noqa: E402

CSV = b"code;nom;code_postal\n1;Hotel A;75001\n2;Hotel B;69001\n"
HTML = b"<!DOCTYPE html><html><body>Erreur 404</body></html>"


def zip_bytes():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("data.csv", CSV)
    return b.getvalue()


ROUTES = {"/ok.csv": CSV, "/fake.csv": HTML, "/a.zip": zip_bytes(),
          "/g.geojson": json.dumps({"type": "FeatureCollection", "features": []}).encode()}


class H(http.server.BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):
        H.hits += 1
        body = ROUTES.get(self.path.split("?")[0])
        self.send_response(200 if body else 404)
        self.end_headers()
        self.wfile.write(body or b"not found")

    def log_message(self, *a):
        pass


class Plumbing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.tmp = Path(tempfile.mkdtemp())
        _common.RAW_DIR = cls.tmp / "raw"
        _common.LOG_DIR = cls.tmp / "logs"
        _common.MIN_INTERVAL_PER_HOST = 0
        cls.s = _common.make_session()
        cls.s.trust_env = False  # yerel sunucu için proxy kullanma

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp)

    def test_validate(self):
        v = _common.validate_content
        self.assertTrue(v(CSV, "csv")["ok"])
        self.assertFalse(v(HTML, "csv")["ok"])
        self.assertIn("HTML", v(HTML, "csv")["detail"])
        self.assertFalse(v(b"", "json")["ok"])
        self.assertTrue(v(zip_bytes(), "zip")["ok"])
        self.assertFalse(v(b"PK broken", "zip")["ok"])
        self.assertTrue(v(b"%PDF-1.7 ...", "pdf")["ok"])
        self.assertTrue(v(ROUTES["/g.geojson"], "geojson")["ok"])
        self.assertFalse(v(b'{"a":1}', "geojson")["ok"])

    def test_fetch_meta_and_cache(self):
        m = _common.fetch_to_raw(self.s, "T", "ok.csv", self.base + "/ok.csv", "csv", params={"x": 1})
        self.assertTrue(m["validation"]["ok"])
        meta = json.loads((_common.RAW_DIR / "T" / _common.today() / "ok.csv.meta.json").read_text())
        for k in ("url", "params", "fetched_at_utc", "sha256", "bytes", "http_status"):
            self.assertIn(k, meta)
        before = H.hits
        m2 = _common.fetch_to_raw(self.s, "T", "ok.csv", self.base + "/ok.csv", "csv")
        self.assertTrue(m2.get("from_cache"))
        self.assertEqual(H.hits, before)

    def test_html_instead_of_csv_is_not_success(self):
        m = _common.safe_step("T", "fake", _common.fetch_to_raw, self.s, "T", "fake.csv",
                              self.base + "/fake.csv", "csv")
        self.assertFalse(m["validation"]["ok"])
        last = (_common.LOG_DIR / "collection_log.jsonl").read_text().strip().splitlines()[-1]
        self.assertIn("doğrulanamadı", json.loads(last)["status"])

    def test_http_404_logged_as_not_found(self):
        r = _common.safe_step("T", "404", _common.fetch_to_raw, self.s, "T", "missing.csv",
                              self.base + "/missing.csv", "csv")
        self.assertIsNone(r)
        last = json.loads((_common.LOG_DIR / "collection_log.jsonl").read_text().strip().splitlines()[-1])
        self.assertEqual(last["http_status"], 404)
        self.assertEqual(last["status"], "Bulunamadı")


if __name__ == "__main__":
    unittest.main()


class Parsers(unittest.TestCase):
    def test_osm_flatten_keeps_missing_as_empty(self):
        import fetch_osm_overpass as o
        el = {"type": "way", "id": 1, "center": {"lat": 48.86, "lon": 2.35},
              "tags": {"amenity": "atm", "currency:USD": "yes", "currency:EUR": "yes", "operator": "X"}}
        r = o.flatten(el, "atm_standalone")
        self.assertEqual((r["lat"], r["lon"]), (48.86, 2.35))
        self.assertEqual(r["currencies_yes"], "EUR;USD")
        self.assertEqual(r["opening_hours"], "")  # eksik etiket = bilinmiyor, "yok" değil

    def test_osm_bbox_requires_explicit_buffer(self):
        import fetch_osm_overpass as o
        with self.assertRaises(SystemExit):
            o.build_query(['nwr["amenity"="atm"]'], "bbox", None, "count", 10)

    def test_apur_layer_url(self):
        import fetch_apur_bdcom as a
        d = [{"accessURL": "https://services.arcgis.com/x/arcgis/rest/services/BDCOM_2023/FeatureServer/0/query?f=geojson"}]
        self.assertTrue(a.find_layer_url(d).endswith("/FeatureServer/0"))
        self.assertIsNone(a.find_layer_url([{"accessURL": "https://example.org/file.csv"}]))
