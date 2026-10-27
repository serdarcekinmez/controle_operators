import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
os.environ["CONTROLE_AGENCES_DATA_DIR"] = TEMP.name
sys.path.insert(0, str(ROOT))
import server
from services import db_service
from services.file_service import ensure_directories
from pypdf import PdfReader
from PIL import Image
from migrate_data import migrate


class Workflow(unittest.TestCase):
    def test_report_excel_persistence(self):
        ensure_directories()
        db_service.init_db()
        client = server.app.test_client()
        report = dict(branch=server.BRANCHES[0], controller="V5 test",
                      control_date="2026-10-27", control_time="12:00")
        image = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(image, format="PNG")
        image.seek(0)
        response = client.post("/api/report", data={"data": json.dumps(report), "files": (image, "scan.png")})
        self.assertEqual(response.status_code, 200)
        result = response.json
        with client.get(result["url"]) as pdf_response:
            self.assertEqual(len(PdfReader(io.BytesIO(pdf_response.data)).pages), 2)
        excel = client.post("/api/excel/save", json={"report": report}).json
        self.assertEqual(excel["total"], 1)
        reopened = client.post("/api/excel/state", json={"base": excel["workbook"]}).json
        self.assertEqual(reopened["total"], 1)
        code = "from services import db_service; assert len(db_service.get_recent_controls()) == 1"
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
        with client.get("/") as frontend_response:
            self.assertEqual(frontend_response.status_code, 200)
        with tempfile.TemporaryDirectory() as target:
            destination = Path(target) / "migrated"
            migrate(TEMP.name, destination)
            env = dict(os.environ, CONTROLE_AGENCES_DATA_DIR=str(destination))
            subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True)
            self.assertTrue(list((destination / "reports").rglob("*.pdf")))
            self.assertTrue(list((destination / "uploads").rglob("*.png")))
            with self.assertRaises(ValueError):
                migrate(TEMP.name, destination)


if __name__ == "__main__":
    unittest.main()
