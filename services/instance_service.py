"""
Instance unique par dossier de données.

Un verrou du système (fichier instance.lock) est pris par le processus qui
sert l'application ; il est libéré automatiquement à la fin du processus,
même brutale. Ce processus écrit ensuite instance.json (port, identifiant
aléatoire de l'instance). Un second lancement qui ne peut pas prendre le
verrou lit ce fichier et rouvre le navigateur sur l'instance existante,
après avoir vérifié qu'elle répond bien avec cet identifiant : un autre
service sur le même port, ou l'instance d'un autre utilisateur du poste,
n'est jamais pris pour la nôtre.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from constants import USER_DIR

LOCK_PATH: Path = USER_DIR / "instance.lock"
INFO_PATH: Path = USER_DIR / "instance.json"


class InstanceLock:
    """Verrou exclusif non bloquant, conservé pendant toute la vie du processus."""

    def __init__(self, path: Path = LOCK_PATH) -> None:
        self._path = path
        self._handle = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True


def new_instance_id() -> str:
    return uuid.uuid4().hex


def write_info(port: int, instance_id: str, version: str) -> None:
    """Écrit instance.json de façon atomique."""
    temp = INFO_PATH.with_name(f".instance.{uuid.uuid4().hex}.tmp")
    temp.write_text(
        json.dumps({"port": port, "instance": instance_id, "version": version, "pid": os.getpid()}),
        encoding="utf-8",
    )
    os.replace(temp, INFO_PATH)


def read_info() -> dict | None:
    try:
        info = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return info if isinstance(info, dict) else None


def probe(host: str, port: int, timeout: float = 0.5) -> dict | None:
    """
    Réponse de /api/identity sur ce port, ou None. N'importe quel service
    peut écouter sur le port : toute réponse inattendue vaut None.
    """
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://{host}:{port}/api/identity", timeout=timeout) as response:
            value = json.loads(response.read(4096))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def find_running(host: str, app_id: str, wait: float) -> tuple[int, dict] | None:
    """
    Instance de ce dossier de données qui répond (port, identité), en
    attendant au plus `wait` secondes qu'elle ait fini de démarrer.
    """
    deadline = time.monotonic() + wait
    while True:
        info = read_info()
        if info and isinstance(info.get("port"), int):
            identity = probe(host, info["port"])
            if (
                identity
                and identity.get("app_id") == app_id
                and identity.get("instance") == info.get("instance")
            ):
                return info["port"], identity
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)
