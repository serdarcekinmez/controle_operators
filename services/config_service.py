"""
Service de configuration.

Lit le fichier facultatif config.json (poste local, non versionné). Il ne
contient plus aucun identifiant : seulement des préférences, comme le nom
du contrôleur proposé par défaut. Sans lui, l'application fonctionne.
"""

from __future__ import annotations

import json

from constants import CONFIG_PATH
from services.logging_service import get_logger

logger = get_logger()


def load_config() -> dict:
    """Charge config.json. Retourne {} s'il est absent ou illisible."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("config.json invalide (JSON) : %s", exc)
        return {}
    except OSError as exc:
        logger.error("Impossible de lire config.json : %s", exc)
        return {}
    return config if isinstance(config, dict) else {}
