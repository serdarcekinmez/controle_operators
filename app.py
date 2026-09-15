"""
Application de contrôle agences — Contrôle niveau 1.

Application Streamlit LOCALE (poste de travail). Aucune donnée client :
uniquement le suivi des points de contrôle interne d'une agence.

Flux : saisie -> génération d'UN PDF final (rapport + pièces jointes
converties/fusionnées) -> envoi par Gmail SMTP vers la boîte partagée.

Mise en page : disposition « bureau » compacte, en blocs/cartes, avec un
choix de statut OK / Problème par point de contrôle.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import io

import streamlit as st

from constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    APP_SUBTITLE,
    APP_TITLE,
    BRANCHES,
    CONTROL_ITEMS,
    SHEET_COLUMN_LABELS,
    SHEET_COLUMNS,
    SHEET_PROBLEM_PREFIX,
    SHEET_VALUE_OK,
    STATUS_OK,
    STATUS_PROBLEM,
)
from services import db_service, sheets_service
from services.config_service import get_config_status
from services.email_service import (
    EmailError,
    build_body,
    build_subject,
    send_report,
)
from services.file_service import (
    ensure_directories,
    get_extension,
    is_allowed_upload,
    is_image,
    save_report_pdf,
    save_uploaded_file,
)
from services.logging_service import get_logger
from services.sheets_service import SheetsError
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
.sec-sync   { color: #15803d; border-left-color: #15803d; }
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

/* Bannière de configuration compacte */
.config-banner { background: #fff8e1; border: 1px solid #f4d35e; color: #7a5b00;
  padding: .5rem .8rem; border-radius: .5rem; font-size: .85rem;
  margin-bottom: .8rem; }

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


def _init_state() -> None:
    if "statuses" not in st.session_state:
        st.session_state.statuses = {key: None for key, _ in CONTROL_ITEMS}


def _set_status(key: str, value: str) -> None:
    """Callback des boutons de statut : sélection exclusive, re-clic = annule."""
    current = st.session_state.statuses.get(key)
    st.session_state.statuses[key] = None if current == value else value


# --------------------------------------------------------------------------- #
# Collecte des données du formulaire
# --------------------------------------------------------------------------- #
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
def _handle_generate(
    controller: str,
    branch: str | None,
    control_date: dt.date,
    observations: str,
    uploaded_files: list,
) -> None:
    statuses = _collect_statuses()
    problem_comments = _collect_problem_comments()

    # --- Validation des champs obligatoires ---
    errors: list[str] = []
    if not controller.strip():
        errors.append("le nom du contrôleur")
    if not branch:
        errors.append("l'agence")
    if errors:
        st.error("Champs obligatoires manquants : " + ", ".join(errors) + ".")
        return

    # --- Validation : tout "Problème" doit être commenté ---
    missing_comments = [
        label
        for key, label in CONTROL_ITEMS
        if statuses.get(key) == STATUS_PROBLEM and not problem_comments.get(key)
    ]
    if missing_comments:
        st.error(
            "Un commentaire est obligatoire pour chaque problème signalé : "
            + ", ".join(missing_comments)
            + "."
        )
        return

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
        control_date=control_date_str,
        controller=controller.strip(),
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
            controller_name=controller.strip(),
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

    st.session_state["report"] = {
        "pdf_bytes": result.pdf_bytes,
        "pdf_path": str(pdf_path),
        "filename": pdf_path.name,
        "control_id": control_id,
        "report_id": report_id,
        "drive_url": "",
        "branch": branch,
        "control_date": control_date_str,
        "controller": controller.strip(),
        "statuses": statuses,
        "problem_comments": problem_comments,
        "observations": observations,
        "email_sent": False,
    }
    st.success(f"PDF généré avec succès : {pdf_path.name}")


# --------------------------------------------------------------------------- #
# Action : envoyer le rapport
# --------------------------------------------------------------------------- #
def _handle_send(config: dict) -> None:
    report = st.session_state.get("report")
    if not report:
        st.error("Aucun rapport généré. Cliquez d'abord sur « Créer le rapport PDF ».")
        return
    if report.get("email_sent"):
        st.info("Ce rapport a déjà été envoyé.")
        return

    subject = build_subject(
        report["branch"], report["control_date"], report["controller"]
    )
    body = build_body(
        report["branch"],
        report["control_date"],
        report["controller"],
        report["statuses"],
        report["problem_comments"],
        report["observations"],
    )

    with st.spinner("Envoi du rapport par email..."):
        try:
            send_report(config, subject, body, report["pdf_path"])
        except EmailError as exc:
            st.error(str(exc))
            if report.get("control_id") is not None:
                db_service.update_email_status(
                    report["control_id"], sent=False, error=str(exc)
                )
            return
        except Exception:
            logger.exception("Échec inattendu de l'envoi email.")
            st.error(
                "Une erreur inattendue est survenue lors de l'envoi. "
                "Consultez logs/app.log."
            )
            return

    report["email_sent"] = True
    st.session_state["report"] = report
    if report.get("control_id") is not None:
        db_service.update_email_status(report["control_id"], sent=True)
    st.success(f"Rapport envoyé à {config['recipient_email']}.")


# --------------------------------------------------------------------------- #
# Action : mettre à jour le tableau Google Sheets
# --------------------------------------------------------------------------- #
def _handle_sync(config: dict | None) -> None:
    """
    Pousse vers la feuille tous les contrôles pas encore synchronisés.

    Le dernier contrôle comme les précédents restés en attente (réseau
    coupé, application fermée trop tôt) partent dans le même envoi.
    """
    # Le message est mis en attente (« flash ») : l'écran est rechargé juste
    # après pour rafraîchir les compteurs, ce qui effacerait un st.success().
    pending = db_service.get_pending_controls()
    if not pending:
        st.session_state["sync_flash"] = (
            "info", "Tous les contrôles enregistrés sont déjà dans le tableau."
        )
        return

    rows = [sheets_service.build_sheet_row(row) for row in pending]
    with st.spinner(f"Mise à jour du tableau ({len(rows)} contrôle(s))..."):
        try:
            result = sheets_service.push_rows(config, rows)
        except SheetsError as exc:
            st.session_state["sync_flash"] = ("error", str(exc))
            return
        except Exception:
            logger.exception("Échec inattendu de la synchronisation.")
            st.session_state["sync_flash"] = (
                "error",
                "Une erreur inattendue est survenue pendant la mise à jour "
                "du tableau. Consultez logs/app.log.",
            )
            return

    db_service.mark_synced([int(row["id"]) for row in pending])

    details = []
    if result.added:
        details.append(f"{result.added} ajouté(s)")
    if result.updated:
        details.append(f"{result.updated} mis à jour")
    st.session_state["sync_flash"] = (
        "success", "Tableau mis à jour : " + ", ".join(details) + "."
    )


# --------------------------------------------------------------------------- #
# Action : déposer le PDF sur le Drive
# --------------------------------------------------------------------------- #
def _handle_drive_upload(config: dict | None) -> None:
    """Dépose le PDF du rapport courant dans le Drive du compte d'archivage."""
    report = st.session_state.get("report")
    if not report:
        st.error("Aucun rapport généré. Cliquez d'abord sur « Créer le rapport PDF ».")
        return
    if report.get("drive_url"):
        st.info("Ce rapport est déjà déposé sur le Drive.")
        return

    with st.spinner("Dépôt du PDF sur le Drive..."):
        try:
            url = sheets_service.upload_pdf(
                config,
                report.get("report_id", ""),
                report["filename"],
                report["pdf_bytes"],
            )
        except SheetsError as exc:
            st.error(str(exc))
            return
        except Exception:
            logger.exception("Échec inattendu du dépôt Drive.")
            st.error(
                "Une erreur inattendue est survenue pendant le dépôt du PDF. "
                "Consultez logs/app.log."
            )
            return

    report["drive_url"] = url
    st.session_state["report"] = report
    if report.get("control_id") is not None:
        db_service.set_drive_url(report["control_id"], url)
    st.success("PDF déposé sur le Drive du compte d\'archivage.")


# --------------------------------------------------------------------------- #
# Consultation : construction du tableau HTML
# --------------------------------------------------------------------------- #
# Colonnes affichées à l\'écran (les autres restent dans les exports).
_AUDIT_DISPLAY_COLUMNS = [
    "date_controle",
    "agence",
    "controleur",
    "journee_comptable",
    "caisses",
    "acr",
    "affichage",
    "affichage_obligatoire",
    "nb_problemes",
    "observations",
    "lien_drive",
]


def _escape(value: str) -> str:
    return html.escape(str(value or ""))


def _cell(column: str, value: str) -> str:
    """Cellule HTML avec la classe de couleur qui convient."""
    text = str(value or "")
    if column == "lien_drive":
        if text.startswith("http"):
            return f'<td><a href="{_escape(text)}" target="_blank">Ouvrir</a></td>'
        return '<td class="na">—</td>'
    if column == "nb_problemes":
        hot = " hot" if text not in ("", "0") else ""
        return f'<td class="num{hot}">{_escape(text)}</td>'
    if text == SHEET_VALUE_OK:
        return f'<td class="ras">{_escape(text)}</td>'
    if text.startswith(SHEET_PROBLEM_PREFIX):
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


def _build_audit_csv(rows: list[dict]) -> bytes:
    """Export CSV ouvrable directement dans Excel (séparateur point-virgule)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([SHEET_COLUMN_LABELS.get(col, col) for col in SHEET_COLUMNS])
    for row in rows:
        writer.writerow([row.get(col, "") for col in SHEET_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")


# --------------------------------------------------------------------------- #
# Barre latérale : configuration (légère) + historique
# --------------------------------------------------------------------------- #
def _render_sidebar(config_status) -> None:
    with st.sidebar:
        st.markdown("### Configuration")
        if config_status.ok:
            st.success("E-mail prêt", icon="✅")
        else:
            st.warning("À configurer", icon="⚠️")
            st.caption(config_status.message)

        st.markdown("### Google Sheets")
        if sheets_service.is_configured(config_status.config):
            pending = db_service.count_pending()
            if pending:
                st.warning(f"{pending} contrôle(s) à envoyer", icon="⏳")
            else:
                st.success("Tableau à jour", icon="✅")
        else:
            st.caption("Liaison non configurée (facultatif).")

        st.markdown("### Historique local")
        rows = db_service.get_recent_controls(limit=8)
        if not rows:
            st.caption("Aucun rapport enregistré pour le moment.")
            return
        for row in rows:
            badge = "🟢" if row["email_sent"] else "⚪"
            badge += "📊" if row["sheet_synced"] else ""
            st.caption(
                f"{badge} **{row['branch_name']}** — {row['control_date']} · "
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
            '<p class="section-sub">Choisissez OK (vert) ou Problème (rouge) pour '
            "chaque point — un commentaire est requis en cas de problème. "
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
                    "Problème", key=f"btn_pb_{key}", use_container_width=True,
                    on_click=_set_status, args=(key, STATUS_PROBLEM),
                )
            # Commentaire conditionnel, lié à ce point précis.
            if st.session_state.statuses.get(key) == STATUS_PROBLEM:
                _, c_comment = st.columns([0.3, 9.7])
                with c_comment:
                    st.text_area(
                        "Commentaire / détail du problème (obligatoire)",
                        key=f"comment_{key}",
                        placeholder="Décrivez le problème constaté...",
                    )


# --------------------------------------------------------------------------- #
# Bloc : Actions du rapport (boutons d'action visibles)
# --------------------------------------------------------------------------- #
def _render_actions(
    controller: str,
    branch: str | None,
    control_date: dt.date,
    observations: str,
    uploaded_files: list,
    config_status,
) -> None:
    with st.container(border=True):
        st.markdown('<p class="section-title sec-act">Actions du rapport</p>', unsafe_allow_html=True)

        if st.button("🖼️ Convertir en PDF", use_container_width=True):
            _handle_convert(uploaded_files)

        if st.button(
            "📄 Créer le rapport PDF", type="primary", use_container_width=True
        ):
            _handle_generate(
                controller=controller,
                branch=branch,
                control_date=control_date,
                observations=observations,
                uploaded_files=uploaded_files,
            )

        report = st.session_state.get("report")
        send_disabled = (
            not report or report.get("email_sent", False) or not config_status.ok
        )
        if st.button(
            "📧 Envoyer le rapport",
            type="primary",
            use_container_width=True,
            disabled=send_disabled,
        ):
            _handle_send(config_status.config)

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
            if report.get("email_sent"):
                st.success("Statut : rapport envoyé", icon="✅")
            else:
                st.info("Statut : PDF généré, non envoyé", icon="📄")
            st.caption(f"Fichier : {report['filename']}")
        else:
            st.caption("Aucun rapport généré pour l'instant.")

        if not config_status.ok:
            st.caption("ℹ️ L'envoi est désactivé tant que config.json n'est pas renseigné.")


# --------------------------------------------------------------------------- #
# Bloc : Synchronisation Google Sheets / Drive
# --------------------------------------------------------------------------- #
def _render_sync(config_status) -> None:
    config = config_status.config
    linked = sheets_service.is_configured(config)
    pending = db_service.count_pending()
    report = st.session_state.get("report")

    with st.container(border=True):
        st.markdown(
            '<p class="section-title sec-sync">Tableau de suivi</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="section-sub">Google Sheets du compte d\'archivage.</p>',
            unsafe_allow_html=True,
        )

        # Message de la dernière synchronisation (survit au rechargement).
        flash = st.session_state.pop("sync_flash", None)
        if flash:
            {"success": st.success, "info": st.info, "error": st.error}[flash[0]](
                flash[1]
            )

        label = "🔄 Mettre à jour le tableau"
        if pending:
            label += f" ({pending})"
        if st.button(
            label,
            use_container_width=True,
            disabled=not linked or pending == 0,
            help="Envoie vers Google Sheets les contrôles pas encore synchronisés.",
        ):
            _handle_sync(config)
            st.rerun()

        drive_done = bool(report and report.get("drive_url"))
        if st.button(
            "☁️ Ajouter le rapport PDF au Drive",
            use_container_width=True,
            disabled=not linked or not report or drive_done,
            help="Facultatif : dépose le PDF final dans le Drive du compte.",
        ):
            _handle_drive_upload(config)

        if not linked:
            st.caption(
                "ℹ️ Liaison Google non configurée (voir README, section "
                "« Google Sheets »)."
            )
        elif pending:
            st.caption(f"⏳ {pending} contrôle(s) en attente d\'envoi.")
        else:
            st.caption("✅ Tous les contrôles sont dans le tableau.")

        if drive_done:
            st.markdown(f"[📎 Voir le PDF sur le Drive]({report['drive_url']})")


# --------------------------------------------------------------------------- #
# Bloc : Consultation des rapports (audit)
# --------------------------------------------------------------------------- #
def _render_audit(config_status) -> None:
    config = config_status.config
    linked = sheets_service.is_configured(config)

    st.markdown("---")
    with st.container(border=True):
        st.markdown(
            '<p class="section-title sec-audit">Consultation des rapports</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="section-sub">Recherche dans le tableau central : '
            "par agence et par période.</p>",
            unsafe_allow_html=True,
        )

        if not linked:
            st.caption(
                "ℹ️ La consultation nécessite la liaison Google "
                "(voir README, section « Google Sheets »)."
            )
            return

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
                with st.spinner("Lecture du tableau..."):
                    try:
                        rows = sheets_service.query_rows(
                            config,
                            branches=selected,
                            date_from=date_from.isoformat(),
                            date_to=date_to.isoformat(),
                        )
                    except SheetsError as exc:
                        st.error(str(exc))
                        rows = None
                    except Exception:
                        logger.exception("Échec inattendu de la consultation.")
                        st.error(
                            "Une erreur inattendue est survenue pendant la "
                            "lecture du tableau. Consultez logs/app.log."
                        )
                        rows = None
                if rows is not None:
                    scope_label = (
                        "Toutes les agences"
                        if scope == "Toutes les agences"
                        else ", ".join(selected)
                    )
                    st.session_state["audit"] = {
                        "rows": rows,
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
        if not rows:
            st.info("Aucun rapport ne correspond à ces critères.")
            return

        problems = sum(1 for row in rows if (row.get("nb_problemes") or "0") != "0")
        m1, m2, m3 = st.columns(3)
        m1.metric("Rapports", len(rows))
        m2.metric("Avec problème", problems)
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
                "⬇️ Télécharger pour Excel (CSV)",
                data=_build_audit_csv(rows),
                file_name=f"rapports_controle_n1_{audit['stamp']}.csv",
                mime="text/csv",
                use_container_width=True,
            )


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🗂️", layout="wide")
    _bootstrap()
    _init_state()

    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    _inject_status_css()

    config_status = get_config_status()
    _render_sidebar(config_status)

    # En-tête
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    # Bannière config compacte (peu intrusive) — détail complet en sidebar.
    if not config_status.ok:
        st.markdown(
            '<div class="config-banner">⚠️ Envoi e-mail indisponible : '
            "config.json est manquant ou incomplet (voir le détail dans la "
            "barre latérale). La génération du PDF reste possible.</div>",
            unsafe_allow_html=True,
        )

    # ----- Zone haute : Informations générales (3 colonnes) -----
    with st.container(border=True):
        st.markdown('<p class="section-title sec-info">Informations générales</p>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            controller = st.text_input(
                "Nom du contrôleur *",
                value=(config_status.config or {}).get("default_controller_name", "") or "",
                placeholder="Ex. : Prénom Nom",
            )
        with c2:
            branch = st.selectbox(
                "Agence *", options=BRANCHES, index=None,
                placeholder="Sélectionnez une agence",
            )
        with c3:
            control_date = st.date_input("Date du contrôle *", value=dt.date.today())

    # ----- Zone centrale : Contrôle niveau 1 -----
    _render_control_block()

    # ----- Zone basse : Observations (gauche) | Documents + Actions (droite) -----
    col_obs, col_right = st.columns(2)
    with col_obs:
        with st.container(border=True):
            st.markdown('<p class="section-title sec-obs">Observations générales</p>', unsafe_allow_html=True)
            st.markdown('<p class="section-sub">Facultatif</p>', unsafe_allow_html=True)
            observations = st.text_area(
                "Observations générales",
                key="observations",
                placeholder="Remarques générales sur le contrôle...",
                label_visibility="collapsed",
            )
    with col_right:
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

        _render_actions(
            controller, branch, control_date, observations,
            uploaded_files, config_status,
        )
        _render_sync(config_status)

    # ----- Bas de page : consultation des rapports archivés -----
    _render_audit(config_status)


if __name__ == "__main__":
    main()
