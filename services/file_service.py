"""
Service de gestion des fichiers et des chemins.

- Création automatique des dossiers.
- Nettoyage (sanitization) des noms de fichiers.
- Organisation des dossiers reports/ et uploads/ par mois et par agence.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from pathlib import Path

from constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    IMAGE_EXTENSIONS,
    REPORTS_DIR,
    REQUIRED_DIRS,
    UPLOADS_DIR,
)
from services.logging_service import get_logger

logger = get_logger()


def ensure_directories() -> None:
    """Crée tous les dossiers requis s'ils n'existent pas."""
    for directory in REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def sanitize_filename(value: str, *, default: str = "inconnu") -> str:
    """
    Nettoie une chaîne pour un usage sûr dans un nom de fichier :
    minuscules, accents retirés, espaces -> underscores, caractères
    spéciaux supprimés.
    """
    if not value:
        return default

    # Retire les accents (é -> e, ô -> o, ...).
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")

    ascii_value = ascii_value.lower().strip()
    # Tout ce qui n'est pas lettre/chiffre/espace/tiret/underscore -> retiré.
    ascii_value = re.sub(r"[^\w\s-]", "", ascii_value)
    # Espaces et tirets multiples -> underscore unique.
    ascii_value = re.sub(r"[\s-]+", "_", ascii_value)
    ascii_value = re.sub(r"_+", "_", ascii_value).strip("_")

    return ascii_value or default


def get_extension(filename: str) -> str:
    """Retourne l'extension en minuscules, sans le point."""
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed_upload(filename: str) -> bool:
    """Vérifie que l'extension fait partie des formats acceptés."""
    return get_extension(filename) in ALLOWED_UPLOAD_EXTENSIONS


def is_image(filename: str) -> bool:
    """Indique si le fichier est une image (JPG/JPEG/PNG)."""
    return get_extension(filename) in IMAGE_EXTENSIONS


def build_report_filename(branch: str, control_date: dt.date, controller: str) -> str:
    """
    Construit le nom du PDF final selon le motif :
    rapport_final_controle_n1_{branch}_{date}_{controller}.pdf
    """
    safe_branch = sanitize_filename(branch, default="agence")
    safe_controller = sanitize_filename(controller, default="controleur")
    date_str = control_date.isoformat()  # YYYY-MM-DD
    return (
        f"rapport_final_controle_n1_{safe_branch}_{date_str}_{safe_controller}.pdf"
    )


def _month_branch_subdir(base: Path, branch: str, control_date: dt.date) -> Path:
    """Construit (et crée) base/AAAA-MM/Agence/."""
    month = control_date.strftime("%Y-%m")
    # On garde le nom d'agence "propre" pour les dossiers (lisible humain).
    target = base / month / branch
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_report_dir(branch: str, control_date: dt.date) -> Path:
    """reports/AAAA-MM/Agence/ (créé si besoin)."""
    return _month_branch_subdir(REPORTS_DIR, branch, control_date)


def get_upload_dir(branch: str, control_date: dt.date) -> Path:
    """uploads/AAAA-MM/Agence/ (créé si besoin)."""
    return _month_branch_subdir(UPLOADS_DIR, branch, control_date)


def save_report_pdf(
    pdf_bytes: bytes, branch: str, control_date: dt.date, controller: str
) -> Path:
    """Enregistre le PDF final dans reports/AAAA-MM/Agence/ et retourne le chemin."""
    report_dir = get_report_dir(branch, control_date)
    filename = build_report_filename(branch, control_date, controller)
    path = report_dir / filename
    path.write_bytes(pdf_bytes)
    logger.info("Rapport PDF enregistré : %s", path)
    return path


def save_uploaded_file(
    data: bytes, original_filename: str, branch: str, control_date: dt.date
) -> Path:
    """
    Enregistre un document téléversé dans uploads/AAAA-MM/Agence/.

    Le nom est nettoyé tout en conservant l'extension d'origine. En cas de
    collision, un suffixe numérique est ajouté.
    """
    upload_dir = get_upload_dir(branch, control_date)
    ext = get_extension(original_filename)
    stem = sanitize_filename(Path(original_filename).stem, default="document")

    candidate = upload_dir / f"{stem}.{ext}"
    counter = 1
    while candidate.exists():
        candidate = upload_dir / f"{stem}_{counter}.{ext}"
        counter += 1

    candidate.write_bytes(data)
    logger.info("Document téléversé enregistré : %s", candidate)
    return candidate
