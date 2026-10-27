"""Offline, non-destructive migration. Close both applications first."""
import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def migrate(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError("Destination already exists; back it up and use a new destination. No merge performed.")
    database = source / "data" / "controles.db"
    if not database.is_file():
        raise ValueError("Legacy database missing.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="controle-migration-", dir=destination.parent))
    try:
        for name in ("reports", "uploads", "logs"):
            if (source / name).exists():
                shutil.copytree(source / name, stage / name)
        if (source / "config.json").exists():
            shutil.copy2(source / "config.json", stage / "config.json")
        (stage / "data").mkdir()
        with sqlite3.connect(database) as old, sqlite3.connect(stage / "data" / "controles.db") as new:
            old.backup(new)
            for table, column in (("controls", "pdf_path"), ("attachments", "stored_path")):
                for rowid, value in new.execute(f"SELECT id, {column} FROM {table}").fetchall():
                    if not value:
                        continue
                    path = Path(value)
                    if not path.is_absolute():
                        path = source / path
                    relative = path.resolve().relative_to(source)
                    if not (stage / relative).is_file():
                        raise ValueError(f"Missing legacy file: {relative}")
                    new.execute(f"UPDATE {table} SET {column}=? WHERE id=?", (str(destination / relative), rowid))
            assert new.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    migrate(args.source, args.destination)
