"""
Point d'entrée de Contrôle Agences (exécutable Windows et « python server.py »).

Toute erreur de démarrage, y compris pendant l'import des modules ou la
création du dossier de données, est journalisée si possible et affichée :
boîte de dialogue Windows (indispensable pour l'exécutable sans console),
et sortie d'erreur quand elle existe.
"""

from __future__ import annotations

import os
import sys

TITLE = "Contrôle Agences"


def show_message(message: str, *, error: bool = True) -> None:
    """Affiche un message à l'utilisateur (boîte Windows et/ou sortie d'erreur)."""
    if sys.stderr is not None:
        try:
            print(message, file=sys.stderr, flush=True)
        except Exception:
            pass
    # CONTROLE_AGENCES_NO_DIALOG : tests automatisés (aucune fenêtre bloquante).
    if sys.platform == "win32" and not os.environ.get("CONTROLE_AGENCES_NO_DIALOG"):
        import ctypes

        # MB_ICONERROR / MB_ICONINFORMATION + MB_SETFOREGROUND + MB_TOPMOST
        flags = (0x10 if error else 0x40) | 0x10000 | 0x40000
        ctypes.windll.user32.MessageBoxW(None, message, TITLE, flags)


def _log_failure() -> None:
    try:
        from services.logging_service import get_logger

        get_logger().exception("Échec du démarrage")
    except Exception:
        pass


def run(load_main=None) -> None:
    # Console Windows : un accent ne doit jamais faire planter le lancement
    # (UTF-8 aussi quand la sortie est redirigée vers un fichier).
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        if load_main is None:
            from server import main  # import statique : visible par PyInstaller
        else:
            main = load_main()
        main()
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException as exc:
        _log_failure()
        try:
            from services.errors import StartupError

            known = isinstance(exc, StartupError)
        except Exception:
            known = False
        if known:
            message = str(exc)
        else:
            message = (
                "Impossible de démarrer Contrôle Agences.\n\n"
                f"{type(exc).__name__} : {exc}"
            )
        show_message(message)
        sys.exit(1)


if __name__ == "__main__":
    run()
