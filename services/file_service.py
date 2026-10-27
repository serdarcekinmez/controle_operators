"""
Service de gestion des fichiers et des chemins.

- Création automatique des dossiers.
- Nettoyage (sanitization) des noms de fichiers.
- Organisation des dossiers reports/ et uploads/ par mois et par agence.
- Écriture sûre : un fichier existant n'est jamais écrasé, et un fichier
  n'apparaît sous son nom définitif qu'une fois entièrement écrit.
- Chemins enregistrés relatifs au dossier de données (sauvegarde/restauration
  sur un autre poste ou sous un autre nom d'utilisateur).
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
import threading
import unicodedata
import uuid
from pathlib import Path, PureWindowsPath

from constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    IMAGE_EXTENSIONS,
    REPORTS_DIR,
    REQUIRED_DIRS,
    UPLOADS_DIR,
    USER_DIR,
)
from services.logging_service import get_logger

logger = get_logger()

# Choix du nom + mise en place du fichier : une seule écriture à la fois
# (une seule instance de l'application par dossier de données).
_write_lock = threading.Lock()


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


def build_report_filename(
    branch: str, control_date: dt.date, controller: str, control_time: str = ""
) -> str:
    """
    Construit le nom du PDF final selon le motif :
    rapport_final_controle_n1_{branch}_{date}_{HHhMM}_{controller}.pdf
    (l'heure distingue deux contrôles du même jour).
    """
    safe_branch = sanitize_filename(branch, default="agence")
    safe_controller = sanitize_filename(controller, default="controleur")
    date_str = control_date.isoformat()  # YYYY-MM-DD
    time_str = re.sub(r"[^0-9]", "", control_time or "")[:4]
    if len(time_str) == 4:
        date_str += f"_{time_str[:2]}h{time_str[2:]}"
    return (
        f"rapport_final_controle_n1_{safe_branch}_{date_str}_{safe_controller}.pdf"
    )


def write_new_file(directory: Path, stem: str, ext: str, data: bytes) -> Path:
    """
    Écrit data dans directory/stem.ext sans jamais écraser un fichier
    existant (suffixe _1, _2... en cas de collision). Le contenu est d'abord
    écrit et synchronisé dans un fichier temporaire, puis renommé : une
    coupure ou une fermeture brutale ne laisse jamais un PDF tronqué.
    """
    temp = directory / f".{stem}.{uuid.uuid4().hex}.part"
    try:
        with open(temp, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        with _write_lock:
            candidate = directory / f"{stem}.{ext}"
            counter = 1
            while candidate.exists():
                candidate = directory / f"{stem}_{counter}.{ext}"
                counter += 1
            os.replace(temp, candidate)
    finally:
        if temp.exists():
            temp.unlink()
    return candidate


def to_stored_path(path: Path) -> str:
    """Chemin à enregistrer en base : relatif au dossier de données si possible."""
    try:
        return Path(path).resolve().relative_to(USER_DIR).as_posix()
    except ValueError:
        return str(path)


def resolve_stored_path(value: str | None) -> Path | None:
    """
    Fichier désigné par un chemin enregistré en base.

    Les chemins relatifs sont rattachés au dossier de données actuel. Un
    ancien chemin absolu qui n'existe plus (dossier de données restauré
    ailleurs, autre nom d'utilisateur) est rattaché à partir de reports/ ou
    uploads/.
    """
    if not value:
        return None
    path = Path(value)
    rooted = path.is_absolute() or PureWindowsPath(value).drive or value.startswith(("/", "\\"))
    if not rooted:
        return USER_DIR / path
    if path.is_file():
        return path
    parts = PureWindowsPath(value).parts if ("\\" in value or sys.platform == "win32") else path.parts
    for anchor in ("reports", "uploads"):
        if anchor in parts:
            index = len(parts) - 1 - parts[::-1].index(anchor)
            candidate = USER_DIR.joinpath(*parts[index:])
            if candidate.is_file():
                return candidate
    return path


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
    pdf_bytes: bytes,
    branch: str,
    control_date: dt.date,
    controller: str,
    control_time: str = "",
) -> Path:
    """Enregistre le PDF final dans reports/AAAA-MM/Agence/ et retourne le chemin."""
    report_dir = get_report_dir(branch, control_date)
    filename = build_report_filename(branch, control_date, controller, control_time)
    path = write_new_file(report_dir, filename[: -len(".pdf")], "pdf", pdf_bytes)
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

    candidate = write_new_file(upload_dir, stem, ext, data)
    logger.info("Document téléversé enregistré : %s", candidate)
    return candidate
