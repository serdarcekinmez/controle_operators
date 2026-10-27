"""Vérifie que l'interface React construite est complète (index.html + fichiers référencés)."""
import re
import sys
from pathlib import Path

dist = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/dist")
index = dist / "index.html"
if not index.is_file():
    sys.exit(f"ERREUR : {index} est absent.")
html = index.read_text(encoding="utf-8")
refs = re.findall(r'(?:src|href)="/([^"]+)"', html)
missing = [ref for ref in refs if not (dist / ref).is_file()]
if not any(ref.endswith(".js") for ref in refs):
    sys.exit("ERREUR : aucun script référencé par index.html.")
if missing:
    sys.exit("ERREUR : fichiers de l'interface manquants : " + ", ".join(missing))
print(f"Interface OK : {len(refs)} fichier(s) référencé(s) dans {dist}")
