# Contrôle Agences 5.0.0 — Windows
Branch: v5-windows, based on v4-react. React and Python remain unchanged in architecture.

## Build
Use Windows x64, Python 3.12 x64, Node 22.12+ and npm.
From this checkout run:
 powershell -ExecutionPolicy Bypass -File packaging/build.ps1
Test dist/ControleAgences/ControleAgences.exe with its entire folder.
Then build the single-file release:
 powershell -ExecutionPolicy Bypass -File packaging/build.ps1 -Release
Deliver dist/ControleAgences.exe. Python and Node are not needed by end users.
The script stops on failure, rebuilds React with npm ci and uses pinned Python packaging dependencies. Version is in version.py and /api/identity.
Record the Git commit, Python/Node versions and SHA256 of the delivered executable with each release.
Windows builds cannot be produced or validated by the Linux environment.

## Data and updates
Frozen applications use %LOCALAPPDATA%/ControleAgences for data, reports,
uploads, logs and config.json. Resources, including frontend/dist, live in the
package. Replace the executable to update; never delete the user data folder.
Back up that entire folder while the application is closed.
Development retains repository-local data; CONTROLE_AGENCES_DATA_DIR can select
an isolated absolute directory for testing.

## Existing installations
Before first V5 launch, close V4 and back up its entire folder plus any separately
saved Excel files. Using Python in the build environment:
 .venv-package/Scripts/python.exe migrate_data.py "C:/old-install" "%LOCALAPPDATA%/ControleAgences"
Expand %LOCALAPPDATA% yourself in PowerShell (use $env:LOCALAPPDATA).
Migration copies reports, attachments, config and logs, takes a SQLite backup,
rewrites stored paths, checks referenced files and database integrity, then
renames the staging folder into place. Originals remain intact.
Destination must not exist: if V5 was already used, back it up and arrange a
separate data reconciliation; migration deliberately refuses an automatic merge.
Run migration on the original Windows machine so absolute legacy paths resolve.
Excel workbooks remain user-managed files: retain and reopen them as in V4.

## Lifecycle
Only 127.0.0.1 is bound. Ports 8600, 8601, 8602 are tried in order.
Only an instance answering with the V5 application identifier and matching
version is reused. This is an application discriminator, not authentication
against malicious local software. Browser opening waits for readiness.
All ports unavailable produces the requested French error, including a native
Windows message box for windowed builds. Use Quitter l’application before updates.

## Validation
Linux: python -m unittest discover -s tests -v
Linux/Windows with ports 8600–8602 initially free: python tests/check_startup.py
The latter deliberately occupies ports, tests fallback, reuse, quit and exhaustion.
Windows release checklist (not yet completed):
- Test both folder and single-file builds on Windows without Python.
- Verify native errors, browser opening at each selected port and duplicate launch.
- Create PDF with PDF/image attachments; open/download and inspect pages.
- Create/update/delete/reopen an Excel workbook.
- Quit and reopen; verify history, reports, attachments and configuration.
- Migrate a backed-up V4 installation and verify old report links.
- Replace executable with a rebuilt version and repeat persistence checks.
- Verify corporate antivirus/signing policies and non-ASCII Windows usernames.
