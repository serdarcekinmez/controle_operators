"""
Service de configuration.

Charge et valide la configuration. Ne contient JAMAIS de secret en dur :
les identifiants sont lus, dans cet ordre, depuis :
  1. config.json (poste local, non versionné) ;
  2. les « Secrets » de Streamlit Community Cloud (application en ligne,
     où config.json n'existe pas).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import streamlit as st

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


def load_secrets() -> dict | None:
    """
    Lit les Secrets Streamlit (Settings > Secrets sur Community Cloud).

    Retourne None s'il n'y en a pas (cas normal sur un poste local).
    """
    try:
        secrets = {key: st.secrets[key] for key in st.secrets.keys()}
    except Exception:  # aucun fichier secrets.toml / Secrets vides
        return None
    return secrets or None


def _looks_like_placeholder(value: str) -> bool:
    """Détecte les valeurs d'exemple non remplacées."""
    lowered = value.strip().lower()
    if not lowered:
        return True
    placeholders = ("xxxx", "votre", "example@", "placeholder", "à_remplir")
    return any(token in lowered for token in placeholders)


def get_config_status() -> ConfigStatus:
    """
    Vérifie la présence et la complétude de la configuration.

    Retourne un ConfigStatus utilisable directement par l'UI.
    """
    if CONFIG_PATH.exists():
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
    else:
        config = load_secrets()
        if config is None:
            return ConfigStatus(
                ok=False,
                config=None,
                message=(
                    "Aucune configuration trouvée. Sur ce poste : copiez "
                    f"« {CONFIG_EXAMPLE_PATH.name} » en « {CONFIG_PATH.name} » "
                    "puis renseignez l'adresse Gmail et le mot de passe "
                    "d'application. En ligne : renseignez les Secrets de "
                    "l'application Streamlit."
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
                "La configuration est incomplète. Champs à renseigner : "
                f"{', '.join(missing)}. "
                "Pour le mot de passe, utilisez un « mot de passe d'application » "
                "Gmail (et non votre mot de passe principal)."
            ),
        )

    return ConfigStatus(ok=True, config=config, message="Configuration valide.")
