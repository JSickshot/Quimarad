# sdk_probe_subproc.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, sys, json, argparse

def _candidate_sdk_dirs() -> list[str]:
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pf64 = os.environ.get("ProgramFiles",       r"C:\Program Files")
    drives = [f"{d}:" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"]

    patterns = [
        r"{drv}\Archivos de programa (x86)\Compac\COMERCIAL",
        r"{drv}\Program Files (x86)\Compac\COMERCIAL",
        r"{drv}\Program Files\Compac\COMERCIAL",
        r"{drv}\Compac\COMERCIAL",
    ]

    out = [os.path.join(pf86, r"Compac\COMERCIAL"),
           os.path.join(pf64, r"Compac\COMERCIAL")]

    for d in drives:
        for pat in patterns:
            out.append(pat.format(drv=d))
    seen=set(); out2=[]
    for p in out:
        p=os.path.normpath(p)
        if p not in seen:
            out2.append(p); seen.add(p)
    return out2

def autodetect() -> dict:
    # 1) config previa si existe
    cfg_dir = os.path.join(os.getenv("APPDATA") or os.getcwd(), "QCG")
    cfg_file= os.path.join(cfg_dir, "carga_comercial.json")
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        sd = cfg.get("sdk_dir")
        if sd and os.path.isfile(os.path.join(sd, "MGWSERVICIOS.DLL")):
            return {"ok": True, "sdk_dir": sd, "from": "config"}
    except Exception:
        pass

    # 2) candidatos rápidos
    for base in _candidate_sdk_dirs():
        dll = os.path.join(base, "MGWSERVICIOS.DLL")
        if os.path.isfile(dll):
            return {"ok": True, "sdk_dir": base, "from": "candidates"}

    return {"ok": False, "error": "not-found"}

def handshake(sdk_dir: str) -> dict:
    try:
        from sdk.loader import get_sdk
    except Exception as e:
        return {"ok": False, "error": f"import loader: {e}"}
    try:
        sdk = get_sdk(sdk_dir)
        # Si llegó aquí, la DLL cargó. No mantenemos objetos abiertos.
        _ = getattr(sdk, "sdk_dir", sdk_dir)
        return {"ok": True, "sdk_dir": _}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--autodetect", action="store_true")
    ap.add_argument("--handshake",  action="store_true")
    ap.add_argument("--sdk-dir",    default=None)
    args = ap.parse_args()

    if args.autodetect:
        print(json.dumps(autodetect(), ensure_ascii=False))
        return

    if args.handshake:
        if not args.sdk_dir:
            print(json.dumps({"ok": False, "error": "sdk-dir requerido"}, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps(handshake(args.sdk_dir), ensure_ascii=False))
        return

    print(json.dumps({"ok": False, "error": "sin-comando"}, ensure_ascii=False))
    sys.exit(2)

if __name__ == "__main__":
    main()
