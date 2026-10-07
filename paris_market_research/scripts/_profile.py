"""İndirilen tabloların hızlı profili (temizlik değildir).

Çıktı data/profiles/<source_id>_<dosya>.json: sütunlar, satır sayısı,
boş oranları, ilk 5 kayıt, koordinat sütunu adayları ve basit Paris
filtresi sayımları. Ham dosyaya dokunulmaz.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from _common import ROOT, utc_now

PROFILE_DIR = ROOT / "data" / "profiles"

# Paris (75056) ve 20 arrondissement kodu 75101–75120; posta kodları 75001–75020 + 75116.
PARIS_ARR_INSEE = {f"751{i:02d}" for i in range(1, 21)}
PARIS_POSTCODES = {f"750{i:02d}" for i in range(1, 21)} | {"75116"}

# Paris'i makul olarak kapsayan WGS84 kutusu (kaba makullük kontrolü, filtre değil)
PARIS_BBOX = (2.22, 48.81, 2.47, 48.91)  # lon_min, lat_min, lon_max, lat_max


def read_table(path: Path, member: str | None = None, **kw) -> pd.DataFrame:
    """CSV / XLSX / ZIP içindeki CSV dosyasını metin olarak (dtype=str) okur."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            name = member or next(n for n in z.namelist() if n.lower().endswith((".csv", ".xlsx")))
            data = z.read(name)
        if name.lower().endswith(".xlsx"):
            return pd.read_excel(io.BytesIO(data), dtype=str, **kw)
        return _read_csv_bytes(data, **kw)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str, **kw)
    return _read_csv_bytes(path.read_bytes(), **kw)


def _read_csv_bytes(data: bytes, **kw) -> pd.DataFrame:
    head = data[:5000].decode("utf-8-sig", errors="replace").splitlines()[0]
    sep = max([";", ",", "\t"], key=head.count)
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(data), sep=sep, dtype=str, encoding=enc,
                               low_memory=False, **kw)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV kodlaması çözülemedi")


def coordinate_candidates(df: pd.DataFrame) -> list[str]:
    keys = ("lat", "lon", "lng", "x", "y", "coord", "geo", "geom", "wgs", "lambert")
    return [c for c in df.columns if any(k == c.lower() or k in c.lower() for k in keys)]


def profile_df(df: pd.DataFrame, source_id: str, name: str, extra: dict | None = None) -> Path:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    prof = {
        "source_id": source_id,
        "table": name,
        "profiled_at_utc": utc_now(),
        "rows": int(len(df)),
        "columns": list(map(str, df.columns)),
        "null_share": {str(c): round(float(df[c].isna().mean()), 4) for c in df.columns},
        "coordinate_column_candidates": coordinate_candidates(df),
        "head": df.head(5).fillna("").astype(str).to_dict(orient="records"),
    }
    if extra:
        prof.update(extra)
    out = PROFILE_DIR / f"{source_id}__{Path(name).stem}.json"
    out.write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def in_paris_bbox(lon: float, lat: float) -> bool:
    return PARIS_BBOX[0] <= lon <= PARIS_BBOX[2] and PARIS_BBOX[1] <= lat <= PARIS_BBOX[3]
