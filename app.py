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

import datetime as dt

import streamlit as st

from constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    APP_SUBTITLE,
    APP_TITLE,
    BRANCHES,
    CONTROL_ITEMS,
    STATUS_OK,
    STATUS_PROBLEM,
)
from services import db_service
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

/* Titres de section dans les cartes */
.section-title { font-size: 1.05rem; font-weight: 700; color: #1f2d3d;
  margin: 0 0 .15rem 0; }
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

        control_id = db_service.insert_control(
            db_service.ControlRecord(
                branch_name=branch,
                controller_name=controller.strip(),
                control_date=control_date_str,
                statuses=statuses,
                observations=observations,
                pdf_path=str(pdf_path),
                problem_comments=problem_comments,
            )
        )
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

        st.markdown("### Historique local")
        rows = db_service.get_recent_controls(limit=8)
        if not rows:
            st.caption("Aucun rapport enregistré pour le moment.")
            return
        for row in rows:
            badge = "🟢" if row["email_sent"] else "⚪"
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
        st.markdown('<p class="section-title">Contrôle niveau 1</p>', unsafe_allow_html=True)
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
        st.markdown('<p class="section-title">Actions du rapport</p>', unsafe_allow_html=True)

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
        st.markdown('<p class="section-title">Informations générales</p>', unsafe_allow_html=True)
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
            st.markdown('<p class="section-title">Observations générales</p>', unsafe_allow_html=True)
            st.markdown('<p class="section-sub">Facultatif</p>', unsafe_allow_html=True)
            observations = st.text_area(
                "Observations générales",
                key="observations",
                placeholder="Remarques générales sur le contrôle...",
                label_visibility="collapsed",
            )
    with col_right:
        with st.container(border=True):
            st.markdown('<p class="section-title">Documents scannés</p>', unsafe_allow_html=True)
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


if __name__ == "__main__":
    main()
