import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Windows : la base peut encore être ouverte à la sortie de l'interpréteur.
TEMP = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["CONTROLE_AGENCES_DATA_DIR"] = str(Path(TEMP.name) / "Données é")
sys.path.insert(0, str(ROOT))
import server
from constants import USER_DIR
from services import db_service, file_service, instance_service
from services.errors import StartupError
from services.file_service import ensure_directories, resolve_stored_path
from pypdf import PdfReader
from PIL import Image
from reportlab.pdfgen import canvas
from migrate_data import migrate

REPORT = dict(branch=server.BRANCHES[0], controller="V5 test",
              control_date="2026-10-27", control_time="12:00")


def png():
    image = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(image, format="PNG")
    image.seek(0)
    return image


def pdf(pages):
    data = io.BytesIO()
    c = canvas.Canvas(data)
    for _ in range(pages):
        c.drawString(100, 700, "annexe")
        c.showPage()
    c.save()
    data.seek(0)
    return data


def setUpModule():
    ensure_directories()
    db_service.init_db()


class Workflow(unittest.TestCase):
    def test_report_excel_persistence(self):
        client = server.app.test_client()
        response = client.post("/api/report", data={
            "data": json.dumps(REPORT), "files": [(png(), "scan.png"), (pdf(2), "annexe.pdf")]})
        self.assertEqual(response.status_code, 200, response.json)
        result = response.json
        with client.get(result["url"]) as pdf_response:
            # rapport (1 page) + 1 image + PDF de 2 pages
            self.assertEqual(len(PdfReader(io.BytesIO(pdf_response.data)).pages), 4)
        excel = client.post("/api/excel/save", json={"report": REPORT}).json
        self.assertEqual(excel["total"], 1)
        updated = client.post("/api/excel/save", json={
            "base": excel["workbook"], "report": dict(REPORT, observations="mise à jour")}).json
        self.assertEqual(updated["total"], 1)
        removed = client.post("/api/excel/delete", json={
            "base": updated["workbook"], "controller": "v5 TEST",
            "date": "2026-10-27", "time": "12:00"}).json
        self.assertEqual(removed["total"], 0)
        reopened = client.post("/api/excel/state", json={"base": updated["workbook"]}).json
        self.assertEqual(reopened["total"], 1)
        code = ("from services import db_service; "
                "assert any(r['report_id'] == %r for r in db_service.get_recent_controls())"
                % result["report"]["report_id"])
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
        with client.get("/") as frontend_response:
            self.assertEqual(frontend_response.status_code, 200)
        history = client.get("/api/history").json["items"]
        self.assertTrue(any(i["report_id"] == result["report"]["report_id"] and i["has_pdf"] for i in history))

    def test_same_day_reports_never_overwrite(self):
        client = server.app.test_client()
        paths = []
        for time, note in (("08:00", "premier"), ("16:30", "second"), ("16:30", "regénéré")):
            r = client.post("/api/report", data={"data": json.dumps(dict(
                REPORT, controller="Même Jour", control_time=time, observations=note))})
            self.assertEqual(r.status_code, 200, r.json)
            paths.append(resolve_stored_path(db_service.get_pdf_path(r.json["report"]["report_id"])))
        self.assertEqual(len({p.name for p in paths}), 3)
        self.assertIn("_08h00_", paths[0].name)
        self.assertTrue(all(p.is_file() for p in paths))

    def test_interrupted_write_leaves_nothing(self):
        directory = Path(TEMP.name) / "write"
        directory.mkdir()
        original = file_service.os.fsync

        def fail(_fd):
            raise OSError("disque plein")

        file_service.os.fsync = fail
        try:
            with self.assertRaises(OSError):
                file_service.write_new_file(directory, "rapport", "pdf", b"x" * 1000)
        finally:
            file_service.os.fsync = original
        self.assertEqual(list(directory.iterdir()), [])
        first = file_service.write_new_file(directory, "rapport", "pdf", b"1")
        second = file_service.write_new_file(directory, "rapport", "pdf", b"2")
        self.assertEqual((first.read_bytes(), second.read_bytes()), (b"1", b"2"))

    def test_stored_paths(self):
        target = USER_DIR / "reports" / "2026-01" / "Lyon" / "a.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF")
        self.assertEqual(file_service.to_stored_path(target), "reports/2026-01/Lyon/a.pdf")
        self.assertEqual(resolve_stored_path("reports/2026-01/Lyon/a.pdf"), target)
        # Dossier de données restauré ailleurs / autre utilisateur Windows.
        for old in (r"C:\Users\Ancien\AppData\Local\ControleAgences\reports\2026-01\Lyon\a.pdf",
                    "/ancien/dossier/reports/2026-01/Lyon/a.pdf"):
            self.assertEqual(resolve_stored_path(old), target)
        self.assertIsNone(resolve_stored_path(""))

    def test_history_failure_is_reported(self):
        original = db_service.insert_control
        db_service.insert_control = lambda record: None
        try:
            r = server.app.test_client().post("/api/report", data={"data": json.dumps(REPORT)})
        finally:
            db_service.insert_control = original
        self.assertEqual(r.status_code, 400)
        self.assertIn("historique", r.json["error"])

    def test_corrupt_database_refuses_start(self):
        bad = Path(TEMP.name) / "corrompu.db"
        bad.write_bytes(b"pas une base" * 100)
        original = db_service.DB_PATH
        db_service.DB_PATH = bad
        try:
            with self.assertRaises(StartupError):
                db_service.init_db()
        finally:
            db_service.DB_PATH = original
        self.assertEqual(bad.read_bytes(), b"pas une base" * 100)


class LocalAccess(unittest.TestCase):
    def setUp(self):
        server._allowed_hosts.update({"127.0.0.1:8600", "localhost:8600"})
        self.client = server.app.test_client()

    def tearDown(self):
        server._allowed_hosts.clear()

    def test_host_and_origin(self):
        ok = self.client.get("/api/identity", base_url="http://127.0.0.1:8600")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json["instance"], server.INSTANCE_ID)
        self.assertEqual(self.client.get("/api/identity", base_url="http://evil.example:8600").status_code, 403)
        cross = self.client.post("/api/report", base_url="http://127.0.0.1:8600",
                                 headers={"Origin": "http://evil.example"}, data={"data": "{}"})
        self.assertEqual(cross.status_code, 403)
        same = self.client.post("/api/excel/state", base_url="http://127.0.0.1:8600",
                                headers={"Origin": "http://127.0.0.1:8600"}, json={})
        self.assertEqual(same.status_code, 200)

    def test_frontend_does_not_probe_files(self):
        outside = self.client.get("/../../server.py", base_url="http://127.0.0.1:8600")
        self.assertNotIn(b"def main", outside.data)


class Instance(unittest.TestCase):
    def test_probe_ignores_foreign_services(self):
        import socket

        for reply in (b"SSH-2.0-OpenSSH\r\n",
                      b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\n[1]"):
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            s.listen()
            port = s.getsockname()[1]

            def answer():
                c, _ = s.accept()
                c.recv(1024)
                c.sendall(reply)
                c.close()

            t = threading.Thread(target=answer)
            t.start()
            self.assertIsNone(instance_service.probe("127.0.0.1", port))
            t.join()
            s.close()

    def test_lock_is_exclusive(self):
        path = Path(TEMP.name) / "test.lock"
        lock = instance_service.InstanceLock(path)
        self.assertTrue(lock.acquire())
        code = ("import sys; sys.path.insert(0, %r); from pathlib import Path; "
                "from services.instance_service import InstanceLock; "
                "sys.exit(0 if not InstanceLock(Path(%r)).acquire() else 1)" % (str(ROOT), str(path)))
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


@unittest.skipIf(sys.platform == "win32",
                 "Migration V4 hors périmètre pour une installation neuve ; "
                 "défaut connu sous Windows (voir WINDOWS_V5.md).")
class LegacyMigration(unittest.TestCase):
    def test_migration(self):
        client = server.app.test_client()
        r = client.post("/api/report", data={"data": json.dumps(dict(REPORT, control_time="07:00")),
                                             "files": (png(), "scan.png")})
        self.assertEqual(r.status_code, 200)
        source = Path(TEMP.name) / "v4"
        source.mkdir()
        for name in ("data", "reports", "uploads"):
            subprocess.run([sys.executable, "-c",
                            "import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2])",
                            str(USER_DIR / name), str(source / name)], check=True)
        with tempfile.TemporaryDirectory() as target:
            destination = Path(target) / "migrated"
            migrate(source, destination)
            con = sqlite3.connect(destination / "data" / "controles.db")
            try:
                count = con.execute("SELECT count(*) FROM controls").fetchone()[0]
            finally:
                con.close()
            self.assertGreaterEqual(count, 1)
            with self.assertRaises(ValueError):
                migrate(source, destination)


if __name__ == "__main__":
    unittest.main()
