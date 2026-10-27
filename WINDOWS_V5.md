# Contrôle Agences 5.0.0 — Windows
Branch: v5-windows, based on v4-react. React and Python keep the V4 architecture.
Target: fresh Windows installation (no previous version to migrate).

## Build
Windows x64, Python 3.12 x64, Node 22.12+ and npm. From this checkout:

    powershell -ExecutionPolicy Bypass -File packaging/build.ps1             # dist\ControleAgences\  (folder, console)
    powershell -ExecutionPolicy Bypass -File packaging/build.ps1 -Release    # dist\ControleAgences.exe (single file, windowed)

The script stops at the first error. It recreates `.venv-package` from scratch,
installs `packaging/requirements.txt` (pinned), rebuilds React with `npm ci`,
checks that every file referenced by `frontend/dist/index.html` exists, runs the
unit tests with the exact packaged versions, then runs PyInstaller
(entry point `launcher.py`, Windows version resource from `version.py`, no UPX).
`dist\build-info-*.txt` records the SHA256, Git commit, Python/Node versions and
`pip freeze`: keep it with each delivered executable. End users need neither
Python nor Node.

The GitHub Actions workflow `.github/workflows/windows-build.yml` runs all of
this on `windows-latest` at each push to `v5-windows` and tests the actual
executables (see Validation). The release executable is attached to the run as
the `ControleAgences-windows` artifact.

## Data and updates
- Executable: data in `%LOCALAPPDATA%\ControleAgences` (`data\controles.db`,
  `reports\`, `uploads\`, `logs\app.log`, `config.json`, `instance.*`).
  Program files (including `frontend/dist`) live inside the executable, so
  replacing the executable never touches the data.
- Update: click « Quitter l’application », replace the executable, relaunch.
  Never delete the data folder. Back it up (application closed) by copying it.
- File paths are stored relative to the data folder, so a restored backup works
  on another PC or under another Windows user name.
- PDFs are named `rapport_final_controle_n1_<agence>_<date>_<HHhMM>_<contrôleur>.pdf`;
  an existing file is never overwritten (`_1`, `_2`… suffix). Files are written
  to a temporary file, synced, then renamed: an interruption never leaves a
  truncated PDF.
- Excel workbooks remain user-managed files, opened/saved from the browser as in V4.
- Development (`python server.py`, RUN_APP.bat) keeps data in the repository
  folder. `CONTROLE_AGENCES_DATA_DIR` selects another absolute folder (tests).

## Lifecycle
- Only 127.0.0.1 is bound; ports 8600, 8601, 8602 are tried in order. On Windows
  the socket is bound with `SO_EXCLUSIVEADDRUSE` before waitress uses it, so a
  port held by any other program is never shared.
- One instance per data folder: an OS lock (`instance.lock`, released even if the
  process is killed). A second launch reads `instance.json` and reopens the
  browser on the running instance after checking its random instance id; it
  never reuses another program or another Windows user's instance. If another
  version is running for the same data, a French dialog asks to quit it first.
- The browser is opened at the selected port only after the server answers. If it
  cannot be opened, a dialog gives the address.
- All three ports unavailable:
  « Les ports 8600, 8601 et 8602 sont déjà utilisés. Impossible de démarrer l’application. Veuillez fermer une autre instance de Contrôle Agences si elle est ouverte, puis réessayer. »
- Every startup error (including during imports, data-folder creation or an
  unreadable database) is logged and shown in a Windows dialog, also in the
  windowed build. An unreadable database stops the start and is left untouched.
- « Quitter l’application » refuses new writes, waits for running requests
  (e.g. a PDF being generated) to finish, then stops the process.

## Local security
- Requests whose `Host` is not `127.0.0.1:<port>`/`localhost:<port>` are refused
  (DNS rebinding). Write requests from another origin (`Origin`, `Sec-Fetch-Site`)
  are refused (a web page can no longer create reports or quit the app).
- Not addressed: there is no per-user authentication of the local API. Any
  program running on the PC, or another user of a shared PC (Remote Desktop/
  Citrix), who opens the URL can use the application. Acceptable for a
  single-user workstation; a session cookie would be required for shared servers.

## Previous versions (not required)
`migrate_data.py` (V4 → V5) is kept but is not part of the fresh installation.
Known defects, unresolved: on Windows the staged database connection is still
open when the staging folder is renamed (migration expected to fail), any missing
legacy file or a moved/backup source aborts the whole migration, and the tool
needs Python. Its test is skipped on Windows.

## Validation
Linux/source: `python -m unittest discover -s tests -v`,
`python tests/check_startup.py`, `python tests/smoke_journey.py create|verify source <dir> <state.json>`.
Windows (CI, `windows-build.yml`), on the built executables:
- folder/console build: startup lifecycle (ports, reuse, exhaustion message,
  races, Host/Origin checks, unreadable database, `%LOCALAPPDATA%` location),
  then the user journey (control with PDF and image attachments, PDF, Excel
  create/update/delete/reopen, quit during a save);
- single-file/windowed build of the next version: replaces the previous
  executable and must find all saved reports, attachments and configuration;
  previous version still open → clear refusal; startup lifecycle again.

Still manual on a real Windows PC (not possible in CI):
- visual check of the Windows dialogs (ports occupied, other version, errors);
- default browser really opening at 8600/8601/8602, with the Excel « Reprendre » button;
- non-ASCII Windows user name; corporate antivirus/SmartScreen and code signing;
- printing/opening generated PDFs and Excel files in the usual applications.
