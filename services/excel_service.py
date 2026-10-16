"""
Service Excel : fichier de contrôle local du contrôleur (.xlsx).

Chaque contrôleur conserve SON fichier Excel sur son poste. À chaque
contrôle, il le téléverse dans l'application, qui y ajoute la ligne du
contrôle (ou la met à jour si le même contrôle y figure déjà), trie les
lignes par date, puis le lui rend à télécharger.

Aucun compte en ligne, aucun envoi réseau : tout se fait en mémoire.

Seul l'onglet « Controles » est réécrit : les autres onglets du classeur et
les colonnes ajoutées à la main par l'utilisateur sont conservés.

Les fonctions lèvent ExcelError avec un message déjà rédigé pour
l'utilisateur final.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from constants import (
    CONTROL_KEY_TO_SHEET_COLUMN,
    EXCEL_SHEET_NAME,
    SHEET_COLUMN_LABELS,
    SHEET_COLUMNS,
    SHEET_PROBLEM_PREFIXES,
    SHEET_VALUE_OK,
    STATUS_PROBLEM,
    sheet_cell_value,
)
from services.logging_service import get_logger

logger = get_logger()


class ExcelError(Exception):
    """Erreur de lecture / écriture du fichier Excel, message utilisateur."""


# Colonnes au format date / nombre dans le classeur (le reste est du texte).
_DATE_COLUMNS = {"date_controle": "DD/MM/YYYY", "horodatage": "DD/MM/YYYY HH:MM"}
_INT_COLUMNS = {"nb_problemes"}
_STATUS_COLUMNS = set(CONTROL_KEY_TO_SHEET_COLUMN.values())

_HEADER_FILL = PatternFill("solid", fgColor="9D174D")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_OK_FONT = Font(bold=True, color="1A7F37")
_PB_FONT = Font(bold=True, color="B42318")
_PB_FILL = PatternFill("solid", fgColor="FDECEA")

_COLUMN_WIDTHS = {
    "report_id": 14, "horodatage": 17, "date_controle": 12, "agence": 16,
    "controleur": 20, "nb_problemes": 11, "observations": 45,
    "fichier_pdf": 38, "email_envoye": 9,
}
_STATUS_WIDTH = 28


# --------------------------------------------------------------------------- #
# Construction d'une ligne
# --------------------------------------------------------------------------- #
def build_row(report: dict) -> dict[str, str]:
    """
    Ligne Excel d'un contrôle, à partir du rapport généré dans l'application.

    Chaque point de contrôle devient une colonne contenant « RAS »,
    « ANOMALIE — commentaire » ou « Non renseigné ».
    """
    statuses = report.get("statuses") or {}
    comments = report.get("problem_comments") or {}
    row: dict[str, str] = {
        "report_id": report.get("report_id", ""),
        "horodatage": report.get("created_at", ""),
        "date_controle": report.get("control_date", ""),
        "agence": report.get("branch", ""),
        "controleur": report.get("controller", ""),
        "observations": (report.get("observations") or "").strip(),
        "fichier_pdf": report.get("filename", ""),
        "email_envoye": "Oui" if report.get("email_sent") else "Non",
    }
    problems = 0
    for key, column in CONTROL_KEY_TO_SHEET_COLUMN.items():
        status = statuses.get(key) or ""
        row[column] = sheet_cell_value(status, comments.get(key))
        if status == STATUS_PROBLEM:
            problems += 1
    row["nb_problemes"] = str(problems)
    return row


# --------------------------------------------------------------------------- #
# Normalisation des valeurs lues
# --------------------------------------------------------------------------- #
_FR_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")


def _to_iso(value, *, with_time: bool) -> str:
    """Date Excel / texte ISO / texte JJ/MM/AAAA -> texte ISO (tri, filtres)."""
    if value is None or value == "":
        return ""
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ", timespec="minutes") if with_time else value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    text = str(value).strip()
    match = _FR_DATE_RE.match(text)
    if match:
        day, month, year, hour, minute = match.groups()
        iso = f"{year}-{int(month):02d}-{int(day):02d}"
        if with_time and hour:
            iso += f" {int(hour):02d}:{minute}"
        return iso
    text = text.replace("T", " ")
    return text[:16] if with_time else text[:10]


def _to_text(column: str, value) -> str:
    """Valeur de cellule -> texte, dans le format attendu par l'application."""
    if column == "date_controle":
        return _to_iso(value, with_time=False)
    if column == "horodatage":
        return _to_iso(value, with_time=True)
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _to_cell(column: str, text: str):
    """Texte de l'application -> valeur typée pour Excel (dates, nombres)."""
    if not text:
        return None
    if column in _DATE_COLUMNS:
        try:
            parsed = dt.datetime.fromisoformat(text)
        except ValueError:
            return text
        return parsed.date() if column == "date_controle" else parsed
    if column in _INT_COLUMNS:
        try:
            return int(text)
        except ValueError:
            return text
    return text


# --------------------------------------------------------------------------- #
# Lecture du classeur
# --------------------------------------------------------------------------- #
def _header_key(value) -> str | None:
    """Colonne de l'application correspondant à un titre d'en-tête."""
    text = str(value or "").strip().casefold()
    if not text:
        return None
    for column in SHEET_COLUMNS:
        if text in (column.casefold(), SHEET_COLUMN_LABELS[column].casefold()):
            return column
    return None


def _open_workbook(data: bytes):
    try:
        return load_workbook(io.BytesIO(data))
    except (InvalidFileException, zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        logger.warning("Fichier Excel illisible : %s", exc)
        raise ExcelError(
            "Ce fichier n'a pas pu être ouvert. Vérifiez qu'il s'agit bien "
            "d'un fichier Excel (.xlsx) enregistré depuis Excel, et qu'il "
            "n'est pas protégé par un mot de passe."
        ) from exc


def _find_sheet(workbook):
    """Onglet « Controles », ou premier onglet portant les bons en-têtes."""
    if EXCEL_SHEET_NAME in workbook.sheetnames:
        return workbook[EXCEL_SHEET_NAME]
    for sheet in workbook.worksheets:
        headers = {_header_key(cell.value) for cell in sheet[1]}
        if {"report_id", "date_controle", "agence"} <= headers:
            return sheet
    raise ExcelError(
        f"Ce fichier ne contient pas d'onglet « {EXCEL_SHEET_NAME} ». "
        "Téléversez le fichier de contrôle téléchargé depuis l'application "
        "(ou retirez ce fichier et utilisez le bouton rouge en haut à "
        "droite de la page)."
    )


def _read_table(sheet) -> tuple[list, list[list]]:
    """En-têtes (valeurs brutes) et lignes de données non vides."""
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return [], []
    header = list(rows[0])
    while header and header[-1] in (None, ""):
        header.pop()
    data = [
        list(row[: len(header)]) + [None] * (len(header) - len(row))
        for row in rows[1:]
        if any(value not in (None, "") for value in row)
    ]
    return header, data


def _rows_as_dicts(header: list, data: list[list]) -> list[dict[str, str]]:
    keys = [_header_key(value) for value in header]
    result = []
    for values in data:
        row = {column: "" for column in SHEET_COLUMNS}
        for key, value in zip(keys, values):
            if key:
                row[key] = _to_text(key, value)
        result.append(row)
    return result


def read_rows(data: bytes) -> list[dict[str, str]]:
    """
    Relit les contrôles d'un fichier Excel de contrôle.

    Retourne une liste de lignes {colonne: texte}, dates au format ISO.
    """
    sheet = _find_sheet(_open_workbook(data))
    header, rows = _read_table(sheet)
    return _rows_as_dicts(header, rows)


# --------------------------------------------------------------------------- #
# Écriture du classeur
# --------------------------------------------------------------------------- #
def _sort_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("date_controle", ""), row.get("horodatage", ""))


def _style_sheet(sheet, keys: list[str | None], n_rows: int) -> None:
    """Mise en forme : en-tête coloré, statuts en couleur, filtres, volet figé."""
    for col_idx, key in enumerate(keys, start=1):
        head = sheet.cell(row=1, column=col_idx)
        if key:
            head.fill, head.font = _HEADER_FILL, _HEADER_FONT
            head.alignment = Alignment(vertical="center")
            width = _STATUS_WIDTH if key in _STATUS_COLUMNS else _COLUMN_WIDTHS.get(key, 14)
            sheet.column_dimensions[get_column_letter(col_idx)].width = width
        for row_idx in range(2, n_rows + 2):
            cell = sheet.cell(row=row_idx, column=col_idx)
            if key in _DATE_COLUMNS:
                cell.number_format = _DATE_COLUMNS[key]
            elif key in _STATUS_COLUMNS:
                text = str(cell.value or "")
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if text == SHEET_VALUE_OK:
                    cell.font, cell.fill = _OK_FONT, PatternFill()
                elif text.startswith(SHEET_PROBLEM_PREFIXES):
                    cell.font, cell.fill = _PB_FONT, _PB_FILL
                else:
                    cell.font, cell.fill = Font(), PatternFill()
            elif key == "observations":
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            elif key == "nb_problemes":
                cell.alignment = Alignment(horizontal="center", vertical="top")
                cell.font = _PB_FONT if cell.value not in (None, 0, "0") else Font(bold=True)
    sheet.freeze_panes = "A2"
    if keys:
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(keys))}{n_rows + 1}"


def _write_table(sheet, header: list, data: list[list], keys: list[str | None]) -> None:
    old_rows = sheet.max_row
    for row_idx, values in enumerate([header, *data], start=1):
        for col_idx, (key, value) in enumerate(zip(keys, values), start=1):
            # Affectation explicite : sheet.cell(value=None) n'efface pas.
            cell = sheet.cell(row=row_idx, column=col_idx)
            cell.value = value
            # openpyxl lit un texte commençant par « = » comme une formule :
            # les textes saisis dans l'application restent du texte.
            if row_idx > 1 and key and isinstance(value, str) and value.startswith("="):
                cell.data_type = "s"
    if old_rows > len(data) + 1:
        sheet.delete_rows(len(data) + 2, old_rows - len(data) - 1)
    _style_sheet(sheet, keys, len(data))


def update_workbook(base: bytes | None, new_rows: list[dict[str, str]]) -> bytes:
    """
    Ajoute (ou met à jour, même « Réf. ») des contrôles dans un classeur.

    - base = None -> nouveau classeur avec l'onglet « Controles » ;
    - sinon, seul l'onglet des contrôles est réécrit, trié par date de
      contrôle puis par heure d'enregistrement. Les colonnes et onglets
      ajoutés par l'utilisateur sont conservés.
    """
    if base:
        workbook = _open_workbook(base)
        sheet = _find_sheet(workbook)
        header, data = _read_table(sheet)
    else:
        workbook = Workbook()
        sheet = workbook.worksheets[0]
        sheet.title = EXCEL_SHEET_NAME
        header, data = [], []

    # Colonnes de l'application absentes du fichier : ajoutées à droite.
    keys = [_header_key(value) for value in header]
    for column in SHEET_COLUMNS:
        if column not in keys:
            header.append(SHEET_COLUMN_LABELS[column])
            keys.append(column)
            for values in data:
                values.append(None)
    position = {key: idx for idx, key in enumerate(keys) if key}

    # Insertion / mise à jour par référence de contrôle.
    by_ref: dict[str, list] = {
        _to_text("report_id", values[position["report_id"]]): values
        for values in data
        if values[position["report_id"]] not in (None, "")
    }
    for row in new_rows:
        if row["report_id"] not in by_ref:
            by_ref[row["report_id"]] = [None] * len(header)
            data.append(by_ref[row["report_id"]])
        values = by_ref[row["report_id"]]
        for column in SHEET_COLUMNS:
            values[position[column]] = _to_cell(column, row.get(column, ""))

    # Tri par date (les lignes gardent leurs colonnes personnelles).
    data.sort(key=lambda values: _sort_key(
        {col: _to_text(col, values[position[col]]) for col in ("date_controle", "horodatage")}
    ))

    _write_table(sheet, header, data, keys)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_workbook(rows: list[dict[str, str]]) -> bytes:
    """Nouveau classeur contenant ces lignes (export de la consultation)."""
    return update_workbook(None, rows)


def summarize(rows: list[dict[str, str]]) -> tuple[int, str]:
    """Nombre de contrôles et date du plus récent (texte ISO, vide si aucun)."""
    dates = [row["date_controle"] for row in rows if row.get("date_controle")]
    return len(rows), max(dates, default="")
