# ui/launcher.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, sys, json, subprocess, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from sdk.loader import get_sdk
from features.catalogs import conceptos, clientes, productos, almacenes, agentes, monedas, series

APP_TITLE = "Asistente de conexión — CONTPAQi Comercial"
CFG_DIR   = os.path.join(os.getenv("APPDATA") or os.getcwd(), "QCG")
CFG_FILE  = os.path.join(CFG_DIR, "carga_comercial.json")

def _load_cfg() -> dict:
    try:
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cfg(data: dict) -> None:
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _resource_path(rel: str) -> str:
    """
    Ubica archivos cuando se empaqueta con PyInstaller (sys._MEIPASS) o en dev.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(sys.argv[0])))
    cand = os.path.join(base, rel)
    if os.path.isfile(cand):
        return cand
    # fallback relativo al proyecto
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", rel)).replace("\\", "/")

def _discover_ad_paths() -> list[str]:
    bases = []
    drives = [f"{d}:" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{d}:\\")]
    patterns = [
        r"{drv}\Compac\Empresas",
        r"{drv}\CONTPAQ i\Empresas",
        r"{drv}\Empresas CONTPAQi",
    ]
    for d in drives:
        for pat in patterns:
            base = os.path.normpath(pat.format(drv=d))
            if not os.path.isdir(base):
                continue
            try:
                for name in os.listdir(base):
                    full = os.path.join(base, name)
                    if name.upper().startswith("AD") and os.path.isdir(full):
                        bases.append(full)
            except Exception:
                pass
    seen = set(); out = []
    for p in bases:
        if p not in seen:
            out.append(p); seen.add(p)
    return out

class LauncherApp(tk.Tk):
    """
    Paso 1: detectar SDK y hacer handshake en subproceso (timeout seguro)
    Paso 2: listar y abrir empresa
    Paso 3: lanzar Workbench con sdk ya listo (y empresa abierta)
    """
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x620")

        self.sdk = None
        self.sdk_dir: str|None = None
        self.company_path: str|None = None

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # --- Step 1: SDK ---
        self.step1 = ttk.Frame(nb)
        nb.add(self.step1, text="1) Conectar SDK")

        self.txt1 = tk.Text(self.step1, height=10)
        self.txt1.pack(fill="x", padx=10, pady=10)

        bar1 = ttk.Frame(self.step1); bar1.pack(fill="x", padx=10, pady=(0,10))
        ttk.Button(bar1, text="Detectar (auto)", command=self._detect_sdk_auto).pack(side="left", padx=4)
        ttk.Button(bar1, text="Elegir MGWSERVICIOS.DLL…", command=self._pick_dll).pack(side="left", padx=4)
        ttk.Button(bar1, text="Handshake (probar SDK)", command=self._handshake_sdk).pack(side="left", padx=4)

        self.lbl_sdk = ttk.Label(self.step1, text="SDK: (no seleccionado)")
        self.lbl_sdk.pack(anchor="w", padx=12)

        # --- Step 2: Empresa ---
        self.step2 = ttk.Frame(nb)
        nb.add(self.step2, text="2) Empresa")

        self.txt2 = tk.Text(self.step2, height=8)
        self.txt2.pack(fill="x", padx=10, pady=10)

        bar2 = ttk.Frame(self.step2); bar2.pack(fill="x", padx=10)
        ttk.Button(bar2, text="Listar empresas (C..Z)", command=self._scan_companies).pack(side="left", padx=4)
        ttk.Button(bar2, text="Examinar carpeta AD…", command=self._browse_ad).pack(side="left", padx=4)
        ttk.Button(bar2, text="Abrir empresa", command=self._open_company).pack(side="left", padx=4)

        self.lb_emp = tk.Listbox(self.step2, height=10)
        self.lb_emp.pack(fill="both", expand=True, padx=10, pady=8)

        self.lbl_emp = ttk.Label(self.step2, text="Empresa: (sin abrir)")
        self.lbl_emp.pack(anchor="w", padx=12, pady=(0,10))

        # --- Step 3: Workbench ---
        self.step3 = ttk.Frame(nb)
        nb.add(self.step3, text="3) Workbench")

        self.txt3 = tk.Text(self.step3, height=8)
        self.txt3.pack(fill="x", padx=10, pady=10)

        ttk.Button(self.step3, text="Abrir Workbench", command=self._launch_workbench).pack(pady=10)

        # intento: cargar ruta persistida para SDK
        cfg = _load_cfg()
        if cfg.get("sdk_dir") and os.path.isfile(os.path.join(cfg["sdk_dir"], "MGWSERVICIOS.DLL")):
            self.sdk_dir = cfg["sdk_dir"]
            self._log1(f"Ruta SDK guardada: {self.sdk_dir}")
            self.lbl_sdk.config(text=f"SDK: {self.sdk_dir}")
        else:
            self._log1("No hay SDK guardado. Usa Detectar (auto) o Elegir DLL…")

    # -------------------- helpers log --------------------
    def _log1(self, s: str): self._writelog(self.txt1, s)
    def _log2(self, s: str): self._writelog(self.txt2, s)
    def _log3(self, s: str): self._writelog(self.txt3, s)
    def _writelog(self, txt: tk.Text, s: str):
        txt.insert("end", f"{datetime.now().strftime('%H:%M:%S')} {s}\n"); txt.see("end")

    # -------------------- Step 1: SDK --------------------
    def _detect_sdk_auto(self):
        script = _resource_path("sdk_probe_subproc.py")
        try:
            res = subprocess.run(
                [sys.executable, script, "--autodetect"],
                capture_output=True, text=True, timeout=40
            )
            out = res.stdout.strip()
            if res.returncode != 0 or not out:
                self._log1(f"[Auto] error: rc={res.returncode} {res.stderr.strip()}")
                return
            data = json.loads(out)
            if data.get("ok") and data.get("sdk_dir"):
                self.sdk_dir = data["sdk_dir"]
                self.lbl_sdk.config(text=f"SDK: {self.sdk_dir}")
                self._log1(f"[Auto] SDK en {self.sdk_dir}")
                cfg = _load_cfg(); cfg["sdk_dir"] = self.sdk_dir; _save_cfg(cfg)
            else:
                self._log1(f"[Auto] no encontrado: {data}")
        except subprocess.TimeoutExpired:
            self._log1("[Auto] timeout buscando SDK (40s)")
        except Exception as e:
            self._log1(f"[Auto] excepción: {e}")

    def _pick_dll(self):
        path = filedialog.askopenfilename(
            title="Selecciona MGWSERVICIOS.DLL",
            filetypes=[("MGWSERVICIOS.DLL","MGWSERVICIOS.DLL"),("DLL","*.DLL")]
        )
        if not path:
            return
        self.sdk_dir = os.path.dirname(path)
        self.lbl_sdk.config(text=f"SDK: {self.sdk_dir}")
        self._log1(f"[Manual] Seleccionado: {self.sdk_dir}")
        cfg = _load_cfg(); cfg["sdk_dir"] = self.sdk_dir; _save_cfg(cfg)

    def _handshake_sdk(self):
        if not self.sdk_dir:
            messagebox.showwarning("SDK", "Selecciona o detecta la ruta del SDK primero.")
            return
        script = _resource_path("sdk_probe_subproc.py")
        try:
            res = subprocess.run(
                [sys.executable, script, "--handshake", "--sdk-dir", self.sdk_dir],
                capture_output=True, text=True, timeout=90
            )
            out = res.stdout.strip()
            if res.returncode != 0 or not out:
                self._log1(f"[Handshake] rc={res.returncode} {res.stderr.strip()}")
                messagebox.showerror("SDK", "Fallo handshake. Revisa CAC000/licencias.")
                return
            data = json.loads(out)
            if not data.get("ok"):
                self._log1(f"[Handshake] respuesta: {data}")
                messagebox.showerror("SDK", "El SDK no se pudo inicializar.")
                return

            # Si handshake ok, ahora cargamos el SDK REAL en este proceso
            try:
                self.sdk = get_sdk(self.sdk_dir)
                self._log1("[Handshake] SDK OK en proceso principal.")
            except Exception as e:
                self._log1(f"[Handshake] get_sdk en principal: {e}")
                messagebox.showerror("SDK", str(e))
                return

        except subprocess.TimeoutExpired:
            self._log1("[Handshake] timeout (90s). Si salió CAC000, acéptalo y reintenta.")
        except Exception as e:
            self._log1(f"[Handshake] excepción: {e}")

    # -------------------- Step 2: Empresa --------------------
    def _scan_companies(self):
        emps = _discover_ad_paths()
        self.lb_emp.delete(0, "end")
        for e in emps:
            self.lb_emp.insert("end", e)
        self._log2(f"Encontradas {len(emps)} empresas AD*")

    def _browse_ad(self):
        path = filedialog.askdirectory(title="Selecciona carpeta AD*")
        if not path:
            return
        if os.path.basename(path).upper().startswith("AD"):
            self.lb_emp.insert("end", os.path.normpath(path))
            self._log2(f"Agregada: {path}")
        else:
            messagebox.showwarning("AD", "Selecciona una carpeta AD* válida.")

    def _open_company(self):
        if not self.sdk:
            messagebox.showwarning("Empresa", "Primero realiza el handshake del SDK.")
            return
        try:
            sel = self.lb_emp.get(self.lb_emp.curselection())
        except Exception:
            sel = None
        if not sel:
            messagebox.showwarning("Empresa", "Selecciona una AD* de la lista.")
            return

        # cerrar previa
        try:
            self.sdk.dll.close_company()
        except Exception:
            pass

        rc = self.sdk.dll.open_company(sel)
        if rc != 0:
            self._log2(f"[Empresa] rc={rc} {self.sdk.dll.error_text(rc)}")
            messagebox.showerror("Empresa", f"rc={rc}\n{self.sdk.dll.error_text(rc)}")
            return

        self.company_path = sel
        self.lbl_emp.config(text=f"Empresa: {sel}")
        self._log2(f"[Empresa] Abierta: {sel}")

        # prueba ligera de catálogos para constatar que no cuelga
        try:
            _ = conceptos(self.sdk)
            _ = monedas(self.sdk)
            self._log2("[Empresa] Catálogos básicos OK.")
        except Exception as e:
            self._log2(f"[Empresa] catálogos: {e}")

    # -------------------- Step 3: Workbench --------------------
    def _launch_workbench(self):
        if not self.sdk:
            messagebox.showwarning("Workbench", "Primero realiza el handshake del SDK.")
            return
        if not self.company_path:
            messagebox.showwarning("Workbench", "Abre una empresa antes de continuar.")
            return
        # Lanza el Workbench en una nueva ventana y oculta el asistente
        try:
            from ui.workbench import WorkbenchApp
        except Exception:
            messagebox.showerror("UI", "No se pudo importar WorkbenchApp.")
            return
        self.withdraw()
        win = WorkbenchApp(sdk=self.sdk)  # <-- inyectamos el SDK listo
        win.protocol("WM_DELETE_WINDOW", self._close_all)
        self._log3("Workbench lanzado.")

    def _close_all(self):
        try:
            self.destroy()
        except Exception:
            os._exit(0)
