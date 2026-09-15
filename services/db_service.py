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
import uuid
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
    report_id                       TEXT,
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
    email_error                     TEXT,
    sheet_synced                    INTEGER NOT NULL DEFAULT 0,
    sheet_synced_at                 TEXT,
    drive_url                       TEXT
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
    report_id: str = ""

    def __post_init__(self) -> None:
        # Identifiant stable, utilisé comme clé d'unicité dans Google Sheets :
        # un même contrôle renvoyé deux fois met à jour la ligne au lieu
        # d'en créer une seconde.
        if not self.report_id:
            self.report_id = uuid.uuid4().hex[:12]


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Colonnes ajoutées après la première version : elles sont créées à la volée
# sur les bases existantes (pas de perte de données, pas de réinstallation).
_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("report_id", "TEXT"),
    ("sheet_synced", "INTEGER NOT NULL DEFAULT 0"),
    ("sheet_synced_at", "TEXT"),
    ("drive_url", "TEXT"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes manquantes sur une base déjà existante."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(controls)")}
    for column, definition in _MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE controls ADD COLUMN {column} {definition}")
            logger.info("Colonne ajoutée à la base locale : %s", column)

    # Les contrôles créés avant cette version n'ont pas de report_id. Sans lui,
    # la passerelle ignore la ligne : on en attribue un aux anciens rapports.
    orphans = conn.execute(
        "SELECT id FROM controls WHERE report_id IS NULL OR report_id = ''"
    ).fetchall()
    for row in orphans:
        conn.execute(
            "UPDATE controls SET report_id = ? WHERE id = ?",
            (uuid.uuid4().hex[:12], row["id"]),
        )
    if orphans:
        logger.info("Identifiants attribués à %s ancien(s) rapport(s).", len(orphans))


def init_db() -> None:
    """Crée les tables si elles n'existent pas, puis applique les migrations."""
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
            _migrate(conn)
    except sqlite3.Error as exc:
        logger.error("Initialisation de la base impossible : %s", exc)


def insert_control(record: ControlRecord) -> int | None:
    """Insère un contrôle et retourne son id local (ou None en cas d'erreur)."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO controls (
                    report_id, branch_name, controller_name, control_date,
                    created_at,
                    controle_journee_comptable, controle_caisses, controle_acr,
                    controle_affichage, controle_affichage_obligatoire,
                    problem_comments, observations, pdf_path, email_sent,
                    sheet_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    record.report_id,
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
    """
    Met à jour le statut d'envoi email d'un contrôle.

    Après un envoi réussi, le contrôle repasse en file d'attente : la colonne
    « E-mail » du tableau sera corrigée au prochain « Mettre à jour le tableau ».
    """
    sent_at = dt.datetime.now().isoformat(timespec="seconds") if sent else None
    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE controls
                   SET email_sent = ?, sent_at = ?, email_error = ?,
                       sheet_synced = CASE WHEN ? THEN 0 ELSE sheet_synced END
                 WHERE id = ?
                """,
                (int(sent), sent_at, error, int(sent), control_id),
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
                       created_at, email_sent, pdf_path, sheet_synced
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


# --------------------------------------------------------------------------- #
# Synchronisation Google Sheets
# --------------------------------------------------------------------------- #
_SYNC_FIELDS = """
    id, report_id, branch_name, controller_name, control_date, created_at,
    controle_journee_comptable, controle_caisses, controle_acr,
    controle_affichage, controle_affichage_obligatoire,
    problem_comments, observations, pdf_path, email_sent, drive_url
"""


def get_pending_controls(limit: int = 200) -> list[sqlite3.Row]:
    """
    Contrôles enregistrés localement mais pas encore poussés vers la feuille.

    C'est la file d'attente : si le réseau était indisponible au moment du
    contrôle, la ligne reste ici et repart au prochain clic sur
    « Mettre à jour le tableau ».
    """
    try:
        with _connect() as conn:
            cur = conn.execute(
                f"""
                SELECT {_SYNC_FIELDS}
                  FROM controls
                 WHERE COALESCE(sheet_synced, 0) = 0
                 ORDER BY id ASC
                 LIMIT ?
                """,
                (limit,),
            )
            return cur.fetchall()
    except sqlite3.Error as exc:
        logger.error("Lecture de la file de synchronisation impossible : %s", exc)
        return []


def get_control(control_id: int) -> sqlite3.Row | None:
    """Retourne un contrôle par son identifiant local."""
    try:
        with _connect() as conn:
            cur = conn.execute(
                f"SELECT {_SYNC_FIELDS} FROM controls WHERE id = ?", (control_id,)
            )
            return cur.fetchone()
    except sqlite3.Error as exc:
        logger.error("Lecture du contrôle %s impossible : %s", control_id, exc)
        return None


def count_pending() -> int:
    """Nombre de contrôles en attente de synchronisation."""
    try:
        with _connect() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM controls WHERE COALESCE(sheet_synced, 0) = 0"
            )
            return int(cur.fetchone()[0])
    except sqlite3.Error as exc:
        logger.error("Comptage des contrôles en attente impossible : %s", exc)
        return 0


def mark_synced(control_ids: list[int]) -> None:
    """Marque des contrôles comme présents dans la feuille."""
    if not control_ids:
        return
    now = dt.datetime.now().isoformat(timespec="seconds")
    placeholders = ",".join("?" for _ in control_ids)
    try:
        with _connect() as conn:
            conn.execute(
                f"""
                UPDATE controls
                   SET sheet_synced = 1, sheet_synced_at = ?
                 WHERE id IN ({placeholders})
                """,
                (now, *control_ids),
            )
    except sqlite3.Error as exc:
        logger.error("Mise à jour du statut de synchronisation impossible : %s", exc)


def set_drive_url(control_id: int, url: str) -> None:
    """
    Enregistre le lien Drive du PDF déposé.

    Le contrôle repasse en file d'attente pour que le lien apparaisse
    dans le tableau au prochain envoi.
    """
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE controls SET drive_url = ?, sheet_synced = 0 WHERE id = ?",
                (url, control_id),
            )
    except sqlite3.Error as exc:
        logger.error("Enregistrement du lien Drive impossible : %s", exc)
