"""Erreurs de démarrage dont le message (en français) est affiché tel quel."""


class StartupError(RuntimeError):
    """Démarrage impossible : le message est montré à l'utilisateur."""
