# sdk/loader.py
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from .comercial import ComercialSDK, DLL_NAME

def _app_dir() -> Path:
    import sys
    return Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent

APP_DIR = _app_dir()

# Rutas típicas
CANDIDATE_DLL_DIRS = [
    str(APP_DIR),
    str(APP_DIR / "compac_sdk"),
    r"C:\Program Files (x86)\Compac\COMERCIAL",
    r"C:\Compac\COMERCIAL",
    r"C:\Compac\Comercial",
]
CANDIDATE_CAC_DIRS = [
    str(APP_DIR),
    str(APP_DIR / "compac_sdk"),
    r"C:\ProgramData\Compac\CAC",
    r"C:\Windows",
    r"C:\Program Files (x86)\Compac\COMERCIAL",
    r"C:\Compac\COMERCIAL",
    r"C:\Compac\Comercial",
]
CANDIDATE_PAQ_NAMES = [
    b"CONTPAQ I COMERCIAL",
    b"CONTPAQ I Comercial",
    b"CONTPAQ i Comercial",
]

def _has_dll(d: str) -> bool:
    try:
        return (Path(d) / DLL_NAME).is_file()
    except Exception:
        return False

# ---------- NUEVO: búsqueda global de CAC.ini ----------
def _list_fixed_roots():
    roots = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        p = Path(f"{letter}:\\")
        if p.exists():
            roots.append(p)
    return roots

def _find_cac_ini_global(max_hits: int = 3):
    """
    Busca CAC.ini de forma global:
    1) en rutas típicas/rápidas
    2) si no aparece, recorre TODOS los discos (C:\, D:\, ...) con poda:
       - Solo nombres exactos 'CAC.ini' (case-insensitive)
       - Evita carpetas muy ruidosas donde no suele estar (Windows\WinSxS, $Recycle.Bin, etc.)
    Devuelve lista de rutas encontradas (orden de hallazgo).
    """
    # primero, típicas
    hits = []
    for base in CANDIDATE_CAC_DIRS:
        p = Path(base) / "CAC.ini"
        if p.is_file():
            hits.append(str(p))
            if len(hits) >= max_hits:
                return hits

    # segundo, variable de entorno si contiene una carpeta (para completarla)
    env = os.environ.get("COMPAC_CAC_INI")
    if env and Path(env).is_file():
        hits.append(env)
        if len(hits) >= max_hits:
            return hits

    # tercero, rastreo global por discos
    SKIP_DIR_NAMES = {
        "Windows", "WinSxS", "Installer", "Temp", "ProgramData\\Package Cache",
        "$Recycle.Bin", "AppData", "Program Files", "Program Files (x86)", "node_modules",
        "System Volume Information"
    }
    roots = _list_fixed_roots()
    for root in roots:
        # rutas probables dentro de cada disco
        quick = [
            root / "Compac",
            root / "ProgramData" / "Compac",
            root / "Program Files (x86)" / "Compac",
            root / "Program Files" / "Compac",
            root / "Windows",
        ]
        for q in quick:
            p = q / "CAC.ini"
            if p.is_file():
                hits.append(str(p))
                if len(hits) >= max_hits:
                    return hits

        # caminata podada
        try:
            for base, dirs, files in os.walk(root, topdown=True):
                # poda de directorios ruidosos
                dirs[:] = [d for d in dirs if all(skip not in os.path.join(base, d) for skip in SKIP_DIR_NAMES)]
                if "CAC.ini" in files:
                    hits.append(os.path.join(base, "CAC.ini"))
                    if len(hits) >= max_hits:
                        return hits
        except Exception:
            # algunos volúmenes protegidos pueden fallar: ignorar
            pass

    return hits

def _choose_cac_ini() -> str | None:
    # 1) variable de entorno explícita
    env = os.environ.get("COMPAC_CAC_INI")
    if env and Path(env).is_file():
        return env
    # 2) típicas + global
    hits = _find_cac_ini_global(max_hits=1)
    return hits[0] if hits else None

def get_sdk() -> ComercialSDK:
    # Localizar CAC.ini de forma automática (global si es necesario)
    cac = _choose_cac_ini()
    if cac:
        try:
            os.chdir(Path(cac).parent)  # SDK espera CWD donde vive CAC.ini
        except Exception:
            pass

    # localizar DLL del SDK
    dll_dirs = []
    env_dll = os.environ.get("COMPAC_SDK_DIR")
    if env_dll:
        dll_dirs.append(env_dll)
    dll_dirs += CANDIDATE_DLL_DIRS
    dll_dirs = [d for d in dll_dirs if d and _has_dll(d)]

    last_err = None
    for d in dll_dirs:
        for paq in CANDIDATE_PAQ_NAMES:
            try:
                sdk = ComercialSDK(d, paq)
                sdk.load()
                return sdk
            except Exception as e:
                last_err = f"{d} / {paq!r}: {e}"

    raise RuntimeError(
        "No se pudo cargar MGWSERVICIOS.DLL.\n"
        "Verifica EXE/Python 32-bit, VC++ x86, CAC.ini y rutas del SDK.\n"
        f"Último intento: {last_err or 'sin detalles'}\n"
        f"CAC.ini usado: {cac or 'no encontrado'}"
    )
