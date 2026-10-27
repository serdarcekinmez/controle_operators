"""
Application de contrôle agences — Contrôle niveau 1 (V4).

Serveur LOCAL (poste de travail) : il sert l'interface React déjà construite
(frontend/dist) et une petite API JSON qui réutilise les services Python
(PDF, fichier de contrôle Excel, historique SQLite). Il n'écoute que sur
127.0.0.1 : rien n'est exposé sur le réseau.

Le serveur ne garde aucun état de session : le navigateur conserve le
fichier de contrôle Excel chargé (ou un accès direct au fichier sur le
disque), les contrôles enregistrés pendant la séance et les suppressions,
et les renvoie à chaque appel. Le classeur à jour est recalculé à partir de
ces trois éléments, comme dans la V3.

Lancement : RUN_APP.bat (ou « python server.py »).
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import io
import json
import logging
import os
import socket
import sys
import threading
import webbrowser
import time
import urllib.request
from version import VERSION
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from pypdf import PdfReader

from constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    APP_SUBTITLE,
    APP_TITLE,
    BASE_DIR,
    BRANCHES,
    CONTROL_ITEMS,
    CONTROL_KEYS,
    REPORTS_DIR,
    SHEET_COLUMN_LABELS,
    SHEET_COLUMNS,
    SHEET_PROBLEM_PREFIXES,
    SHEET_VALUE_OK,
    STATUS_OK,
    STATUS_PROBLEM,
)
from services import db_service, excel_service
from services.config_service import load_config
from services.excel_service import ExcelError
from services.file_service import (
    ensure_directories,
    get_extension,
    is_allowed_upload,
    is_image,
    save_report_pdf,
    save_uploaded_file,
)
from services.logging_service import get_logger
from services.pdf_service import (
    Attachment,
    ReportMetadata,
    build_final_report,
    image_to_pdf_bytes,
)

logger = get_logger()

HOST = "127.0.0.1"
PORTS = (8600, 8601, 8602)
APP_ID = "fr.controle-agences.desktop"

DIST_DIR: Path = BASE_DIR / "frontend" / "dist"

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

app = Flask(__name__, static_folder=None)
# Documents scannés : quelques dizaines de Mo au plus.
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
app.json.ensure_ascii = False


class ApiError(Exception):
    """Erreur à afficher telle quelle à l'utilisateur (HTTP 400)."""


@app.errorhandler(ApiError)
@app.errorhandler(ExcelError)
def _user_error(exc: Exception):
    return jsonify(error=str(exc)), 400


@app.errorhandler(413)
def _too_large(_exc):
    return jsonify(error="Les documents envoyés sont trop volumineux (80 Mo au plus)."), 413


@app.errorhandler(Exception)
def _unexpected(exc: Exception):
    # Les erreurs HTTP de Flask (404...) gardent leur code.
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code < 500:
        return jsonify(error=str(exc)), code
    logger.exception("Erreur inattendue sur %s", request.path)
    return jsonify(
        error="Une erreur inattendue est survenue. Le détail technique est "
        "dans le fichier logs/app.log."
    ), 500


# --------------------------------------------------------------------------- #
# Outils
# --------------------------------------------------------------------------- #
def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str | None) -> bytes | None:
    if not text:
        return None
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError("Le fichier Excel transmis est illisible.") from exc


def _json_body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _fr_date(iso: str) -> str:
    """AAAA-MM-JJ -> JJ/MM/AAAA (texte laissé tel quel s'il est différent)."""
    try:
        return dt.date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


# --------------------------------------------------------------------------- #
# Contrôle saisi
# --------------------------------------------------------------------------- #
def _report_from(data) -> dict:
    """Contrôle reçu du navigateur, au format attendu par excel_service.build_row."""
    data = data if isinstance(data, dict) else {}
    raw_statuses = data.get("statuses") if isinstance(data.get("statuses"), dict) else {}
    raw_comments = (
        data.get("problem_comments") if isinstance(data.get("problem_comments"), dict) else {}
    )
    statuses = {}
    for key in CONTROL_KEYS:
        status = str(raw_statuses.get(key) or "")
        statuses[key] = status if status in (STATUS_OK, STATUS_PROBLEM) else ""
    return {
        "report_id": str(data.get("report_id") or "") or db_service.new_report_id(),
        "control_date": str(data.get("control_date") or "").strip(),
        "control_time": str(data.get("control_time") or "").strip()[:5],
        "branch": str(data.get("branch") or "").strip(),
        "controller": str(data.get("controller") or "").strip(),
        "statuses": statuses,
        "problem_comments": {
            key: str(raw_comments.get(key) or "").strip()
            for key in CONTROL_KEYS
            if statuses[key] == STATUS_PROBLEM
        },
        "observations": str(data.get("observations") or ""),
        "filename": str(data.get("filename") or ""),
        "email_sent": False,
    }


def _report_errors(report: dict) -> list[str]:
    """Messages d'erreur du contrôle (liste vide si tout est correct)."""
    missing = []
    if not report["controller"]:
        missing.append("le nom du contrôleur")
    if not report["branch"]:
        missing.append("l'agence")
    try:
        dt.date.fromisoformat(report["control_date"])
    except ValueError:
        missing.append("la date du contrôle")
    try:
        dt.time.fromisoformat(report["control_time"])
    except ValueError:
        missing.append("l'heure du contrôle")
    if missing:
        return ["Champs obligatoires manquants : " + ", ".join(missing) + "."]
    if report["branch"] not in BRANCHES:
        return [f"Agence inconnue : {report['branch']}."]

    uncommented = [
        label
        for key, label in CONTROL_ITEMS
        if report["statuses"][key] == STATUS_PROBLEM and not report["problem_comments"].get(key)
    ]
    if uncommented:
        return [
            "Un commentaire est obligatoire pour chaque anomalie signalée : "
            + ", ".join(uncommented) + "."
        ]
    return []


def _conflict_error(report: dict, rows: list[dict]) -> str:
    """
    Date + heure + contrôleur identifient un contrôle : un contrôle d'une
    autre agence au même moment serait écrasé.
    """
    key = (
        report["control_date"],
        report["control_time"],
        excel_service.normalize_name(report["controller"]),
    )
    for row in rows:
        if excel_service.row_key(row) == key and row.get("agence") != report["branch"]:
            return (
                f"Le fichier Excel contient déjà un contrôle de {report['controller']} "
                f"le {_fr_date(key[0])} à {key[1]} (agence {row.get('agence')}). "
                "Corrigez l'heure du contrôle."
            )
    return ""


# --------------------------------------------------------------------------- #
# Fichier de contrôle Excel
# --------------------------------------------------------------------------- #
def _excel_input(body: dict) -> tuple[bytes | None, list[dict], set[tuple]]:
    """Fichier chargé, contrôles de la séance et suppressions envoyés par le navigateur."""
    base = _unb64(body.get("base"))
    session_rows = [
        {column: str(row.get(column) or "") for column in SHEET_COLUMNS}
        for row in body.get("session_rows") or []
        if isinstance(row, dict)
    ]
    deleted = {
        tuple(str(part) for part in key)
        for key in body.get("deleted") or []
        if isinstance(key, list) and len(key) == 3
    }
    return base, session_rows, deleted


def _excel_state(
    base: bytes | None, session_rows: list[dict], deleted: set[tuple], create: bool
) -> dict:
    """
    Classeur à jour : fichier chargé + contrôles de la séance - suppressions.

    workbook vaut None tant qu'il n'y a ni fichier, ni contrôle, ni demande
    de création d'un nouveau fichier.
    """
    state = {
        "session_rows": session_rows,
        "deleted": [list(key) for key in sorted(deleted)],
        "workbook": None,
        "rows": [],
        "base_count": len(excel_service.read_rows(base)) if base is not None else 0,
        "total": 0,
        "last": "",
    }
    if base is None and not session_rows and not create:
        return state
    data = excel_service.update_workbook(base, session_rows, deleted)
    rows = excel_service.read_rows(data)
    state["total"], state["last"] = excel_service.summarize(rows)
    state.update(workbook=_b64(data), rows=rows)
    return state


@app.post("/api/excel/state")
def excel_state():
    """Recalcule le classeur (chargement d'un fichier, création d'un fichier)."""
    body = _json_body()
    base, session_rows, deleted = _excel_input(body)
    return jsonify(_excel_state(base, session_rows, deleted, bool(body.get("create"))))


@app.post("/api/excel/save")
def excel_save():
    """« Enregistrer dans Excel » : ajoute (ou met à jour) le contrôle saisi."""
    body = _json_body()
    base, session_rows, deleted = _excel_input(body)
    report = _report_from(body.get("report"))
    errors = _report_errors(report)
    if errors:
        raise ApiError(" ".join(errors))

    current = _excel_state(base, session_rows, deleted, create=False)["rows"]
    conflict = _conflict_error(report, current)
    if conflict:
        raise ApiError(conflict)

    # Un contrôle déjà enregistré (même date, heure et contrôleur) garde sa
    # « Réf. » et son nom de PDF.
    row = excel_service.build_row(report)
    key = excel_service.row_key(row)
    previous = next(
        (r for r in [*session_rows, *current] if excel_service.row_key(r) == key), None
    )
    if previous:
        row["report_id"] = previous.get("report_id") or row["report_id"]
        row["fichier_pdf"] = row["fichier_pdf"] or previous.get("fichier_pdf", "")
    session_rows = [r for r in session_rows if excel_service.row_key(r) != key] + [row]
    deleted.discard(key)

    state = _excel_state(base, session_rows, deleted, create=True)
    state["row"] = row
    return jsonify(state)


@app.post("/api/excel/delete")
def excel_delete():
    """Retire un contrôle (date, heure, contrôleur) du fichier."""
    body = _json_body()
    base, session_rows, deleted = _excel_input(body)
    controller = str(body.get("controller") or "").strip()
    date, time = str(body.get("date") or ""), str(body.get("time") or "")[:5]
    if not controller or not date or not time:
        raise ApiError("Renseignez la date, l'heure et le nom du contrôleur à supprimer.")

    key = (date, time, excel_service.normalize_name(controller))
    label = f"{_fr_date(date)} à {time} — {controller}"
    current = _excel_state(base, session_rows, deleted, create=False)["rows"]
    matches = [row for row in current if excel_service.row_key(row) == key]
    if not matches:
        raise ApiError(
            f"Aucun contrôle trouvé dans le fichier pour : {label}. Vérifiez la "
            "date, l'heure (colonne « Heure ») et le nom du contrôleur."
        )
    session_rows = [r for r in session_rows if excel_service.row_key(r) != key]
    deleted.add(key)

    state = _excel_state(base, session_rows, deleted, create=True)
    state["removed"] = matches
    return jsonify(state)


@app.post("/api/excel/export")
def excel_export():
    """Classeur contenant les contrôles affichés dans la consultation."""
    rows = [
        {column: str(row.get(column) or "") for column in SHEET_COLUMNS}
        for row in _json_body().get("rows") or []
        if isinstance(row, dict)
    ]
    data = excel_service.build_workbook(rows)
    return send_file(io.BytesIO(data), mimetype=_XLSX_MIME, download_name="export.xlsx")


@app.post("/api/audit")
def audit():
    """
    Contrôles consultables : tous les fichiers envoyés, sans doublon.

    Un même contrôle présent dans plusieurs fichiers n'est compté qu'une
    fois (même « Réf. ») ; la version du dernier fichier l'emporte.
    """
    by_ref: dict = {}
    warnings: list[str] = []
    for source in _json_body().get("sources") or []:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or "fichier")
        try:
            rows = excel_service.read_rows(_unb64(source.get("data")) or b"")
        except (ExcelError, ApiError) as exc:
            warnings.append(f"« {name} » ignoré : {exc}")
            continue
        for row in rows:
            by_ref[row.get("report_id") or tuple(row.values())] = row
    rows = sorted(by_ref.values(), key=excel_service.sort_key, reverse=True)
    return jsonify(rows=rows, warnings=warnings)


# --------------------------------------------------------------------------- #
# Rapport PDF
# --------------------------------------------------------------------------- #
@app.post("/api/attachments/check")
def check_attachment():
    """Vérifie dès l'ajout qu'un document pourra être intégré au PDF final."""
    upload = request.files.get("file")
    if upload is None:
        raise ApiError("Aucun fichier reçu.")
    name = upload.filename or "document"
    if not is_allowed_upload(name):
        return jsonify(ok=False, error="Format non accepté (PDF, JPG, JPEG ou PNG).")
    data = upload.read()
    try:
        if is_image(name):
            image_to_pdf_bytes(data)
            return jsonify(ok=True, kind="image", pages=1)
        return jsonify(ok=True, kind="pdf", pages=len(PdfReader(io.BytesIO(data)).pages))
    except Exception as exc:
        logger.warning("Document illisible : %s (%s)", name, exc)
        return jsonify(ok=False, error="Fichier illisible ou corrompu : il sera ignoré.")


@app.post("/api/report")
def create_report():
    """Crée le PDF final (rapport + documents), l'enregistre et l'historise."""
    try:
        data = json.loads(request.form.get("data") or "{}")
    except json.JSONDecodeError as exc:
        raise ApiError("Données du formulaire illisibles.") from exc
    report = _report_from(data)
    errors = _report_errors(report)
    if errors:
        raise ApiError(" ".join(errors))

    warnings: list[str] = []
    attachments: list[Attachment] = []
    for upload in request.files.getlist("files"):
        name = upload.filename or "document"
        if not is_allowed_upload(name):
            warnings.append(f"Format non accepté, fichier ignoré : {name}")
            logger.warning("Fichier rejeté (format) : %s", name)
            continue
        attachments.append(Attachment(filename=name, data=upload.read()))

    control_date = dt.date.fromisoformat(report["control_date"])
    meta = ReportMetadata(
        branch=report["branch"],
        control_date=f"{_fr_date(report['control_date'])} à {report['control_time']}",
        controller=report["controller"],
        generated_at=dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        statuses=report["statuses"],
        problem_comments=report["problem_comments"],
        observations=report["observations"],
        attachment_names=[a.filename for a in attachments],
    )
    result = build_final_report(meta, attachments)
    warnings += result.errors

    try:
        pdf_path = save_report_pdf(
            result.pdf_bytes, report["branch"], control_date, report["controller"]
        )
    except OSError as exc:
        logger.exception("Écriture du PDF final impossible.")
        raise ApiError(
            "Le PDF a été généré mais n'a pas pu être enregistré sur le poste "
            "(droits ou disque plein). Consultez logs/app.log."
        ) from exc

    stored_uploads: list[tuple[str, str, str]] = []
    for att in attachments:
        try:
            stored = save_uploaded_file(att.data, att.filename, report["branch"], control_date)
            stored_uploads.append((att.filename, str(stored), get_extension(att.filename)))
        except OSError:
            logger.exception("Sauvegarde du fichier téléversé impossible : %s", att.filename)

    control_id = db_service.insert_control(
        db_service.ControlRecord(
            branch_name=report["branch"],
            controller_name=report["controller"],
            control_date=report["control_date"],
            statuses=report["statuses"],
            observations=report["observations"],
            pdf_path=str(pdf_path),
            problem_comments=report["problem_comments"],
            report_id=report["report_id"],
        )
    )
    if control_id is not None:
        for original, stored_path, file_type in stored_uploads:
            db_service.insert_attachment(control_id, original, stored_path, file_type)

    report["filename"] = pdf_path.name
    return jsonify(
        report=report,
        filename=pdf_path.name,
        url=f"/api/reports/{report['report_id']}",
        warnings=warnings,
    )


@app.get("/api/reports/<report_id>")
def get_report_pdf(report_id: str):
    """PDF d'un contrôle (?download=1 pour le télécharger)."""
    stored = db_service.get_pdf_path(report_id)
    path = Path(stored).resolve() if stored else None
    # On ne sert que des fichiers du dossier reports/ de l'application.
    if path is None or not path.is_file() or not path.is_relative_to(REPORTS_DIR.resolve()):
        return jsonify(error="Ce rapport PDF est introuvable sur ce poste."), 404
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=request.args.get("download") == "1",
        download_name=path.name,
    )


# --------------------------------------------------------------------------- #
# Configuration et historique
# --------------------------------------------------------------------------- #
@app.get("/api/config")
def get_config():
    config = load_config()
    return jsonify(
        title=APP_TITLE,
        subtitle=APP_SUBTITLE,
        branches=BRANCHES,
        control_items=[{"key": key, "label": label} for key, label in CONTROL_ITEMS],
        upload_extensions=list(ALLOWED_UPLOAD_EXTENSIONS),
        default_controller=str(config.get("default_controller_name") or ""),
        column_labels=SHEET_COLUMN_LABELS,
        sheet_columns=SHEET_COLUMNS,
        value_ok=SHEET_VALUE_OK,
        problem_prefixes=list(SHEET_PROBLEM_PREFIXES),
    )


@app.get("/api/history")
def history():
    """Derniers rapports PDF créés sur ce poste."""
    items = []
    for row in db_service.get_recent_controls(limit=12):
        pdf = row["pdf_path"] or ""
        items.append({
            "report_id": row["report_id"] or "",
            "branch": row["branch_name"],
            "controller": row["controller_name"],
            "control_date": row["control_date"],
            "created_at": row["created_at"],
            "has_pdf": bool(pdf) and Path(pdf).is_file(),
        })
    return jsonify(items=items)


# --------------------------------------------------------------------------- #
# Fermeture de l'application
# --------------------------------------------------------------------------- #
def _shutdown() -> None:
    """Arrête le serveur : la fenêtre noire de RUN_APP.bat se ferme."""
    logger.info("Application fermée par l'utilisateur.")
    logging.shutdown()
    os._exit(0)


@app.post("/api/quit")
def quit_app():
    """Bouton « Quitter l'application » (après confirmation dans la page)."""
    # Corps JSON exigé : un autre site ouvert dans le navigateur ne peut pas
    # envoyer cette requête sans l'accord du serveur (contrôle CORS).
    if not request.is_json:
        raise ApiError("Requête invalide.")
    # Laisse le temps à la réponse de partir avant l'arrêt.
    threading.Timer(0.5, _shutdown).start()
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
# Interface React (déjà construite dans frontend/dist)
# --------------------------------------------------------------------------- #
@app.get("/")
@app.get("/<path:path>")
def frontend(path: str = ""):
    if path.startswith("api/"):
        return jsonify(error="Adresse inconnue."), 404
    if path and (DIST_DIR / path).is_file():
        return send_from_directory(DIST_DIR, path)
    if not (DIST_DIR / "index.html").is_file():
        return (
            "<h1>Interface introuvable</h1><p>Le dossier <code>frontend/dist</code> "
            "est absent. Récupérez la version complète de l'application.</p>",
            500,
        )
    response = send_from_directory(DIST_DIR, "index.html")
    response.headers["Cache-Control"] = "no-cache"
    return response


# --------------------------------------------------------------------------- #
# Lancement
# --------------------------------------------------------------------------- #
@app.get("/api/identity")
def identity():
    return jsonify(app_id=APP_ID, version=VERSION)


def identified(port):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://{HOST}:{port}/api/identity", timeout=0.4) as response:
            value = json.loads(response.read(4096))
            return value.get("app_id") == APP_ID and value.get("version") == VERSION
    except (OSError, ValueError):
        return False


def main() -> None:
    from waitress import create_server
    open_browser = "--no-browser" not in sys.argv
    ensure_directories()
    db_service.init_db()
    if not (DIST_DIR / "index.html").is_file():
        raise RuntimeError("Interface React introuvable.")
    for port in PORTS:
        if identified(port):
            if open_browser:
                webbrowser.open(f"http://{HOST}:{port}")
            return
    for port in PORTS:
        try:
            server = create_server(app, host=HOST, port=port, threads=6)
            break
        except OSError:
            continue
    else:
        raise RuntimeError("Les ports 8600, 8601 et 8602 sont déjà utilisés. Impossible de démarrer l’application. Veuillez fermer une autre instance de Contrôle Agences si elle est ouverte, puis réessayer.")
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    try:
        for _ in range(50):
            if identified(port):
                break
            if not worker.is_alive():
                raise RuntimeError("Le serveur n’a pas pu démarrer.")
            time.sleep(0.1)
        else:
            raise RuntimeError("Le serveur ne répond pas.")
        if open_browser:
            webbrowser.open(f"http://{HOST}:{port}")
        worker.join()
    finally:
        server.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception("Échec du démarrage")
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "Contrôle Agences", 0x10)
        else:
            print(str(exc), file=sys.stderr)
        sys.exit(1)
