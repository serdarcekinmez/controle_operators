"""
Service d'envoi d'email via Gmail SMTP (SSL).

Le PDF final fusionné est la SEULE pièce jointe (les images d'origine ne
sont pas jointes séparément). Les identifiants proviennent de config.json.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from constants import (
    CONTROL_ITEMS,
    SMTP_HOST,
    SMTP_PORT,
    STATUS_PROBLEM,
    status_label,
)
from services.logging_service import get_logger

logger = get_logger()


class EmailError(Exception):
    """Erreur d'envoi d'email avec message déjà adapté à l'utilisateur."""


def build_subject(branch: str, control_date: str, controller: str) -> str:
    """[Contrôle N1] {branch} - {date} - {controller}"""
    return f"[Contrôle N1] {branch} - {control_date} - {controller}"


def build_body(
    branch: str,
    control_date: str,
    controller: str,
    statuses: dict[str, str],
    problem_comments: dict[str, str],
    observations: str,
) -> str:
    """Corps de l'email en français, avec le résumé de la checklist."""
    lines = [
        "Bonjour,",
        "",
        "Veuillez trouver ci-joint le rapport de contrôle niveau 1.",
        "",
        f"Agence : {branch}",
        f"Date du contrôle : {control_date}",
        f"Contrôleur : {controller}",
        "",
        "Résumé :",
    ]
    for key, label in CONTROL_ITEMS:
        lines.append(f"- {label} : {status_label(statuses.get(key) or '')}")

    # Section dédiée listant les points en problème et leur commentaire.
    problems = [
        (label, (problem_comments.get(key) or "").strip())
        for key, label in CONTROL_ITEMS
        if (statuses.get(key) or "") == STATUS_PROBLEM
    ]
    if problems:
        lines += ["", "Points avec problème :"]
        for label, comment in problems:
            lines.append(f"- {label} : {comment or '(sans commentaire)'}")

    lines += [
        "",
        "Observations :",
        observations.strip() or "Aucune observation.",
        "",
        "Cordialement,",
        "Application de contrôle agences",
    ]
    return "\n".join(lines)


def send_report(
    config: dict,
    subject: str,
    body: str,
    attachment_path: Path,
) -> None:
    """
    Envoie le rapport par email. Lève EmailError (message français) en cas
    d'échec ; les détails techniques sont journalisés.
    """
    attachment_path = Path(attachment_path)
    if not attachment_path.exists():
        raise EmailError("Le PDF à envoyer est introuvable sur le disque.")

    sender = config["smtp_email"]
    password = config["smtp_app_password"]
    recipient = config["recipient_email"]

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        data = attachment_path.read_bytes()
    except OSError as exc:
        logger.error("Lecture du PDF impossible : %s", exc)
        raise EmailError("Impossible de lire le PDF à joindre.") from exc

    message.add_attachment(
        data,
        maintype="application",
        subtype="pdf",
        filename=attachment_path.name,
    )

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
            server.login(sender, password)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("Authentification SMTP refusée : %s", exc)
        raise EmailError(
            "Authentification Gmail refusée. Vérifiez l'adresse et le "
            "« mot de passe d'application » dans config.json."
        ) from exc
    except (smtplib.SMTPException, ssl.SSLError) as exc:
        logger.error("Erreur SMTP : %s", exc)
        raise EmailError(
            "Erreur lors de l'envoi via Gmail (problème SMTP). "
            "Réessayez plus tard."
        ) from exc
    except (TimeoutError, OSError) as exc:
        logger.error("Connexion SMTP impossible : %s", exc)
        raise EmailError(
            "Connexion au serveur Gmail impossible. Vérifiez votre "
            "connexion internet."
        ) from exc

    logger.info(
        "Email envoyé à %s (sujet : %s, pièce jointe : %s)",
        recipient,
        subject,
        attachment_path.name,
    )
