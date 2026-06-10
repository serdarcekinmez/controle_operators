"""
Constantes et configuration centrale de l'application.

Tout ce qui est "fixe" (titres, liste des agences, items de contrôle,
chemins des dossiers) est regroupé ici afin d'éviter la dispersion
de ces valeurs dans le reste du code.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Identité de l'application
# --------------------------------------------------------------------------- #
APP_TITLE = "Application de contrôle agences"
APP_SUBTITLE = "Contrôle niveau 1"

# --------------------------------------------------------------------------- #
# Chemins (tous relatifs à la racine du projet)
# --------------------------------------------------------------------------- #
BASE_DIR: Path = Path(__file__).resolve().parent

DATA_DIR: Path = BASE_DIR / "data"
REPORTS_DIR: Path = BASE_DIR / "reports"
UPLOADS_DIR: Path = BASE_DIR / "uploads"
LOGS_DIR: Path = BASE_DIR / "logs"

DB_PATH: Path = DATA_DIR / "controles.db"
LOG_PATH: Path = LOGS_DIR / "app.log"

CONFIG_PATH: Path = BASE_DIR / "config.json"
CONFIG_EXAMPLE_PATH: Path = BASE_DIR / "config.example.json"

# Dossiers à créer automatiquement au démarrage.
REQUIRED_DIRS = (DATA_DIR, REPORTS_DIR, UPLOADS_DIR, LOGS_DIR)

# --------------------------------------------------------------------------- #
# Liste des agences (triée alphabétiquement, capitalisation propre)
# --------------------------------------------------------------------------- #
BRANCHES: list[str] = sorted(
    [
        "Argenteuil",
        "Athens",
        "Belleville",
        "Canebiere",
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
        "Strasbourg",
        "Tolbiac",
        "Toulouse",
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
    ("controle_affichage_obligatoire", "Contrôle affichage obligatoire"),
]

# Clés techniques uniquement (pratique pour les boucles)
CONTROL_KEYS: list[str] = [key for key, _ in CONTROL_ITEMS]

# --------------------------------------------------------------------------- #
# Statuts d'un point de contrôle (logique tri-état)
#   "ok"      -> conforme (vert)
#   "problem" -> problème constaté (rouge), commentaire requis
#   ""/None   -> non renseigné
# --------------------------------------------------------------------------- #
STATUS_OK = "ok"
STATUS_PROBLEM = "problem"

# Libellés affichés (PDF, email, UI). La clé "" couvre aussi None via .get().
STATUS_DISPLAY: dict[str, str] = {
    STATUS_OK: "OK",
    STATUS_PROBLEM: "Problème",
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
# Email / SMTP
# --------------------------------------------------------------------------- #
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL

# Clés obligatoires dans config.json
REQUIRED_CONFIG_KEYS = ("smtp_email", "smtp_app_password", "recipient_email")
