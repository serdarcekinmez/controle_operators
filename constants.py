"""
Constantes et configuration centrale de l'application.

Tout ce qui est "fixe" (titres, liste des agences, items de contrôle,
chemins des dossiers) est regroupé ici afin d'éviter la dispersion
de ces valeurs dans le reste du code.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys

# --------------------------------------------------------------------------- #
# Identité de l'application
# --------------------------------------------------------------------------- #
APP_TITLE = "Contrôle des agences"
APP_SUBTITLE = "Contrôle niveau 1"

# --------------------------------------------------------------------------- #
# Chemins (tous relatifs à la racine du projet)
# --------------------------------------------------------------------------- #
BASE_DIR: Path = Path(__file__).resolve().parent

USER_DIR = Path(os.environ.get("CONTROLE_AGENCES_DATA_DIR") or (str(Path(os.environ["LOCALAPPDATA"]) / "ControleAgences") if getattr(sys, "frozen", False) else str(BASE_DIR))).resolve()

DATA_DIR: Path = USER_DIR / "data"
REPORTS_DIR: Path = USER_DIR / "reports"
UPLOADS_DIR: Path = USER_DIR / "uploads"
LOGS_DIR: Path = USER_DIR / "logs"

DB_PATH: Path = DATA_DIR / "controles.db"
LOG_PATH: Path = LOGS_DIR / "app.log"

CONFIG_PATH: Path = USER_DIR / "config.json"

# Dossiers à créer automatiquement au démarrage.
REQUIRED_DIRS = (DATA_DIR, REPORTS_DIR, UPLOADS_DIR, LOGS_DIR)

# --------------------------------------------------------------------------- #
# Liste des agences (triée alphabétiquement, capitalisation propre)
# --------------------------------------------------------------------------- #
BRANCHES: list[str] = sorted(
    [
        "Argenteuil",
        "Athens",
        "Aubervilliers",
        "Belleville",
        "Canebiere",
        "CDG-TGV",
        "Choisy",
        "Davout",
        "Dezobry",
        "Dormoy",
        "Gabriel Péri",
        "Hermel",
        "Lescot",
        "Lille",
        "Lyon",
        "Magenta",
        "Montreuil",
        "Rennes",
        "Rivoli",
        "St Michel",
        "Tolbiac",
        "Toulouse",
        "Voltaire",
    ],
    key=str.casefold,
)

# --------------------------------------------------------------------------- #
# Items du contrôle niveau 1
# Chaque item = (clé technique / colonne SQLite, libellé affiché en français)
# L'ordre de cette liste est l'ordre d'affichage dans l'UI, le PDF et l'email.
# --------------------------------------------------------------------------- #
CONTROL_ITEMS: list[tuple[str, str]] = [
    ("controle_journee_comptable", "Contrôle journée comptable"),
    ("controle_caisses", "Contrôle caisses"),
    ("controle_acr", "Contrôle ACR"),
    ("controle_affichage", "Contrôle affichage"),
    ("controle_cash", "Contrôle cash"),
]

# Clés techniques uniquement (pratique pour les boucles)
CONTROL_KEYS: list[str] = [key for key, _ in CONTROL_ITEMS]

# --------------------------------------------------------------------------- #
# Statuts d'un point de contrôle (logique tri-état)
#   "ok"      -> conforme (vert)
#   "problem" -> anomalie constatée (rouge), commentaire requis
#   ""/None   -> non renseigné
# --------------------------------------------------------------------------- #
STATUS_OK = "ok"
STATUS_PROBLEM = "problem"

# Libellés affichés (PDF, email, UI). La clé "" couvre aussi None via .get().
STATUS_DISPLAY: dict[str, str] = {
    STATUS_OK: "OK",
    STATUS_PROBLEM: "Anomalie",
    "": "Non renseigné",
}


def status_label(status: str | None) -> str:
    """Retourne le libellé français d'un statut (gère None)."""
    return STATUS_DISPLAY.get(status or "", "Non renseigné")

# --------------------------------------------------------------------------- #
# Téléversement de fichiers
# --------------------------------------------------------------------------- #
ALLOWED_UPLOAD_EXTENSIONS = ("pdf", "jpg", "jpeg", "png")
IMAGE_EXTENSIONS = ("jpg", "jpeg", "png")

# Taille max d'une image (px) avant redimensionnement de sécurité.
MAX_IMAGE_DIMENSION = 2200

# --------------------------------------------------------------------------- #
# Fichier de contrôle Excel (.xlsx, conservé par chaque contrôleur)
# --------------------------------------------------------------------------- #
# Onglet du classeur qui contient les contrôles (les autres onglets sont
# laissés intacts).
EXCEL_SHEET_NAME = "Controles"

# Fin du nom de fichier téléchargé quand le contrôleur n'est pas connu
# (sinon : « AAMMJJ - Prénom.xlsx »).
EXCEL_DEFAULT_STEM = "Controles"

# Colonnes de l'onglet, dans l'ordre. Les en-têtes du fichier sont les
# libellés de SHEET_COLUMN_LABELS. Un contrôle est identifié par sa date,
# son heure et son contrôleur (voir excel_service.row_key) ; la « Réf. »
# permet de le reconnaître d'un fichier à l'autre.
SHEET_COLUMNS: list[str] = [
    "report_id",
    "date_controle",
    "heure_controle",
    "agence",
    "controleur",
    "journee_comptable",
    "caisses",
    "acr",
    "affichage",
    "cash",
    "nb_problemes",
    "observations",
    "fichier_pdf",
    "email_envoye",
]

# Correspondance : clé technique du point de contrôle -> colonne du fichier.
CONTROL_KEY_TO_SHEET_COLUMN: dict[str, str] = {
    "controle_journee_comptable": "journee_comptable",
    "controle_caisses": "caisses",
    "controle_acr": "acr",
    "controle_affichage": "affichage",
    "controle_cash": "cash",
}

# Libellés lisibles : en-têtes du fichier Excel et du tableau de consultation.
SHEET_COLUMN_LABELS: dict[str, str] = {
    "report_id": "Réf.",
    "date_controle": "Date",
    "heure_controle": "Heure",
    "agence": "Agence",
    "controleur": "Contrôleur",
    "journee_comptable": "Journée comptable",
    "caisses": "Caisses",
    "acr": "ACR",
    "affichage": "Affichage",
    "cash": "Cash",
    "nb_problemes": "Anomalies",
    "observations": "Observations",
    "fichier_pdf": "Fichier PDF",
    "email_envoye": "E-mail",
}

# Ancienne colonne « Enregistré le » (date + heure d'enregistrement) des
# fichiers créés avant la colonne « Heure » : son heure est reprise dans
# « Heure », puis la colonne est retirée.
SHEET_LEGACY_TIMESTAMP_LABELS: tuple[str, ...] = ("horodatage", "Enregistré le")

# Valeur inscrite dans le fichier pour un point conforme.
SHEET_VALUE_OK = "RAS"
SHEET_VALUE_EMPTY = "Non renseigné"
SHEET_PROBLEM_PREFIX = "ANOMALIE"
# Préfixe utilisé avant le passage à « Anomalie » : d'anciennes lignes
# le portent encore, on le reconnaît toujours pour la mise en couleur.
SHEET_PROBLEM_PREFIXES: tuple[str, ...] = (SHEET_PROBLEM_PREFIX, "PROBLÈME")


def sheet_cell_value(status: str | None, comment: str | None = None) -> str:
    """
    Valeur d'une colonne de contrôle dans le fichier Excel.

    - statut "ok"      -> "RAS"
    - statut "problem" -> "ANOMALIE — {commentaire}"
    - non renseigné    -> "Non renseigné"
    """
    if status == STATUS_OK:
        return SHEET_VALUE_OK
    if status == STATUS_PROBLEM:
        detail = (comment or "").strip()
        return f"{SHEET_PROBLEM_PREFIX} — {detail}" if detail else SHEET_PROBLEM_PREFIX
    return SHEET_VALUE_EMPTY
