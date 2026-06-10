"""
Service SQLite : historique local des contrôles.

Deux tables : `controls` et `attachments`. Toutes les opérations sont
encapsulées ici. Les erreurs sont journalisées sans interrompre l'UI
(l'historique reste secondaire par rapport à la génération du PDF).
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field

from constants import DATA_DIR, DB_PATH
from services.logging_service import get_logger

logger = get_logger()

# Les colonnes de contrôle stockent désormais un statut texte :
# "ok" | "problem" | "" (non renseigné). Les commentaires des points en
# problème sont conservés en JSON dans problem_comments.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS controls (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_name                     TEXT NOT NULL,
    controller_name                 TEXT NOT NULL,
    control_date                    TEXT NOT NULL,
    created_at                      TEXT NOT NULL,
    controle_journee_comptable      TEXT NOT NULL DEFAULT '',
    controle_caisses                TEXT NOT NULL DEFAULT '',
    controle_acr                    TEXT NOT NULL DEFAULT '',
    controle_affichage              TEXT NOT NULL DEFAULT '',
    controle_affichage_obligatoire  TEXT NOT NULL DEFAULT '',
    problem_comments                TEXT,
    observations                    TEXT,
    pdf_path                        TEXT,
    email_sent                      INTEGER NOT NULL DEFAULT 0,
    sent_at                         TEXT,
    email_error                     TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    control_id          INTEGER NOT NULL,
    original_filename   TEXT NOT NULL,
    stored_path         TEXT,
    file_type           TEXT,
    uploaded_at         TEXT NOT NULL,
    FOREIGN KEY (control_id) REFERENCES controls(id)
);
"""


@dataclass
class ControlRecord:
    """Données d'un contrôle à insérer."""

    branch_name: str
    controller_name: str
    control_date: str
    statuses: dict[str, str]  # {clé: "ok"|"problem"|""}
    observations: str
    pdf_path: str
    problem_comments: dict[str, str] = field(default_factory=dict)


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crée les tables si elles n'existent pas."""
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error as exc:
        logger.error("Initialisation de la base impossible : %s", exc)


def insert_control(record: ControlRecord) -> int | None:
    """Insère un contrôle et retourne son id (ou None en cas d'erreur)."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO controls (
                    branch_name, controller_name, control_date, created_at,
                    controle_journee_comptable, controle_caisses, controle_acr,
                    controle_affichage, controle_affichage_obligatoire,
                    problem_comments, observations, pdf_path, email_sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    record.branch_name,
                    record.controller_name,
                    record.control_date,
                    now,
                    record.statuses.get("controle_journee_comptable", ""),
                    record.statuses.get("controle_caisses", ""),
                    record.statuses.get("controle_acr", ""),
                    record.statuses.get("controle_affichage", ""),
                    record.statuses.get("controle_affichage_obligatoire", ""),
                    json.dumps(record.problem_comments, ensure_ascii=False),
                    record.observations,
                    record.pdf_path,
                ),
            )
            return cur.lastrowid
    except sqlite3.Error as exc:
        logger.error("Insertion du contrôle impossible : %s", exc)
        return None


def insert_attachment(
    control_id: int, original_filename: str, stored_path: str, file_type: str
) -> None:
    """Enregistre un document joint lié à un contrôle."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO attachments (
                    control_id, original_filename, stored_path,
                    file_type, uploaded_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (control_id, original_filename, stored_path, file_type, now),
            )
    except sqlite3.Error as exc:
        logger.error("Insertion de la pièce jointe impossible : %s", exc)


def update_email_status(
    control_id: int, *, sent: bool, error: str | None = None
) -> None:
    """Met à jour le statut d'envoi email d'un contrôle."""
    sent_at = dt.datetime.now().isoformat(timespec="seconds") if sent else None
    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE controls
                   SET email_sent = ?, sent_at = ?, email_error = ?
                 WHERE id = ?
                """,
                (int(sent), sent_at, error, control_id),
            )
    except sqlite3.Error as exc:
        logger.error("Mise à jour du statut email impossible : %s", exc)


def get_recent_controls(limit: int = 10) -> list[sqlite3.Row]:
    """Retourne les derniers contrôles enregistrés (pour l'historique)."""
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                SELECT branch_name, controller_name, control_date,
                       created_at, email_sent, pdf_path
                  FROM controls
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (limit,),
            )
            return cur.fetchall()
    except sqlite3.Error as exc:
        logger.error("Lecture de l'historique impossible : %s", exc)
        return []
