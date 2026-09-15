"""
Service Google Sheets / Drive via la passerelle Apps Script.

Aucune dépendance supplémentaire : tout passe par la bibliothèque standard
(urllib). La passerelle est une « application web » Apps Script déployée
depuis le classeur du compte d'archivage ; son URL et son jeton sont lus
depuis config.json (jamais versionné).

Toutes les fonctions lèvent SheetsError avec un message déjà rédigé pour
l'utilisateur final. Aucune ne fait planter l'application : l'appelant
décide quoi afficher.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import PurePath

from constants import (
    CONTROL_KEY_TO_SHEET_COLUMN,
    SHEETS_CONFIG_KEYS,
    SHEETS_TIMEOUT,
    SHEETS_UPLOAD_TIMEOUT,
    STATUS_PROBLEM,
    sheet_cell_value,
)
from services.logging_service import get_logger

logger = get_logger()


class SheetsError(Exception):
    """Erreur de synchronisation, avec un message adapté à l'utilisateur."""


@dataclass
class SyncResult:
    """Résultat d'un envoi de lignes vers la feuille."""

    added: int
    updated: int

    @property
    def total(self) -> int:
        return self.added + self.updated


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(
        token in lowered
        for token in ("remplacez", "xxxx", "votre", "example", "placeholder")
    )


def is_configured(config: dict | None) -> bool:
    """Vrai si l'URL et le jeton de la passerelle sont renseignés."""
    if not config:
        return False
    for key in SHEETS_CONFIG_KEYS:
        value = config.get(key, "")
        if not isinstance(value, str) or _looks_like_placeholder(value):
            return False
    return str(config.get("sheets_webapp_url", "")).startswith("https://")


def _credentials(config: dict | None) -> tuple[str, str]:
    if not is_configured(config):
        raise SheetsError(
            "La liaison Google Sheets n'est pas configurée. Renseignez "
            "« sheets_webapp_url » et « sheets_token » dans config.json "
            "(voir le README, section Google Sheets)."
        )
    assert config is not None
    return str(config["sheets_webapp_url"]).strip(), str(config["sheets_token"]).strip()


# --------------------------------------------------------------------------- #
# Appels HTTP
# --------------------------------------------------------------------------- #
def _read_json(response) -> dict:
    raw = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Réponse non-JSON de la passerelle : %s", raw[:400])
        raise SheetsError(
            "La passerelle Google a renvoyé une réponse inattendue. "
            "Vérifiez que le déploiement est bien accessible « à tout le "
            "monde » et que l'URL se termine par /exec."
        ) from exc


def _handle_network_error(exc: Exception) -> SheetsError:
    if isinstance(exc, urllib.error.HTTPError):
        logger.error("Erreur HTTP de la passerelle : %s", exc)
        return SheetsError(
            f"La passerelle Google a répondu par une erreur ({exc.code}). "
            "Vérifiez l'URL de déploiement dans config.json."
        )
    logger.error("Appel de la passerelle impossible : %s", exc)
    return SheetsError(
        "Connexion à Google impossible. Vérifiez votre accès internet "
        "(ou le pare-feu / proxy de l'entreprise), puis réessayez. "
        "Les contrôles non synchronisés restent enregistrés localement."
    )


def _post(config: dict | None, payload: dict, *, timeout: int) -> dict:
    url, token = _credentials(config)
    body = json.dumps({**payload, "token": token}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = _read_json(response)
    except (urllib.error.URLError, OSError) as exc:
        raise _handle_network_error(exc) from exc

    if not data.get("ok"):
        raise SheetsError(
            f"Google a refusé l'opération : {data.get('error', 'raison inconnue')}"
        )
    return data


def _get(config: dict | None, params: dict, *, timeout: int) -> dict:
    url, token = _credentials(config)
    query = urllib.parse.urlencode({**params, "token": token})
    try:
        with urllib.request.urlopen(f"{url}?{query}", timeout=timeout) as response:
            data = _read_json(response)
    except (urllib.error.URLError, OSError) as exc:
        raise _handle_network_error(exc) from exc

    if not data.get("ok"):
        raise SheetsError(
            f"Google a refusé la lecture : {data.get('error', 'raison inconnue')}"
        )
    return data


# --------------------------------------------------------------------------- #
# API du service
# --------------------------------------------------------------------------- #
def build_sheet_row(control) -> dict:
    """
    Convertit un enregistrement de la base locale en ligne de feuille.

    `control` est une ligne SQLite (ou tout objet indexable par nom de
    colonne). Chaque point de contrôle devient une colonne contenant
    « RAS », « PROBLÈME — commentaire » ou « Non renseigné ».
    """
    try:
        comments = json.loads(control["problem_comments"] or "{}")
    except (json.JSONDecodeError, TypeError):
        comments = {}

    row: dict[str, str] = {
        "report_id": control["report_id"] or "",
        "horodatage": control["created_at"] or "",
        "date_controle": control["control_date"] or "",
        "agence": control["branch_name"] or "",
        "controleur": control["controller_name"] or "",
        "observations": (control["observations"] or "").strip(),
        "fichier_pdf": PurePath(control["pdf_path"] or "").name,
        "lien_drive": control["drive_url"] or "",
        "email_envoye": "Oui" if control["email_sent"] else "Non",
    }

    problems = 0
    for key, column in CONTROL_KEY_TO_SHEET_COLUMN.items():
        status = control[key] or ""
        row[column] = sheet_cell_value(status, comments.get(key))
        if status == STATUS_PROBLEM:
            problems += 1
    row["nb_problemes"] = str(problems)

    return row


def ping(config: dict | None) -> str:
    """Test de liaison : retourne le nom de la feuille cible."""
    data = _get(config, {"action": "ping"}, timeout=SHEETS_TIMEOUT)
    return str(data.get("sheet", ""))


def push_rows(config: dict | None, rows: list[dict]) -> SyncResult:
    """
    Envoie des lignes vers la feuille (ajout, ou mise à jour si le
    report_id existe déjà). Retourne le détail ajouts / mises à jour.
    """
    if not rows:
        return SyncResult(added=0, updated=0)
    data = _post(
        config, {"action": "append", "rows": rows}, timeout=SHEETS_TIMEOUT
    )
    return SyncResult(
        added=int(data.get("added", 0)), updated=int(data.get("updated", 0))
    )


def upload_pdf(
    config: dict | None, report_id: str, filename: str, pdf_bytes: bytes
) -> str:
    """Dépose le PDF dans le Drive du compte d'archivage, retourne son lien."""
    if not pdf_bytes:
        raise SheetsError("Le PDF est vide : rien à déposer sur le Drive.")
    payload = {
        "action": "upload_pdf",
        "report_id": report_id,
        "filename": filename,
        "content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
    }
    data = _post(config, payload, timeout=SHEETS_UPLOAD_TIMEOUT)
    return str(data.get("url", ""))


def query_rows(
    config: dict | None,
    *,
    branches: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """
    Relit les contrôles de la feuille.

    - branches vide/None -> toutes les agences
    - dates au format AAAA-MM-JJ (bornes incluses), facultatives
    """
    params: dict[str, str] = {"action": "query"}
    if branches:
        params["branches"] = "|".join(branches)
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    data = _get(config, params, timeout=SHEETS_TIMEOUT)
    rows = data.get("rows", [])
    return rows if isinstance(rows, list) else []
