"""
Cycle de vie au démarrage, sur le code source ou sur l'exécutable construit.

    python tests/check_startup.py                       # code source (server.py)
    python tests/check_startup.py dist/ControleAgences.exe

Exige les ports 8600 à 8602 libres. Utilise uniquement des dossiers de
données temporaires (jamais celui de l'utilisateur), sauf avec --default-dir
(machine de CI jetable) qui vérifie l'emplacement %LOCALAPPDATA%.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "Les ports 8600, 8601 et 8602 sont déjà utilisés. Impossible de démarrer "
    "l’application. Veuillez fermer une autre instance de Contrôle Agences si "
    "elle est ouverte, puis réessayer."
)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
EXE = Path(args[0]).resolve() if args else None
COMMAND = [str(EXE)] if EXE else [sys.executable, str(ROOT / "server.py")]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name + (f" — {detail}" if detail and not condition else ""), flush=True)
    if not condition:
        failures.append(name)


def identity(port):
    try:
        with OPENER.open(f"http://127.0.0.1:{port}/api/identity", timeout=1) as r:
            return json.load(r)
    except Exception:
        return None


def status(port, path, method="GET", headers=None, body=None):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method=method, headers=headers or {})
    try:
        with OPENER.open(request, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def quit_app(port):
    status(port, "/api/quit", "POST", {"Content-Type": "application/json"}, b"{}")


def blocker(port, banner=None):
    s = socket.socket()
    if sys.platform == "win32":
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen()
    if banner:
        def serve():
            while True:
                try:
                    c, _ = s.accept()
                except OSError:
                    return
                try:
                    c.sendall(banner)
                finally:
                    c.close()
        threading.Thread(target=serve, daemon=True).start()
    return s


def wait_until(predicate, timeout=40):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    return None


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    data = tmp / "Données Sérdar"
    browser_log = tmp / "browser.log"
    browser_script = tmp / "browser.py"
    browser_script.write_text(
        "import json, sys, urllib.request\n"
        "url = sys.argv[1]\n"
        "try:\n"
        "    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))\n"
        "    state = json.load(op.open(url + '/api/identity', timeout=2))['app_id']\n"
        "except Exception as exc:\n"
        "    state = 'NOT-READY'\n"
        f"open({str(browser_log)!r}, 'a', encoding='utf-8').write(url + ' ' + state + '\\n')\n",
        encoding="utf-8",
    )
    py = Path(sys.executable).as_posix()
    env = dict(
        os.environ,
        CONTROLE_AGENCES_DATA_DIR=str(data),
        CONTROLE_AGENCES_NO_DIALOG="1",
        BROWSER=f'"{py}" "{browser_script.as_posix()}" %s',
        PYTHONIOENCODING="utf-8",
    )

    def launch(*extra, environ=None):
        return subprocess.Popen(COMMAND + list(extra), cwd=ROOT, env=environ or env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding="utf-8", errors="replace")

    def browser_lines():
        return browser_log.read_text(encoding="utf-8").splitlines() if browser_log.exists() else []

    def log_text(folder=data):
        path = folder / "logs" / "app.log"
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def finish(process, timeout=30):
        try:
            process.wait(timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return process.returncode

    blockers = []
    try:
        # 1. Ports libres : 8600, navigateur ouvert une fois l'application prête.
        first = launch()
        line = wait_until(lambda: (browser_lines() or [None])[0])
        check("ports libres : navigateur ouvert sur 8600 après démarrage",
              line == "http://127.0.0.1:8600 fr.controle-agences.desktop", line)
        check("interface React servie", status(8600, "/") == 200)
        info = json.loads((data / "instance.json").read_text(encoding="utf-8"))
        check("instance.json cohérent", info.get("instance") == (identity(8600) or {}).get("instance"))

        # 2. Second lancement : réutilise l'instance, pas de second serveur.
        second = launch()
        check("second lancement : code 0", finish(second) == 0)
        line = wait_until(lambda: browser_lines()[1] if len(browser_lines()) > 1 else None)
        check("second lancement : navigateur rouvert sur 8600",
              line == "http://127.0.0.1:8600 fr.controle-agences.desktop", line)
        check("second lancement : aucun autre serveur", identity(8601) is None)

        # 3. Protection locale.
        check("en-tête Host étranger refusé", status(8600, "/api/history", headers={"Host": "evil.example:8600"}) == 403)
        check("POST d'une autre origine refusé",
              status(8600, "/api/quit", "POST", {"Content-Type": "application/json", "Origin": "http://evil.example"}, b"{}") == 403)
        check("POST multipart d'une autre origine refusé",
              status(8600, "/api/report", "POST", {"Content-Type": "multipart/form-data; boundary=x", "Origin": "http://evil.example"}, b"--x--\r\n") == 403)
        check("instance toujours active", identity(8600) is not None)

        # 4. Quitter.
        quit_app(8600)
        check("Quitter : le processus s'arrête (code 0)", finish(first) == 0)

        # 5. Relance immédiate : de nouveau sur 8600.
        again = launch("--no-browser")
        check("relance immédiate après Quitter : 8600", wait_until(lambda: identity(8600)) is not None)
        quit_app(8600)
        finish(again)

        # 6. Service étranger (non HTTP) sur 8600, port occupé sur 8601 : 8602.
        blockers += [blocker(8600, b"SSH-2.0-OpenSSH_9.6\r\n"), blocker(8601)]
        n = len(browser_lines())
        third = launch()
        line = wait_until(lambda: browser_lines()[n] if len(browser_lines()) > n else None)
        check("8600 (service étranger) et 8601 occupés : navigateur sur 8602",
              line == "http://127.0.0.1:8602 fr.controle-agences.desktop", line)
        quit_app(8602)
        finish(third)

        # 7. Trois ports occupés : message exact, code 1, pas de navigateur.
        blockers.append(blocker(8602))
        n = len(browser_lines())
        fourth = launch()
        code = finish(fourth)
        stderr = fourth.stderr.read()
        check("trois ports occupés : code 1", code == 1, f"code {code}")
        check("trois ports occupés : message exact (journal)", REQUIRED in log_text())
        if not EXE or "--console" in sys.argv:
            last = (stderr.strip().splitlines() or [""])[-1]
            check("trois ports occupés : message exact (sortie d'erreur)", last == REQUIRED, last)
        check("trois ports occupés : navigateur non ouvert", len(browser_lines()) == n)
    finally:
        for s in blockers:
            s.close()
        blockers.clear()

    # 8. Lancements simultanés (double-clic répété) : une seule instance.
    time.sleep(1)
    bad = 0
    for _ in range(5):
        processes = [launch("--no-browser") for _ in range(2)]
        wait_until(lambda: identity(8600) or identity(8601))
        time.sleep(4)
        running = [p for p in (8600, 8601, 8602) if identity(p)]
        for port in running:
            quit_app(port)
        codes = [finish(p) for p in processes]
        bad += len(running) != 1 or codes != [0, 0]
        time.sleep(1)
    check("lancements simultanés x5 : une seule instance", bad == 0, f"{bad} essai(s) en échec")

    # 9. Base de données illisible : démarrage refusé, fichier intact.
    corrupt = tmp / "corrompu"
    (corrupt / "data").mkdir(parents=True)
    junk = b"pas une base SQLite " * 50
    (corrupt / "data" / "controles.db").write_bytes(junk)
    p = launch("--no-browser", environ=dict(env, CONTROLE_AGENCES_DATA_DIR=str(corrupt)))
    code = finish(p)
    check("base illisible : démarrage refusé avec message",
          code == 1 and "base de données" in log_text(corrupt), f"code {code}")
    check("base illisible : fichier non modifié", (corrupt / "data" / "controles.db").read_bytes() == junk)

    # 10. Exécutable sans dossier imposé : %LOCALAPPDATA%\ControleAgences (CI uniquement).
    if EXE and "--default-dir" in sys.argv:
        environ = {k: v for k, v in env.items() if k != "CONTROLE_AGENCES_DATA_DIR"}
        default = Path(os.environ["LOCALAPPDATA"]) / "ControleAgences"
        p = launch("--no-browser", environ=environ)
        # instance.json est écrit juste après la vérification de disponibilité.
        up = wait_until(lambda: identity(8600) and (default / "instance.json").is_file())
        check("exécutable : données dans %LOCALAPPDATA%\\ControleAgences",
              up and (default / "data" / "controles.db").is_file() and (default / "instance.json").is_file())
        check("exécutable : rien d'écrit à côté de l'exécutable",
              not (EXE.parent / "data").exists() and not (EXE.parent / "reports").exists())
        if up:
            quit_app(8600)
        finish(p)

print()
if failures:
    print(f"ÉCHEC : {len(failures)} vérification(s) : {failures}")
    sys.exit(1)
print("Toutes les vérifications de démarrage sont passées.")
