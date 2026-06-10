"""
Service de configuration.

Charge et valide config.json. Ne contient JAMAIS de secret en dur :
les identifiants Gmail sont lus depuis config.json (non versionné).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from constants import (
    CONFIG_EXAMPLE_PATH,
    CONFIG_PATH,
    REQUIRED_CONFIG_KEYS,
)
from services.logging_service import get_logger

logger = get_logger()


@dataclass
class ConfigStatus:
    """Résultat de la vérification de la configuration."""

    ok: bool
    config: dict | None
    message: str


def load_config() -> dict | None:
    """Charge config.json. Retourne None si absent ou illisible."""
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("config.json invalide (JSON) : %s", exc)
        return None
    except OSError as exc:
        logger.error("Impossible de lire config.json : %s", exc)
        return None


def _looks_like_placeholder(value: str) -> bool:
    """Détecte les valeurs d'exemple non remplacées."""
    lowered = value.strip().lower()
    if not lowered:
        return True
    placeholders = ("xxxx", "votre", "example@", "placeholder", "à_remplir")
    return any(token in lowered for token in placeholders)


def get_config_status() -> ConfigStatus:
    """
    Vérifie la présence et la complétude de config.json.

    Retourne un ConfigStatus utilisable directement par l'UI.
    """
    if not CONFIG_PATH.exists():
        return ConfigStatus(
            ok=False,
            config=None,
            message=(
                "Le fichier config.json est introuvable. "
                f"Copiez « {CONFIG_EXAMPLE_PATH.name} » en « {CONFIG_PATH.name} » "
                "puis renseignez l'adresse Gmail et le mot de passe d'application."
            ),
        )

    config = load_config()
    if config is None:
        return ConfigStatus(
            ok=False,
            config=None,
            message=(
                "Le fichier config.json est illisible ou mal formé. "
                "Vérifiez qu'il s'agit bien d'un JSON valide "
                f"(voir le modèle « {CONFIG_EXAMPLE_PATH.name} »)."
            ),
        )

    # Vérification des clés obligatoires et de leur contenu.
    missing: list[str] = []
    for key in REQUIRED_CONFIG_KEYS:
        value = config.get(key, "")
        if not isinstance(value, str) or _looks_like_placeholder(value):
            missing.append(key)

    if missing:
        return ConfigStatus(
            ok=False,
            config=config,
            message=(
                "La configuration est incomplète. Champs à renseigner dans "
                f"config.json : {', '.join(missing)}. "
                "Pour le mot de passe, utilisez un « mot de passe d'application » "
                "Gmail (et non votre mot de passe principal)."
            ),
        )

    return ConfigStatus(ok=True, config=config, message="Configuration valide.")
