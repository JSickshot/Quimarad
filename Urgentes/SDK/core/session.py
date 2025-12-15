# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, string, threading
import tkinter as tk
from tkinter import ttk, messagebox

from sdk.loader import get_sdk, SDKNotFound, SDKArchMismatch, SDKError

CFG_DIR   = os.path.join(os.getenv("APPDATA") or os.getcwd(), "QCG")
CFG_FILE  = os.path.join(CFG_DIR, "carga_comercial.json")

def _load_cfg() -> dict:
    try:
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cfg(d: dict) -> None:
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

class SdkSession:
    """
    1) Ubica / carga el SDK (MGWSERVICIOS.DLL) automáticamente.
    2) Escanea C:..Z: en busca de carpetas AD* (empresas).
    3) Presenta una selección simple de empresa y la abre.
    Retorna (sdk, empresa_path)
    """
    def __init__(self):
        self.sdk = None
        self.empresa_path = None
        self.cfg = _load_cfg()

    # -------------------- Público --------------------
    def run_wizard(self):
        # 1) SDK
        self._obtener_sdk()

        # 2) Empresa (lista AD* encontrada)
        if not self._elegir_empresa():
            return None, None

        # 3) Abrir empresa
        rc = self.sdk.dll.open_company(self.empresa_path)
        if rc != 0:
            messagebox.showerror("Empresa", f"rc={rc}\n{self._err(rc)}")
            return None, None

        # Persistir
        self.cfg["sdk_dir"] = self.sdk.sdk_dir
        self.cfg["ultima_empresa"] = self.empresa_path
        _save_cfg(self.cfg)

        return self.sdk, self.empresa_path

    # -------------------- Interno --------------------
    def _obtener_sdk(self):
        # Intenta usar el cache primero
        sdk_dir_cached = self.cfg.get("sdk_dir")
        if sdk_dir_cached:
            try:
                self.sdk = get_sdk(sdk_dir_cached)
                return
            except (SDKNotFound, SDKArchMismatch, SDKError):
                self.sdk = None

        # Escaneo rápido por ubicaciones típicas
        candidates = []
        for base in [
            r"C:\Archivos de programa (x86)\Compac\COMERCIAL",
            r"C:\Program Files (x86)\Compac\COMERCIAL",
            r"D:\Archivos de programa (x86)\Compac\COMERCIAL",
            r"D:\Program Files (x86)\Compac\COMERCIAL",
        ]:
            dll = os.path.join(base, "MGWSERVICIOS.DLL")
            if os.path.isfile(dll):
                candidates.append(base)

        # Si no se halló, busca en todas las unidades C..Z
        if not candidates:
            for drv in string.ascii_uppercase:
                root = f"{drv}:\\"
                if not os.path.isdir(root):
                    continue
                for rel in [
                    r"Archivos de programa (x86)\Compac\COMERCIAL",
                    r"Program Files (x86)\Compac\COMERCIAL",
                    r"Compac\COMERCIAL",
                ]:
                    base = os.path.join(root, rel)
                    dll = os.path.join(base, "MGWSERVICIOS.DLL")
                    if os.path.isfile(dll):
                        candidates.append(base)

        if not candidates:
            # Pide ruta manual
            self._dialogo_sdk_manual()
            return

        # Usa el primero que funcione
        for base in candidates:
            try:
                self.sdk = get_sdk(base)
                return
            except (SDKNotFound, SDKArchMismatch, SDKError):
                continue

        # Último recurso: diálogo manual
        self._dialogo_sdk_manual()

    def _dialogo_sdk_manual(self):
        root = tk.Tk(); root.withdraw()
        messagebox.showwarning(
            "SDK",
            "SDK no localizado automáticamente. Selecciona MGWSERVICIOS.DLL en el cuadro siguiente."
        )
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Selecciona MGWSERVICIOS.DLL",
            filetypes=[("MGWSERVICIOS.DLL","MGWSERVICIOS.DLL"),("DLL","*.DLL")]
        )
        root.destroy()
        if not path:
            return
        try:
            self.sdk = get_sdk(os.path.dirname(path))
        except Exception as e:
            tk.Tk().withdraw()
            messagebox.showerror("SDK", str(e))
            self.sdk = None

    def _elegir_empresa(self) -> bool:
        if not self.sdk:
            return False

        # Construye lista AD* (C..Z)
        ad_paths = self._scan_empresas_ad()

        if not ad_paths:
            tk.Tk().withdraw()
            messagebox.showinfo("Empresas", "No se encontraron carpetas AD* en C..Z")
            return False

        # Si hay cache de última empresa y existe, úsala directo
        last = self.cfg.get("ultima_empresa")
        if last and last in ad_paths:
            self.empresa_path = last
            return True

        # Diálogo de selección
        self.empresa_path = self._dialogo_empresas(ad_paths)
        return bool(self.empresa_path)

    def _scan_empresas_ad(self) -> list[str]:
        ad_paths = []
        seen = set()
        for drv in string.ascii_uppercase:
            root = f"{drv}:\\"
            if not os.path.isdir(root):
                continue
            for rel in [r"Compac\Empresas", r"CONTPAQ i\Empresas", r"Empresas CONTPAQi"]:
                base = os.path.join(root, rel)
                if not os.path.isdir(base):
                    continue
                try:
                    for name in os.listdir(base):
                        full = os.path.join(base, name)
                        if os.path.isdir(full) and name.upper().startswith("AD"):
                            npath = os.path.normpath(full)
                            if npath not in seen:
                                seen.add(npath)
                                ad_paths.append(npath)
                except Exception:
                    pass
        ad_paths.sort()
        return ad_paths

    def _dialogo_empresas(self, opciones: list[str]) -> str | None:
        sel = {"out": None}
        win = tk.Tk()
        win.title("Selecciona empresa (AD*)")
        win.geometry("780x420")

        ttk.Label(win, text="Empresas encontradas en C..Z (AD*):").pack(anchor="w", padx=10, pady=(10,6))
        lb = tk.Listbox(win, height=16)
        lb.pack(fill="both", expand=True, padx=10, pady=(0,10))
        for p in opciones:
            lb.insert("end", p)

        btns = ttk.Frame(win); btns.pack(fill="x", padx=10, pady=10)
        def _ok(*_):
            try:
                idx = lb.curselection()[0]
                sel["out"] = opciones[idx]
            except Exception:
                sel["out"] = None
            win.destroy()
        def _cancel(*_):
            sel["out"] = None
            win.destroy()

        ttk.Button(btns, text="Aceptar", command=_ok).pack(side="right")
        ttk.Button(btns, text="Cancelar", command=_cancel).pack(side="right", padx=(0,8))
        lb.bind("<Return>", _ok)
        win.bind("<Escape>", _cancel)
        win.mainloop()
        return sel["out"]

    def _err(self, rc: int) -> str:
        try:
            return self.sdk.dll.error_text(rc)
        except Exception:
            return ""
