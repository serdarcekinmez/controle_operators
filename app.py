"""
Application de contrôle agences — Contrôle niveau 1.

Application Streamlit LOCALE (poste de travail). Aucune donnée client :
uniquement le suivi des points de contrôle interne d'une agence.

Flux : saisie -> génération d'UN PDF final (rapport + pièces jointes
converties/fusionnées) -> ajout au fichier de contrôle Excel du contrôleur.
L'envoi par e-mail sera branché plus tard sur Outlook / SharePoint
(Microsoft 365) : le bouton est déjà présent, mais désactivé.

Suivi des contrôles : chaque contrôleur conserve SON fichier Excel sur son
poste. Il le téléverse, chaque contrôle enregistré (« Enregistrer dans
Excel », ou création du PDF) y est ajouté, puis il le retélécharge mis à
jour. Un contrôle peut aussi en être supprimé. Aucun compte en ligne n'est
nécessaire.

Mise en page : disposition « bureau » compacte, en blocs/cartes, avec un
choix de statut OK / Problème par point de contrôle.
"""

from __future__ import annotations

import datetime as dt
import html
import re

import streamlit as st

from constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    APP_SUBTITLE,
    APP_TITLE,
    BRANCHES,
    CONTROL_ITEMS,
    EXCEL_DEFAULT_STEM,
    LOGO_PATH,
    SHEET_COLUMN_LABELS,
    SHEET_COLUMNS,
    SHEET_PROBLEM_PREFIXES,
    SHEET_VALUE_OK,
    STATUS_OK,
    STATUS_PROBLEM,
)
from services import db_service, excel_service
from services.config_service import load_config
from services.file_service import (
    ensure_directories,
    get_extension,
    is_allowed_upload,
    is_image,
    save_report_pdf,
    save_uploaded_file,
)
from services.excel_service import ExcelError
from services.logging_service import get_logger
from services.pdf_service import (
    Attachment,
    ReportMetadata,
    build_final_report,
    image_to_pdf_bytes,
)

logger = get_logger()


# --------------------------------------------------------------------------- #
# Styles (CSS) — disposition compacte type outil métier
# --------------------------------------------------------------------------- #
_BASE_CSS = """
<style>
/* Largeur de page agréable sur desktop */
.block-container { max-width: 1180px; padding-top: 1.6rem; padding-bottom: 3rem; }

/* Titre principal de l'application */
h1 { color: #0f2b46 !important; font-weight: 800 !important;
  letter-spacing: -.01em; margin-bottom: .1rem !important; }
h1::after { content: ""; display: block; width: 92px; height: 4px;
  margin-top: .45rem; border-radius: 3px;
  background: linear-gradient(90deg, #1d4ed8, #6d28d9 55%, #0f766e); }

/* Titres de section dans les cartes — une couleur par domaine */
.section-title { font-size: 1.05rem; font-weight: 700; color: #1f2d3d;
  margin: 0 0 .15rem 0; padding-left: .55rem;
  border-left: 4px solid #cbd5e1; border-radius: 2px; }
.sec-info   { color: #1d4ed8; border-left-color: #1d4ed8; }
.sec-ctrl   { color: #6d28d9; border-left-color: #6d28d9; }
.sec-obs    { color: #0f766e; border-left-color: #0f766e; }
.sec-doc    { color: #b45309; border-left-color: #b45309; }
.sec-act    { color: #0f2b46; border-left-color: #0f2b46; }
.sec-xlsx   { color: #15803d; border-left-color: #15803d; }
.sec-audit  { color: #9d174d; border-left-color: #9d174d; }
.section-sub { color: #6b7280; font-size: .82rem; margin: 0 0 .6rem 0; }

/* Libellé d'un point de contrôle */
.ctrl-label { font-size: .95rem; color: #1f2d3d; font-weight: 500;
  padding: .15rem 0; }

/* Boutons "OK" (verts) — base = contour vert, fond blanc */
[class*="st-key-btn_ok_"] button {
  border: 1px solid #1a7f37 !important; color: #1a7f37 !important;
  background: #ffffff !important; font-weight: 600 !important;
}
[class*="st-key-btn_ok_"] button:hover { background: #e9f7ee !important; }

/* Boutons "Problème" (rouges) — base = contour rouge, fond blanc */
[class*="st-key-btn_pb_"] button {
  border: 1px solid #b42318 !important; color: #b42318 !important;
  background: #ffffff !important; font-weight: 600 !important;
}
[class*="st-key-btn_pb_"] button:hover { background: #fdecea !important; }

/* Zones de texte qui grandissent avec le contenu (navigateurs récents) */
.stTextArea textarea { field-sizing: content; min-height: 90px; max-height: 360px; }
.st-key-observations textarea { min-height: 150px; }

/* Tableau de consultation (audit) */
.audit-wrap { overflow-x: auto; border: 1px solid #e2e8f0; border-radius: .5rem; }
table.audit { border-collapse: collapse; width: 100%; font-size: .82rem; }
table.audit thead th { background: #9d174d; color: #fff; font-weight: 600;
  text-align: left; padding: .45rem .6rem; white-space: nowrap;
  position: sticky; top: 0; }
table.audit td { padding: .4rem .6rem; border-top: 1px solid #eef2f7;
  vertical-align: top; }
table.audit tbody tr:nth-child(even) { background: #fafbfc; }
table.audit td.ras { color: #1a7f37; font-weight: 600; white-space: nowrap; }
table.audit td.pb  { color: #b42318; font-weight: 600; }
table.audit td.na  { color: #94a3b8; }
table.audit td.num { text-align: center; font-weight: 700; }
table.audit td.num.hot { color: #b42318; }

/* Bouton « Première fois ? » (en-tête) : rouge, en gras, bien visible */
.st-key-btn_first_excel button {
  background: #b42318 !important; border: 1px solid #b42318 !important;
  color: #ffffff !important; box-shadow: 0 2px 8px #b4231840;
}
.st-key-btn_first_excel button { height: auto !important; padding: .55rem .8rem !important; }
.st-key-btn_first_excel button div, .st-key-btn_first_excel button p {
  white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; }
.st-key-btn_first_excel button p { font-weight: 800 !important; font-size: .95rem;
  line-height: 1.3; text-align: center; }
.st-key-btn_first_excel button:hover { background: #912018 !important; }

/* Indentation du commentaire de problème */
.problem-hint { color: #b42318; font-size: .82rem; font-weight: 600;
  margin: .1rem 0 -.4rem .2rem; }
</style>
"""


def _inject_status_css() -> None:
    """CSS dynamique : remplit le bouton du statut sélectionné (vert/rouge)."""
    rules: list[str] = []
    for key, _ in CONTROL_ITEMS:
        status = st.session_state.statuses.get(key)
        if status == STATUS_OK:
            rules.append(
                f".st-key-btn_ok_{key} button {{ background:#1a7f37 !important;"
                f" color:#fff !important; box-shadow:0 0 0 2px #1a7f3733; }}"
            )
        elif status == STATUS_PROBLEM:
            rules.append(
                f".st-key-btn_pb_{key} button {{ background:#b42318 !important;"
                f" color:#fff !important; box-shadow:0 0 0 2px #b4231833; }}"
            )
    if rules:
        st.markdown("<style>" + "".join(rules) + "</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Initialisation
# --------------------------------------------------------------------------- #
@st.cache_resource
def _bootstrap() -> bool:
    ensure_directories()
    db_service.init_db()
    logger.info("Application démarrée.")
    return True


def _init_state(config: dict) -> None:
    if "statuses" not in st.session_state:
        st.session_state.statuses = {key: None for key, _ in CONTROL_ITEMS}
    # Valeurs initiales des champs (fixées une fois : une valeur par défaut
    # recalculée à chaque passage réinitialiserait le champ).
    now = dt.datetime.now().time().replace(second=0, microsecond=0)
    st.session_state.setdefault("controller", config.get("default_controller_name", "") or "")
    st.session_state.setdefault("control_date", dt.date.today())
    st.session_state.setdefault("control_time", now)
    st.session_state.setdefault("del_date", dt.date.today())
    st.session_state.setdefault("del_time", now)


def _set_status(key: str, value: str) -> None:
    """Callback des boutons de statut : sélection exclusive, re-clic = annule."""
    current = st.session_state.statuses.get(key)
    st.session_state.statuses[key] = None if current == value else value


# --------------------------------------------------------------------------- #
# Collecte des données du formulaire
# --------------------------------------------------------------------------- #
def _form() -> dict:
    """Champs du formulaire (Informations générales + observations)."""
    ss = st.session_state
    return {
        "controller": (ss.get("controller") or "").strip(),
        "branch": ss.get("branch"),
        "control_date": ss.get("control_date") or dt.date.today(),
        "control_time": ss.get("control_time") or dt.time(0, 0),
        "observations": ss.get("observations") or "",
    }


def _collect_statuses() -> dict[str, str]:
    """Statuts normalisés en chaîne ('ok' | 'problem' | '')."""
    return {key: (st.session_state.statuses.get(key) or "") for key, _ in CONTROL_ITEMS}


def _collect_problem_comments() -> dict[str, str]:
    """Commentaires des points en statut 'problem'."""
    comments: dict[str, str] = {}
    for key, _ in CONTROL_ITEMS:
        if st.session_state.statuses.get(key) == STATUS_PROBLEM:
            comments[key] = (st.session_state.get(f"comment_{key}", "") or "").strip()
    return comments


def _form_report(form: dict) -> dict:
    """Contrôle saisi, au format attendu par excel_service.build_row."""
    return {
        "report_id": db_service.new_report_id(),
        "control_date": form["control_date"].isoformat(),
        "control_time": form["control_time"].strftime("%H:%M"),
        "branch": form["branch"],
        "controller": form["controller"],
        "statuses": _collect_statuses(),
        "problem_comments": _collect_problem_comments(),
        "observations": form["observations"],
        "filename": "",
        "email_sent": False,
    }


def _form_errors(form: dict) -> list[str]:
    """Messages d'erreur du formulaire (liste vide si tout est correct)."""
    missing = []
    if not form["controller"]:
        missing.append("le nom du contrôleur")
    if not form["branch"]:
        missing.append("l'agence")
    if missing:
        return ["Champs obligatoires manquants : " + ", ".join(missing) + "."]

    statuses, comments = _collect_statuses(), _collect_problem_comments()
    uncommented = [
        label
        for key, label in CONTROL_ITEMS
        if statuses.get(key) == STATUS_PROBLEM and not comments.get(key)
    ]
    if uncommented:
        return [
            "Un commentaire est obligatoire pour chaque anomalie signalée : "
            + ", ".join(uncommented) + "."
        ]

    # Date + heure + contrôleur identifient un contrôle : un contrôle d'une
    # autre agence au même moment serait écrasé.
    key = (
        form["control_date"].isoformat(),
        form["control_time"].strftime("%H:%M"),
        excel_service.normalize_name(form["controller"]),
    )
    for row in _excel_state()["rows"]:
        if excel_service.row_key(row) == key and row.get("agence") != form["branch"]:
            return [
                f"Le fichier Excel contient déjà un contrôle de {form['controller']} "
                f"le {_fr_date(key[0])} à {key[1]} (agence {row.get('agence')}). "
                "Corrigez l'heure du contrôle."
            ]
    return []


# --------------------------------------------------------------------------- #
# Action : convertir en PDF (aide / statut)
# --------------------------------------------------------------------------- #
def _handle_convert(uploaded_files: list) -> None:
    # On ne compte que les images : seules elles ont besoin d'être converties.
    images = [
        uf for uf in (uploaded_files or [])
        if is_allowed_upload(uf.name) and is_image(uf.name)
    ]
    if not images:
        st.info("Aucune image à convertir.")
        return

    converted = 0
    errors: list[str] = []
    for uf in images:
        try:
            image_to_pdf_bytes(uf.getvalue())
            converted += 1
        except Exception:
            logger.exception("Conversion impossible : %s", uf.name)
            errors.append(uf.name)

    if converted:
        st.success(
            f"Images converties en PDF avec succès ({converted}). "
            "Elles seront intégrées au rapport final."
        )
    for name in errors:
        st.warning(f"Image ignorée (illisible/corrompue) : {name}")


# --------------------------------------------------------------------------- #
# Action : créer le rapport PDF
# --------------------------------------------------------------------------- #
def _handle_generate(uploaded_files: list) -> None:
    form = _form()
    errors = _form_errors(form)
    for error in errors:
        st.error(error)
    if errors:
        return

    controller, branch = form["controller"], form["branch"]
    control_date, observations = form["control_date"], form["observations"]
    control_time_str = form["control_time"].strftime("%H:%M")
    statuses = _collect_statuses()
    problem_comments = _collect_problem_comments()

    # --- Préparation des pièces jointes ---
    attachments: list[Attachment] = []
    for uf in uploaded_files or []:
        if not is_allowed_upload(uf.name):
            st.warning(f"Format non accepté, fichier ignoré : {uf.name}")
            logger.warning("Fichier rejeté (format) : %s", uf.name)
            continue
        attachments.append(Attachment(filename=uf.name, data=uf.getvalue()))

    control_date_str = control_date.isoformat()
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    meta = ReportMetadata(
        branch=branch,
        control_date=f"{control_date_str} à {control_time_str}",
        controller=controller,
        generated_at=generated_at,
        statuses=statuses,
        problem_comments=problem_comments,
        observations=observations,
        attachment_names=[a.filename for a in attachments],
    )

    with st.spinner("Génération du rapport PDF en cours..."):
        try:
            result = build_final_report(meta, attachments)
        except Exception:
            logger.exception("Échec inattendu de la génération du PDF.")
            st.error(
                "Une erreur est survenue pendant la génération du PDF. "
                "Consultez logs/app.log pour le détail technique."
            )
            return

        for err in result.errors:
            st.warning(err)

        try:
            pdf_path = save_report_pdf(
                result.pdf_bytes, branch, control_date, controller
            )
        except OSError:
            logger.exception("Écriture du PDF final impossible.")
            st.error(
                "Le PDF a été généré mais n'a pas pu être enregistré "
                "(droits/disque). Consultez logs/app.log."
            )
            return

        stored_uploads: list[tuple[str, str, str]] = []
        for att in attachments:
            try:
                stored = save_uploaded_file(
                    att.data, att.filename, branch, control_date
                )
                stored_uploads.append(
                    (att.filename, str(stored), get_extension(att.filename))
                )
            except OSError:
                logger.exception(
                    "Sauvegarde du fichier téléversé impossible : %s", att.filename
                )

        record = db_service.ControlRecord(
            branch_name=branch,
            controller_name=controller,
            control_date=control_date_str,
            statuses=statuses,
            observations=observations,
            pdf_path=str(pdf_path),
            problem_comments=problem_comments,
        )
        report_id = record.report_id
        control_id = db_service.insert_control(record)
        if control_id is not None:
            for original, stored_path, file_type in stored_uploads:
                db_service.insert_attachment(
                    control_id, original, stored_path, file_type
                )

    report = {
        "pdf_bytes": result.pdf_bytes,
        "pdf_path": str(pdf_path),
        "filename": pdf_path.name,
        "control_id": control_id,
        "report_id": report_id,
        "branch": branch,
        "control_date": control_date_str,
        "control_time": control_time_str,
        "controller": controller,
        "statuses": statuses,
        "problem_comments": problem_comments,
        "observations": observations,
        "email_sent": False,
    }
    st.session_state["report"] = report
    _add_to_excel(report)
    st.success(
        f"PDF généré avec succès : {pdf_path.name}. Le contrôle est enregistré "
        "dans votre fichier de contrôle Excel (bloc « Fichier de contrôle "
        "Excel »)."
    )


# --------------------------------------------------------------------------- #
# Fichier de contrôle Excel (téléversé, mis à jour, retéléchargé)
# --------------------------------------------------------------------------- #
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _add_to_excel(report: dict) -> dict[str, str]:
    """
    Ajoute (ou met à jour) le contrôle dans les lignes Excel de la session.

    Les lignes sont indexées par identité (date, heure, contrôleur) : un
    contrôle enregistré une seconde fois (ex. « Enregistrer dans Excel »
    après la création du PDF) garde sa « Réf. » et son nom de PDF.
    """
    rows = st.session_state.setdefault("excel_rows", {})
    row = excel_service.build_row(report)
    key = excel_service.row_key(row)
    previous = rows.get(key)
    if previous:
        row["report_id"] = previous["report_id"]
        row["fichier_pdf"] = row["fichier_pdf"] or previous["fichier_pdf"]
    rows[key] = row
    st.session_state.setdefault("excel_deleted", set()).discard(key)
    return row


def _save_to_excel() -> None:
    """Bouton « Enregistrer dans Excel » : ajoute le contrôle saisi."""
    form = _form()
    errors = _form_errors(form)
    if errors:
        st.session_state["excel_msg"] = ("error", " ".join(errors))
        return
    row = _add_to_excel(_form_report(form))
    st.session_state["excel_msg"] = (
        "success",
        f"Contrôle enregistré : {row['agence']} — {_fr_date(row['date_controle'])} "
        f"à {row['heure_controle']} — {row['controleur']}. Téléchargez le "
        "fichier pour conserver la mise à jour.",
    )


def _delete_from_excel() -> None:
    """Bouton « Supprimer » : retire le contrôle (date, heure, contrôleur)."""
    ss = st.session_state
    controller = (ss.get("del_controller") or "").strip()
    if not controller or ss.get("del_date") is None or ss.get("del_time") is None:
        ss["excel_msg"] = (
            "error", "Renseignez la date, l'heure et le nom du contrôleur à supprimer."
        )
        return
    key = (
        ss["del_date"].isoformat(),
        ss["del_time"].strftime("%H:%M"),
        excel_service.normalize_name(controller),
    )
    label = f"{_fr_date(key[0])} à {key[1]} — {controller}"
    matches = [row for row in _excel_state()["rows"] if excel_service.row_key(row) == key]
    if not matches:
        ss["excel_msg"] = (
            "error",
            f"Aucun contrôle trouvé dans le fichier pour : {label}. Vérifiez "
            "la date, l'heure (colonne « Heure ») et le nom du contrôleur.",
        )
        return
    ss.setdefault("excel_rows", {}).pop(key, None)
    ss.setdefault("excel_deleted", set()).add(key)
    agencies = ", ".join(sorted({row.get("agence", "") for row in matches}))
    ss["excel_msg"] = (
        "success",
        f"Contrôle supprimé : {agencies} — {label}. Téléchargez le fichier "
        "pour conserver la suppression.",
    )


@st.cache_data(show_spinner=False, max_entries=32)
def _read_excel(data: bytes) -> list[dict[str, str]]:
    return excel_service.read_rows(data)


@st.cache_data(show_spinner=False, max_entries=16)
def _merge_excel(
    base: bytes | None, rows: list[dict[str, str]], deleted: tuple = ()
) -> bytes:
    return excel_service.update_workbook(base, rows, deleted)


def _fr_date(iso: str) -> str:
    """AAAA-MM-JJ -> JJ/MM/AAAA (texte laissé tel quel s'il est différent)."""
    try:
        return dt.date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return iso


_FORBIDDEN_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _excel_download_name(controller: str) -> str:
    """
    Nom du fichier téléchargé : « AAMMJJ - Prénom.xlsx ».

    - date : jour de la mise à jour du fichier (ex. 261016) ;
    - prénom : premier mot du nom du contrôleur (« Jean Dupont » -> « Jean »).

    Exemple : « 261016 - Jean.xlsx » (« 261016 - Controles.xlsx » sans nom).
    Le fichier contient toutes les agences : l'agence n'est plus dans le nom.
    """
    first_name = (controller or "").split()[0] if (controller or "").strip() else ""
    if first_name.islower():
        first_name = first_name.title()  # « jean-marie » -> « Jean-Marie »
    parts = [dt.date.today().strftime("%y%m%d"), first_name or EXCEL_DEFAULT_STEM]
    parts = [_FORBIDDEN_FILENAME_CHARS.sub("", part).strip(" .") for part in parts]
    return " - ".join(part for part in parts if part) + ".xlsx"


def _excel_state() -> dict:
    """
    Fichier de contrôle à jour : fichier téléversé + contrôles de la session.

    Retourne name (fichier téléversé ou None), created (nouveau fichier
    demandé, sans fichier téléversé), error, base_count (contrôles déjà dans
    le fichier), session_count, data (classeur à télécharger ou None) et
    rows (ses lignes).
    """
    upload = st.session_state.get("xlsx_upload")
    session_rows = list(st.session_state.get("excel_rows", {}).values())
    deleted = tuple(sorted(st.session_state.get("excel_deleted", set())))
    state: dict = {
        "name": upload.name if upload is not None else None,
        "created": upload is None and st.session_state.get("xlsx_new", False),
        "error": "",
        "base_count": 0,
        "session_count": len(session_rows),
        "data": None,
        "rows": [],
    }
    base = upload.getvalue() if upload is not None else None
    if base is None and not session_rows and not state["created"]:
        return state
    try:
        if base is not None:
            state["base_count"] = len(_read_excel(base))
        data = _merge_excel(base, session_rows, deleted)
        state["rows"] = _read_excel(data)
        state["data"] = data
    except ExcelError as exc:
        state["error"] = str(exc)
    except Exception:
        logger.exception("Mise à jour du fichier Excel impossible.")
        state["error"] = (
            "Une erreur inattendue est survenue avec le fichier Excel. "
            "Consultez logs/app.log."
        )
    return state


# --------------------------------------------------------------------------- #
# Consultation : construction du tableau HTML
# --------------------------------------------------------------------------- #
# Colonnes affichées à l'écran (les autres restent dans les exports).
_AUDIT_DISPLAY_COLUMNS = [
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
]


def _escape(value: str) -> str:
    return html.escape(str(value or ""))


def _cell(column: str, value: str) -> str:
    """Cellule HTML avec la classe de couleur qui convient."""
    text = str(value or "")
    if column == "date_controle":
        text = _fr_date(text)
    if column == "nb_problemes":
        hot = " hot" if text not in ("", "0") else ""
        return f'<td class="num{hot}">{_escape(text)}</td>'
    if text == SHEET_VALUE_OK:
        return f'<td class="ras">{_escape(text)}</td>'
    if text.startswith(SHEET_PROBLEM_PREFIXES):
        return f'<td class="pb">{_escape(text)}</td>'
    if not text:
        return '<td class="na">—</td>'
    return f"<td>{_escape(text)}</td>"


def _build_audit_table(rows: list[dict], columns: list[str]) -> str:
    """Tableau HTML (fragment) des contrôles."""
    head = "".join(
        f"<th>{_escape(SHEET_COLUMN_LABELS.get(col, col))}</th>" for col in columns
    )
    body = "".join(
        "<tr>" + "".join(_cell(col, row.get(col, "")) for col in columns) + "</tr>"
        for row in rows
    )
    return (
        '<div class="audit-wrap"><table class="audit">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _build_audit_document(rows: list[dict], subtitle: str) -> str:
    """Document HTML autonome, téléchargeable et imprimable."""
    table = _build_audit_table(rows, SHEET_COLUMNS)
    generated = dt.datetime.now().strftime("%d/%m/%Y à %H:%M")
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Rapports de contrôle niveau 1</title>
<style>
body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 2rem;
  color: #0f2b46; }}
h1 {{ color: #0f2b46; margin-bottom: .2rem; }}
p.meta {{ color: #64748b; font-size: .85rem; margin-top: 0; }}
.audit-wrap {{ overflow-x: auto; border: 1px solid #e2e8f0; border-radius: .5rem; }}
table.audit {{ border-collapse: collapse; width: 100%; font-size: .8rem; }}
table.audit thead th {{ background: #9d174d; color: #fff; text-align: left;
  padding: .45rem .6rem; white-space: nowrap; }}
table.audit td {{ padding: .4rem .6rem; border-top: 1px solid #eef2f7;
  vertical-align: top; }}
table.audit tbody tr:nth-child(even) {{ background: #fafbfc; }}
table.audit td.ras {{ color: #1a7f37; font-weight: 600; }}
table.audit td.pb {{ color: #b42318; font-weight: 600; }}
table.audit td.na {{ color: #94a3b8; }}
table.audit td.num {{ text-align: center; font-weight: 700; }}
table.audit td.num.hot {{ color: #b42318; }}
</style></head><body>
<h1>Rapports de contrôle niveau 1</h1>
<p class="meta">{_escape(subtitle)} — {len(rows)} rapport(s) — édité le {generated}</p>
{table}
</body></html>"""


# --------------------------------------------------------------------------- #
# Barre latérale : historique local
# --------------------------------------------------------------------------- #
def _render_sidebar() -> None:
    """Affiche la barre latérale : derniers rapports créés sur ce poste."""
    with st.sidebar:
        st.markdown("### Historique local")
        rows = db_service.get_recent_controls(limit=8)
        if not rows:
            st.caption("Aucun rapport enregistré pour le moment.")
        for row in rows:
            st.caption(
                f"📄 **{row['branch_name']}** — {row['control_date']} · "
                f"{row['controller_name']}"
            )


# --------------------------------------------------------------------------- #
# Bloc : Contrôle niveau 1
# --------------------------------------------------------------------------- #
def _render_control_block() -> None:
    with st.container(border=True):
        answered = sum(1 for k, _ in CONTROL_ITEMS if st.session_state.statuses.get(k))
        st.markdown('<p class="section-title sec-ctrl">Contrôle niveau 1</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="section-sub">Choisissez OK (vert) ou Anomalie (rouge) pour '
            "chaque point — un commentaire est requis en cas d'anomalie. "
            f"<b>{answered}/{len(CONTROL_ITEMS)} renseigné(s)</b>.</p>",
            unsafe_allow_html=True,
        )
        for key, label in CONTROL_ITEMS:
            c_label, c_ok, c_pb = st.columns([5, 1.3, 1.7], vertical_alignment="center")
            with c_label:
                st.markdown(f'<div class="ctrl-label">{label}</div>', unsafe_allow_html=True)
            with c_ok:
                st.button(
                    "OK", key=f"btn_ok_{key}", use_container_width=True,
                    on_click=_set_status, args=(key, STATUS_OK),
                )
            with c_pb:
                st.button(
                    "Anomalie", key=f"btn_pb_{key}", use_container_width=True,
                    on_click=_set_status, args=(key, STATUS_PROBLEM),
                )
            # Commentaire conditionnel, lié à ce point précis.
            if st.session_state.statuses.get(key) == STATUS_PROBLEM:
                _, c_comment = st.columns([0.3, 9.7])
                with c_comment:
                    st.text_area(
                        "Commentaire / détail de l'anomalie (obligatoire)",
                        key=f"comment_{key}",
                        placeholder="Décrivez l'anomalie constatée...",
                    )


# --------------------------------------------------------------------------- #
# Bloc : Actions du rapport (boutons d'action visibles)
# --------------------------------------------------------------------------- #
def _render_actions(uploaded_files: list) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-title sec-act">Actions du rapport</p>', unsafe_allow_html=True)

        if st.button("🖼️ Convertir en PDF", use_container_width=True):
            _handle_convert(uploaded_files)

        if st.button(
            "📄 Créer le rapport PDF", type="primary", use_container_width=True
        ):
            _handle_generate(uploaded_files)

        # Emplacement réservé : l'envoi sera branché sur Outlook / SharePoint
        # (comptes Microsoft 365 des agences et des directions).
        st.button(
            "📧 Envoyer le rapport",
            use_container_width=True,
            disabled=True,
            help="Bientôt disponible : envoi par Outlook (Microsoft 365).",
        )

        # Statut + téléchargement
        report = st.session_state.get("report")
        st.divider()
        if report:
            st.download_button(
                "⬇️ Télécharger le rapport",
                data=report["pdf_bytes"],
                file_name=report["filename"],
                mime="application/pdf",
                use_container_width=True,
            )
            st.success("Statut : PDF généré", icon="📄")
            st.caption(
                f"Fichier : {report['filename']} — une copie est aussi "
                "enregistrée sur ce poste, dans le dossier « reports » de "
                "l'application (classée par mois et par agence)."
            )
        else:
            st.caption("Aucun rapport généré pour l'instant.")

        st.caption("ℹ️ Envoi par e-mail (Outlook) : bientôt disponible.")


# --------------------------------------------------------------------------- #
# En-tête : création du premier fichier Excel
# --------------------------------------------------------------------------- #
def _render_first_time_button() -> None:
    """
    Bouton rouge « Première fois ? », en haut à droite de la page.

    Volontairement séparé des blocs d'opérations (PDF / Excel) pour ne pas
    être confondu avec eux. Masqué dès qu'un fichier est chargé ou créé.
    """
    if st.session_state.get("xlsx_upload") is not None or st.session_state.get("xlsx_new"):
        return
    st.markdown('<div style="height: 40px"></div>', unsafe_allow_html=True)
    st.button(
        "🆕 Première fois ? Créez votre 1er fichier Excel en cliquant ici",
        key="btn_first_excel",
        use_container_width=True,
        on_click=st.session_state.update,
        kwargs={"xlsx_new": True},
        help=(
            "Crée un fichier de contrôle Excel vide. Vos rapports y seront "
            "ajoutés ; téléchargez-le ensuite (bloc « Fichier de contrôle "
            "Excel », en bas à droite) et rechargez-le aux prochains contrôles."
        ),
    )


# --------------------------------------------------------------------------- #
# Bloc : Fichier de contrôle Excel
# --------------------------------------------------------------------------- #
def _render_excel(controller: str) -> None:
    with st.container(border=True):
        st.markdown(
            '<p class="section-title sec-xlsx">Fichier de contrôle Excel</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="section-sub">Chargez votre fichier, puis cliquez sur '
            "« Enregistrer dans Excel » à chaque contrôle : il est ajouté au "
            "fichier, trié par date puis par heure. Téléchargez-le ensuite pour "
            "le conserver sur votre poste.</p>",
            unsafe_allow_html=True,
        )
        st.file_uploader(
            "Mettre à jour votre fichier de contrôle",
            type=["xlsx"],
            key="xlsx_upload",
            help=(
                "Le fichier Excel (.xlsx) téléchargé lors de votre dernier "
                "contrôle. Première fois : utilisez le bouton rouge en haut "
                "à droite de la page."
            ),
        )

        st.button(
            "💾 Enregistrer dans Excel",
            type="primary",
            use_container_width=True,
            on_click=_save_to_excel,
            help=(
                "Ajoute le contrôle saisi (date, heure, agence, points de "
                "contrôle, observations) au fichier de contrôle. Un contrôle "
                "déjà enregistré (même date, heure et contrôleur) est mis à jour."
            ),
        )
        message = st.session_state.pop("excel_msg", None)
        if message:
            kind, text = message
            (st.success if kind == "success" else st.error)(text)

        state = _excel_state()
        if state["error"]:
            st.error(state["error"])
            return

        if state["name"]:
            st.caption(
                f"📗 {state['name']} — {state['base_count']} contrôle(s) "
                "déjà dans le fichier."
            )
        elif state["created"]:
            st.info(
                "Nouveau fichier de contrôle créé. Enregistrez-y vos contrôles "
                "(« Enregistrer dans Excel »), téléchargez-le puis rechargez-le "
                "aux prochains contrôles.",
                icon="🆕",
            )
        else:
            session_note = (
                "\n\nSans fichier, le fichier téléchargé ne contiendra que "
                "les contrôles de cette session."
                if state["session_count"]
                else ""
            )
            st.warning(
                "**Aucun fichier Excel chargé.**\n\n"
                "- **Vous avez déjà un fichier ?** Chargez-le ci-dessus, dans "
                "« Mettre à jour votre fichier de contrôle ».\n"
                "- **Première fois ?** Créez votre fichier avec le bouton "
                "rouge **en haut à droite de la page**." + session_note,
                icon="⚠️",
            )

        if state["session_count"]:
            st.success(
                f"{state['session_count']} contrôle(s) de cette session "
                "enregistré(s) dans le fichier.",
                icon="✅",
            )

        st.download_button(
            "⬇️ Télécharger le fichier de contrôle",
            data=state["data"] or b"",
            file_name=_excel_download_name(controller),
            mime=_XLSX_MIME,
            type="primary" if state["session_count"] or state["created"] else "secondary",
            disabled=state["data"] is None,
            use_container_width=True,
        )
        if state["data"] is not None:
            total, last = excel_service.summarize(state["rows"])
            if total:
                st.caption(
                    f"{total} contrôle(s), dernier le {_fr_date(last)} — onglet "
                    "« Controles » (tous les contrôles) et un onglet par agence. "
                    "Enregistrez le fichier dans vos Téléchargements et "
                    "rechargez-le au prochain contrôle. Pensez à le télécharger "
                    "avant de fermer l'application."
                )
            else:
                st.warning(
                    "Le fichier ne contient encore aucun contrôle : remplissez "
                    "le formulaire puis cliquez sur « 💾 Enregistrer dans "
                    "Excel » avant de le télécharger.",
                    icon="⚠️",
                )

        with st.expander("🗑️ Supprimer un contrôle du fichier"):
            st.caption(
                "Indiquez la date, l'heure (colonne « Heure » du fichier) et le "
                "nom du contrôleur du contrôle à retirer."
            )
            d_date, d_time = st.columns(2)
            with d_date:
                st.date_input("Date", key="del_date", format="DD/MM/YYYY")
            with d_time:
                st.time_input("Heure", key="del_time", step=60)
            st.text_input("Nom du contrôleur", key="del_controller")
            st.button(
                "🗑️ Supprimer ce contrôle",
                use_container_width=True,
                on_click=_delete_from_excel,
                disabled=state["data"] is None,
            )


# --------------------------------------------------------------------------- #
# Bloc : Consultation des rapports (audit)
# --------------------------------------------------------------------------- #
def _collect_audit_rows(extra_files: list) -> tuple[list[dict], list[str]]:
    """
    Contrôles consultables : fichiers ajoutés + fichier de contrôle courant.

    Un même contrôle présent dans plusieurs fichiers n'est compté qu'une
    fois (même « Réf. ») ; la version du fichier courant l'emporte.
    """
    by_ref: dict = {}
    warnings: list[str] = []
    sources = [(upload.name, upload.getvalue()) for upload in extra_files or []]
    own = _excel_state()
    if own["data"] is not None:
        sources.append((own["name"] or "fichier de cette session", own["data"]))

    for name, data in sources:
        try:
            rows = _read_excel(data)
        except ExcelError as exc:
            warnings.append(f"« {name} » ignoré : {exc}")
            continue
        for row in rows:
            by_ref[row.get("report_id") or tuple(row.values())] = row

    rows = sorted(by_ref.values(), key=excel_service.sort_key, reverse=True)
    return rows, warnings


def _render_audit() -> None:
    st.markdown("---")
    with st.container(border=True):
        st.markdown(
            '<p class="section-title sec-audit">Consultation des rapports</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="section-sub">Recherche dans les fichiers de contrôle '
            "Excel : par agence et par période. Votre fichier (bloc « Fichier "
            "de contrôle Excel ») est inclus automatiquement.</p>",
            unsafe_allow_html=True,
        )

        extra_files = st.file_uploader(
            "Autres fichiers de contrôle à consulter (facultatif)",
            type=["xlsx"],
            accept_multiple_files=True,
            key="audit_files",
            help=(
                "Ajoutez les fichiers d'autres contrôleurs pour une vue "
                "d'ensemble. Ils sont seulement lus, jamais modifiés."
            ),
        )

        today = dt.date.today()
        c_scope, c_from, c_to = st.columns([2, 1, 1])
        with c_scope:
            scope = st.radio(
                "Périmètre",
                options=("Une agence", "Plusieurs agences", "Toutes les agences"),
                horizontal=True,
            )
        with c_from:
            date_from = st.date_input("Du", value=today.replace(day=1))
        with c_to:
            date_to = st.date_input("Au", value=today)

        selected: list[str] = []
        if scope == "Une agence":
            one = st.selectbox(
                "Agence", options=BRANCHES, index=None,
                placeholder="Sélectionnez une agence",
            )
            selected = [one] if one else []
        elif scope == "Plusieurs agences":
            selected = st.multiselect(
                "Agences", options=BRANCHES, placeholder="Sélectionnez les agences"
            )

        if st.button("🔍 Afficher les rapports", type="primary"):
            if scope != "Toutes les agences" and not selected:
                st.error("Sélectionnez au moins une agence.")
            elif date_from > date_to:
                st.error("La date de début est postérieure à la date de fin.")
            else:
                all_rows, warnings = _collect_audit_rows(extra_files)
                for warning in warnings:
                    st.warning(warning)
                start, end = date_from.isoformat(), date_to.isoformat()
                rows = [
                    row for row in all_rows
                    if start <= row.get("date_controle", "") <= end
                    and (not selected or row.get("agence") in selected)
                ]
                scope_label = (
                    "Toutes les agences"
                    if scope == "Toutes les agences"
                    else ", ".join(selected)
                )
                st.session_state["audit"] = {
                    "rows": rows,
                    "sources_empty": not all_rows,
                    "subtitle": (
                        f"{scope_label} — du {date_from.strftime('%d/%m/%Y')} "
                        f"au {date_to.strftime('%d/%m/%Y')}"
                    ),
                    "stamp": dt.datetime.now().strftime("%Y%m%d_%H%M"),
                }

        audit = st.session_state.get("audit")
        if not audit:
            return

        rows = audit["rows"]
        st.caption(audit["subtitle"])
        if audit.get("sources_empty"):
            st.info(
                "Aucun contrôle à consulter : chargez votre fichier de "
                "contrôle Excel, ou ajoutez des fichiers ci-dessus."
            )
            return
        if not rows:
            st.info("Aucun rapport ne correspond à ces critères.")
            return

        problems = sum(1 for row in rows if (row.get("nb_problemes") or "0") != "0")
        m1, m2, m3 = st.columns(3)
        m1.metric("Rapports", len(rows))
        m2.metric("Avec anomalie", problems)
        m3.metric("Agences couvertes", len({row.get("agence", "") for row in rows}))

        st.markdown(
            _build_audit_table(rows, _AUDIT_DISPLAY_COLUMNS), unsafe_allow_html=True
        )

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "⬇️ Télécharger en HTML",
                data=_build_audit_document(rows, audit["subtitle"]).encode("utf-8"),
                file_name=f"rapports_controle_n1_{audit['stamp']}.html",
                mime="text/html",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "⬇️ Télécharger en Excel",
                data=_merge_excel(None, rows),
                file_name=f"rapports_controle_n1_{audit['stamp']}.xlsx",
                mime=_XLSX_MIME,
                use_container_width=True,
            )


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🗂️", layout="wide")
    _bootstrap()
    _init_state(load_config())

    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    _inject_status_css()

    _render_sidebar()

    # En-tête : logo en haut à gauche, titre, et à droite le bouton de
    # création du premier fichier Excel (à l'écart des blocs d'opérations).
    if LOGO_PATH.exists():
        logo_col, title_col, first_col = st.columns([1, 6.2, 2.8])
        with logo_col:
            # Décale le logo vers le bas pour qu'il ne passe pas sous la barre Streamlit.
            st.markdown('<div style="height: 40px"></div>', unsafe_allow_html=True)
            st.image(str(LOGO_PATH), width=120)
    else:
        title_col, first_col = st.columns([7.2, 2.8])
    with title_col:
        st.title(APP_TITLE)
        st.caption(APP_SUBTITLE)
    with first_col:
        _render_first_time_button()

    # ----- Zone haute : Informations générales (3 colonnes) -----
    with st.container(border=True):
        st.markdown('<p class="section-title sec-info">Informations générales</p>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([3, 3, 2, 1.6])
        with c1:
            controller = st.text_input(
                "Nom du contrôleur *", key="controller", placeholder="Ex. : Prénom Nom",
            )
        with c2:
            st.selectbox(
                "Agence *", options=BRANCHES, index=None, key="branch",
                placeholder="Sélectionnez une agence",
            )
        with c3:
            st.date_input("Date du contrôle *", key="control_date", format="DD/MM/YYYY")
        with c4:
            st.time_input("Heure *", key="control_time", step=60)

    # ----- Zone centrale : Contrôle niveau 1 -----
    _render_control_block()

    # ----- Observations (gauche) | Documents scannés (droite) -----
    col_obs, col_docs = st.columns(2)
    with col_obs:
        with st.container(border=True):
            st.markdown('<p class="section-title sec-obs">Observations générales</p>', unsafe_allow_html=True)
            st.markdown('<p class="section-sub">Facultatif</p>', unsafe_allow_html=True)
            st.text_area(
                "Observations générales",
                key="observations",
                placeholder="Remarques générales sur le contrôle...",
                label_visibility="collapsed",
            )
    with col_docs:
        with st.container(border=True):
            st.markdown('<p class="section-title sec-doc">Documents scannés</p>', unsafe_allow_html=True)
            st.markdown(
                '<p class="section-sub">PDF, JPG, JPEG, PNG — les images sont '
                "converties en PDF.</p>",
                unsafe_allow_html=True,
            )
            uploaded_files = st.file_uploader(
                "Documents scannés",
                type=list(ALLOWED_UPLOAD_EXTENSIONS),
                accept_multiple_files=True,
                label_visibility="collapsed",
            )


    # ----- Bas : Actions du rapport PDF (gauche) | Fichier Excel (droite) -----
    # Les actions sont exécutées en premier : un rapport créé à l'instant
    # figure déjà dans le fichier Excel affiché à droite.
    col_pdf, col_xlsx = st.columns(2)
    with col_pdf:
        _render_actions(uploaded_files)
    with col_xlsx:
        _render_excel(controller)

    # ----- Bas de page : consultation des fichiers de contrôle -----
    _render_audit()


if __name__ == "__main__":
    main()
