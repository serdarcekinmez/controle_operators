"""
Contenu de l'e-mail du rapport (objet et corps), sans envoi.

L'envoi par e-mail n'est pas encore branché : il le sera plus tard via les
comptes Outlook / SharePoint (Microsoft 365) des agences et des directions.
Ces fonctions, indépendantes du service de messagerie, serviront alors à
composer le message ; le PDF final fusionné en sera la seule pièce jointe.
"""

from __future__ import annotations

from constants import CONTROL_ITEMS, STATUS_PROBLEM, status_label


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
        lines += ["", "Points avec anomalie :"]
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
