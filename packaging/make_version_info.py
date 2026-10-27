"""Écrit la ressource de version Windows (PyInstaller --version-file) depuis version.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from version import VERSION  # noqa: E402

numbers = [int(part) for part in VERSION.split(".")[:3] if part.isdigit()]
numbers = tuple((numbers + [0, 0, 0, 0])[:4])
text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('FileDescription', 'Controle Agences'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'ControleAgences'),
      StringStruct('OriginalFilename', 'ControleAgences.exe'),
      StringStruct('ProductName', 'Controle Agences'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)
"""
target = Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(text, encoding="utf-8")
print(f"Ressource de version {VERSION} -> {target}")
