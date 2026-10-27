"""
Service de journalisation.

Configure un logger unique écrivant dans logs/app.log (avec rotation)
ainsi que sur la sortie standard. Les détails techniques des erreurs
sont consignés ici ; l'UI n'affiche que des messages clairs en français.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from constants import LOG_PATH, LOGS_DIR

_LOGGER_NAME = "controle_agences"
_configured = False


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Retourne le logger applicatif, en le configurant une seule fois."""
    global _configured
    logger = logging.getLogger(name)

    if not _configured:
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Fichier tournant : 1 Mo par fichier, 3 archives. Un dossier de
        # données inaccessible ne doit pas empêcher l'import : le démarrage
        # le signale ensuite avec un message clair.
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
        except OSError:
            file_handler = None
        if file_handler is not None:
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Sortie console (absente dans l'exécutable sans fenêtre).
        if sys.stderr is not None:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        logger.propagate = False
        _configured = True

    return logger
