# ─────────────────────────────────────────────────────────────────────────────
# File: core/paths.py
# ─────────────────────────────────────────────────────────────────────────────
import os, sys


def resource_path(relative_path: str) -> str:
    """Resuelve rutas compatible con PyInstaller."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
