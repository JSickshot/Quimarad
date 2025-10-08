# core/files.py
import os, shutil
from typing import Iterable

ALLOWED_EXT = {".mdf", ".ldf"}
BLOCKLIST = {  # nunca copiar DBs de sistema
    "master.mdf", "mastlog.ldf",
    "model.mdf", "modellog.ldf",
    "msdbdata.mdf", "msdblog.ldf",
    "tempdb.mdf", "templog.ldf",
}

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def iter_db_files(src_dir: str) -> Iterable[str]:
    for name in os.listdir(src_dir):
        lower = name.lower()
        if lower in (b.lower() for b in BLOCKLIST):
            continue
        _, ext = os.path.splitext(name)
        if ext.lower() in ALLOWED_EXT:
            yield os.path.join(src_dir, name)

def copy_data_tree(src_dir: str, dst_dir: str, *, skip_existing: bool = True) -> list[tuple[str, str]]:
    """
    Copia .mdf/.ldf del origen al destino (excluye DB de sistema).
    Si skip_existing=True no sobrescribe. Retorna lista de (src, dst).
    """
    ensure_dir(dst_dir)
    copied: list[tuple[str, str]] = []
    for src in iter_db_files(src_dir):
        dst = os.path.join(dst_dir, os.path.basename(src))
        if skip_existing and os.path.exists(dst):
            continue
        shutil.copy2(src, dst)
        copied.append((src, dst))
    return copied
