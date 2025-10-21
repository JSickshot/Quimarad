# ui/app.py
import os
import sys
import threading
import datetime as _dt
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from typing import Optional, Dict, Tuple, Set, List
from PIL import Image, ImageTk

def resource_path(rel_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, rel_path)

from settings import (
    APP_TITLE,
    QCG_LOGO_PATH,
    DEFAULT_SQL_INSTANCE,
    DEFAULT_SQL_USER,
    DEFAULT_SQL_PASSWORD,
    QCG_ICON_PATH,
)
from ui.theme import apply_theme

from core.copy_task import run_copy_task
from core.sql import sql_conn
from core.attach import attach_catalog_by_name
from core.files import copy_data_tree

class ProgressDialog(tk.Toplevel):
    def __init__(self, master, title="Proceso", text="En proceso"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.label = ttk.Label(self, text=text, width=48)
        self.label.pack(padx=16, pady=(16, 8))
        self.pb = ttk.Progressbar(self, orient="horizontal", length=360, mode="determinate")
        self.pb.pack(padx=16, pady=(0, 16))
        self.pb["value"] = 0
        self.update_idletasks()

    def set(self, pct: float, msg: str):
        try:
            self.pb["value"] = max(0, min(100, pct))
            self.label.configure(text=msg)
            self.update_idletasks()
        except tk.TclError:
            pass

    def close(self):
        try:
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass

class App(tk.Tk):
    _CATALOG_NAMES: Set[str] = {
        "DB_Directory","predeterminada","generalessql","GeneralesSQL","GENERALESSQL",
        "CompacwAdmin","repositorioadminpaq","Nomgenerales","nomGenerales"
    }
    _SYSTEM_DB_NAMES: Set[str] = {
        "master","model","msdb","tempdb","MSDBData","mssqlsystemresource","Resource","ReportServer","ReportServerTempDB"
    }

    def __init__(self):
        super().__init__()

        try:
            if hasattr(sys, "_MEIPASS"):
                icon_candidate = resource_path("logo.ico")
                logo_candidate = resource_path("logo.jpg")
            else:
                icon_candidate = QCG_ICON_PATH
                logo_candidate = QCG_LOGO_PATH
            if icon_candidate and os.path.exists(icon_candidate) and icon_candidate.lower().endswith(".ico"):
                self.iconbitmap(icon_candidate)
            else:
                if logo_candidate and os.path.exists(logo_candidate):
                    _ico_img = ImageTk.PhotoImage(Image.open(logo_candidate))
                    self._ico_img_ref = _ico_img
                    self.iconphoto(True, _ico_img)
        except Exception:
            pass

        self.title(APP_TITLE)
        self.geometry("1120x860")
        self.minsize(1040, 800)
        try:
            if os.name == "nt":
                self.state("zoomed")
            else:
                self.attributes("-zoomed", True)
        except tk.TclError:
            self.attributes("-fullscreen", True)

        apply_theme(self, QCG_LOGO_PATH)

        self._build_shell()
        self._build_home()
        self._build_copy_page()
        self._build_attach_page()
        self.show_frame("home")

    def _build_shell(self):
        self.header = ttk.Frame(self)
        self.header.pack(fill="x", padx=16, pady=(12, 8))
        self.header.columnconfigure(0, weight=1)

        self.title_lbl = ttk.Label(self.header, text="Migración CONTPAQi", style="Header.TLabel")
        self.title_lbl.grid(row=0, column=0, sticky="w")

        self._load_logo_grid(self.header)

        self.stack = ttk.Frame(self)
        self.stack.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.frames: dict[str, ttk.Frame] = {}

    def _load_logo_grid(self, parent: ttk.Frame):
        try:
            if hasattr(sys, "_MEIPASS"):
                logo_path = resource_path("logo.jpg")
            else:
                logo_path = QCG_LOGO_PATH

            if logo_path and os.path.exists(logo_path):
                img = Image.open(logo_path)
                img.thumbnail((140, 48))
                self._logo_img = ImageTk.PhotoImage(img)
                lbl = ttk.Label(parent, image=self._logo_img)
            else:
                lbl = ttk.Label(parent, text="QCG")
            lbl.grid(row=0, column=1, sticky="e")
        except Exception:
            ttk.Label(parent, text="QCG").grid(row=0, column=1, sticky="e")

    def show_frame(self, key: str):
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)

    def _build_home(self):
        home = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["home"] = home

        wrapper = ttk.Frame(home)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Button(
            wrapper,
            text="1) Copiar DATA y Empresas",
            style="Accent.TButton",
            command=lambda: self.show_frame("copy"),
        ).pack(fill="x", padx=4, pady=8)

        ttk.Button(
            wrapper,
            text="2) Attach",
            style="Accent.TButton",
            command=lambda: self.show_frame("attach"),
        ).pack(fill="x", padx=4, pady=8)

    def _build_copy_page(self):
        page = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["copy"] = page

        tb = ttk.Frame(page)
        tb.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(tb, text=" Regresar", command=lambda: self.show_frame("home")).pack(side="left")
        ttk.Label(tb, text="Copiar DATA/Empresas", font=("Segoe UI Semibold", 13)).pack(side="left", padx=12)

        instf = ttk.LabelFrame(page, text="Instancia")
        instf.pack(fill="x", padx=16, pady=(12, 10))
        r1 = ttk.Frame(instf); r1.pack(fill="x", pady=(4, 2))
        ttk.Label(r1, text="Instancia:").pack(side="left")
        self.m_instance = tk.StringVar(value=DEFAULT_SQL_INSTANCE)
        ttk.Entry(r1, textvariable=self.m_instance, width=44).pack(side="left", padx=(8, 16))

        srcf = ttk.LabelFrame(page, text="Rutas de ORIGEN")
        srcf.pack(fill="x", padx=16, pady=(0, 10))
        r2 = ttk.Frame(srcf); r2.pack(fill="x", pady=(4, 2))
        ttk.Label(r2, text="DATA ORIGEN (carpeta):").pack(side="left")
        self.m_data_src = tk.StringVar()
        ttk.Entry(r2, textvariable=self.m_data_src, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r2, text="Elegir", command=lambda: self._pick_dir(self.m_data_src)).pack(side="left")

        r3 = ttk.Frame(srcf); r3.pack(fill="x", pady=(2, 2))
        ttk.Label(r3, text="Empresas (origen):").pack(side="left")
        self.m_emp_src = tk.StringVar(value=r"C:\Compac\Empresas")
        ttk.Entry(r3, textvariable=self.m_emp_src, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r3, text="Elegir", command=lambda: self._pick_dir(self.m_emp_src)).pack(side="left")

        dstf = ttk.LabelFrame(page, text="Destino raíz")
        dstf.pack(fill="x", padx=16, pady=(0, 10))
        r4 = ttk.Frame(dstf); r4.pack(fill="x", pady=(4, 2))
        ttk.Label(r4, text="Ubicación de destino:").pack(side="left")
        self.m_root_dst = tk.StringVar(value=self._default_migracion_root())
        ttk.Entry(r4, textvariable=self.m_root_dst, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r4, text="Elegir", command=lambda: self._pick_dir(self.m_root_dst)).pack(side="left")

        actions = ttk.Frame(page); actions.pack(fill="x", padx=16, pady=(6, 8))
        ttk.Button(
            actions,
            text="Iniciar copia",
            style="Accent.TButton",
            command=self._run_copy_flow,
        ).pack(side="left")

        logf = ttk.Frame(page); logf.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        ttk.Label(
            page,
            text="Ejecuta como Administrador - QCG ",
            foreground="#666",
        ).pack(anchor="w", padx=20)

    def _build_attach_page(self):
        page = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["attach"] = page

        tb = ttk.Frame(page); tb.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(tb, text=" Regresar", command=lambda: self.show_frame("home")).pack(side="left")
        ttk.Label(tb, text="Migración (copiar DATA y adjuntar)", font=("Segoe UI Semibold", 13)).pack(side="left", padx=12)

        connf = ttk.LabelFrame(page, text="SQL")
        connf.pack(fill="x", padx=16, pady=(12, 10))
        r1 = ttk.Frame(connf); r1.pack(fill="x", pady=(4, 2))
        ttk.Label(r1, text="Instancia:").pack(side="left")
        self.a_instance = tk.StringVar(value=DEFAULT_SQL_INSTANCE)
        ttk.Entry(r1, textvariable=self.a_instance, width=44).pack(side="left", padx=(8, 16))
        r2 = ttk.Frame(connf); r2.pack(fill="x", pady=(2, 2))
        ttk.Label(r2, text="Usuario:").pack(side="left")
        self.a_user = tk.StringVar(value=DEFAULT_SQL_USER)
        ttk.Entry(r2, textvariable=self.a_user, width=24).pack(side="left", padx=(8, 16))
        ttk.Label(r2, text="Contraseña:").pack(side="left")
        self.a_pwd = tk.StringVar(value=DEFAULT_SQL_PASSWORD)
        ttk.Entry(r2, textvariable=self.a_pwd, width=24, show="•").pack(side="left", padx=(8, 16))
        ttk.Button(connf, text="Probar conexión", command=self._test_conn_attach).pack(pady=(6, 4), anchor="w")

        pathf = ttk.LabelFrame(page, text="DATA")
        pathf.pack(fill="x", padx=16, pady=(0, 10))
        r3 = ttk.Frame(pathf); r3.pack(fill="x", pady=(4, 2))
        ttk.Label(r3, text="DATA ORIGEN (carpeta):").pack(side="left")
        self.a_data_src = tk.StringVar()
        ttk.Entry(r3, textvariable=self.a_data_src, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r3, text="Elegir", command=lambda: self._pick_dir(self.a_data_src)).pack(side="left")

        r4 = ttk.Frame(pathf); r4.pack(fill="x", pady=(2, 4))
        ttk.Label(r4, text="DATA DESTINO (instancia):").pack(side="left")
        self.a_data_dst = tk.StringVar()
        ttk.Entry(r4, textvariable=self.a_data_dst, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r4, text="Elegir", command=lambda: self._pick_dir(self.a_data_dst)).pack(side="left")

        actions = ttk.Frame(page); actions.pack(fill="x", padx=16, pady=(6, 8))
        ttk.Button(
            actions,
            text="Iniciar proceso",
            style="Accent.TButton",
            command=self._run_attach_flow,
        ).pack(side="left")

        logf = ttk.Frame(page); logf.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        ttk.Label(logf, text="Log (Attach)").pack(anchor="w")
        self.a_log = tk.Text(logf, height=18, wrap="word")
        self.a_log.pack(fill="both", expand=True)

    def _pick_dir(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Selecciona carpeta")
        if d:
            var.set(d)

    def _default_migracion_root(self) -> str:
        from pathlib import Path
        return str(Path.home() / "Desktop" / "Migracion")

    def _alog(self, msg: str):
        def _do():
            self.a_log.insert("end", msg + "\n")
            self.a_log.see("end")
        self.after(0, _do)

    def _scan_mdfs(self, root: str) -> Dict[str, Tuple[str, Optional[str]]]:
        out: Dict[str, Tuple[str, Optional[str]]] = {}
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.lower().endswith(".mdf"):
                    continue
                name = os.path.splitext(fn)[0]
                mdf = os.path.normpath(os.path.join(dirpath, fn))
                candidates = [
                    os.path.join(dirpath, f"{name}_log.ldf"),
                    os.path.join(dirpath, f"mastlog.ldf{name}.ldf"),
                    os.path.join(dirpath, f"{name}.ldf"),
                ]
                ldf = next((os.path.normpath(c) for c in candidates if os.path.exists(c)), None)
                out[name] = (mdf, ldf)
        return out

    def _db_exists(self, conn, name: str) -> bool:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM sys.databases WHERE name = ?", name)
        return cur.fetchone() is not None

    def _qident(self, name: str) -> str:
        return "[" + name.replace("]", "]]") + "]"

    def _sql_can_see_file(self, conn, full_path: str) -> bool:
        try:
            cur = conn.cursor()
            cur.execute("EXEC master.dbo.xp_fileexist ?", full_path)
            row = cur.fetchone()
            return any((row and c == 1) for c in row[:3])
        except Exception:
            return False

    def _attach_one(self, conn, name: str, mdf: str, ldf: Optional[str]):
        if not os.path.exists(mdf):
            raise FileNotFoundError(f"MDF no encontrado localmente: {mdf}")
        if not self._sql_can_see_file(conn, mdf):
            raise PermissionError(f"SQL Server no puede acceder al MDF: {mdf}")

        name_q = self._qident(name)
        mdf_q = mdf.replace("'", "''")

        if ldf and self._sql_can_see_file(conn, ldf):
            ldf_q = ldf.replace("'", "''")
            tsql = (
                f"CREATE DATABASE {name_q} ON "
                f"(FILENAME = N'{mdf_q}'), (FILENAME = N'{ldf_q}') FOR ATTACH;"
            )
        else:
            tsql = f"CREATE DATABASE {name_q} ON (FILENAME = N'{mdf_q}') FOR ATTACH;"

        cur = conn.cursor()
        cur.execute(tsql)

    def _run_copy_flow(self):
        def worker():
            instance = self.m_instance.get().strip()
            data_src = self.m_data_src.get().strip()
            emp_src  = self.m_emp_src.get().strip()
            root_dst = self.m_root_dst.get().strip()

            if not instance:
                self.after(0, lambda: messagebox.showwarning("Instancia", "Indica la instancia")); return
            if not data_src or not os.path.isdir(data_src):
                self.after(0, lambda: messagebox.showwarning("DATA ORIGEN", "Selecciona una carpeta válida")); return
            if not emp_src or not os.path.isdir(emp_src):
                self.after(0, lambda: messagebox.showwarning("Empresas (origen)", "Selecciona una carpeta válida")); return
            if not root_dst:
                self.after(0, lambda: messagebox.showwarning("Migración", "Indica carpeta raíz para 'Migracion'.")); return

            dlg = ProgressDialog(self, title="Copia", text="Preparando...")
            def progress_cb(pct, msg):
                self.after(0, lambda: dlg.set(pct, msg))

            try:
                zip_path, emp_dst = run_copy_task(
                    instance, data_src, emp_src, root_dst,
                    log_cb=None,
                    progress_cb=progress_cb,
                )
                self.after(0, lambda: messagebox.showinfo(
                    "Migración",
                    f"Listo.\nZIP DATA:\n{zip_path}\n\nEmpresas:\n{emp_dst}"
                ))
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror("Copia", str(ex)))
            finally:
                self.after(0, dlg.close)

        threading.Thread(target=worker, daemon=True).start()

    def _test_conn_attach(self):
        inst = self.a_instance.get().strip()
        if not inst:
            messagebox.showwarning("Instancia", "Indica la instancia"); return
        try:
            with sql_conn(inst, trusted=False, user=self.a_user.get().strip(), password=self.a_pwd.get()) as conn:
                cur = conn.cursor(); cur.execute("SELECT @@SERVERNAME, SYSTEM_USER, DB_NAME(), CONVERT(nvarchar(4000), SERVERPROPERTY('InstanceDefaultDataPath'))")
                s, u, db, datapath = cur.fetchone()
            self._alog(f"Conexión: {s} Usuario: {u}")
            self._alog(f"Ruta DATA de la instancia: {datapath}")
            messagebox.showinfo("Conexión", "Conexión exitosa.")
        except Exception as ex:
            self._alog(f"[ERROR] Conexión: {ex}"); messagebox.showerror("Conexión", str(ex))

    def _run_attach_flow(self):

        def worker():
            inst = self.a_instance.get().strip()
            data_src = self.a_data_src.get().strip()
            data_dst = self.a_data_dst.get().strip()

            if not inst:
                self.after(0, lambda: messagebox.showwarning("Instancia", "Indica la instancia SQL")); return
            if not data_src or not os.path.isdir(data_src):
                self.after(0, lambda: messagebox.showwarning("DATA ORIGEN", "Selecciona una carpeta válida")); return
            if not data_dst:
                self.after(0, lambda: messagebox.showwarning("DATA DESTINO", "Selecciona una carpeta de DATA DESTINO")); return

            try:
                self._alog(f"Copiando  {data_src}  ->  {data_dst}")
                copied = copy_data_tree(data_src, data_dst, skip_existing=True)
                if copied:
                    for _, d in copied:
                        self._alog(f"  copiado: {os.path.basename(d)}")
                else:
                    self._alog("  (no había archivos nuevos por copiar)")
            except Exception as ex:
                self._alog(f"[ERROR] Copia DATA: {ex}")
                self.after(0, lambda: messagebox.showerror("Copia DATA", str(ex)))
                return

            data_root = os.path.normpath(data_dst)

            try:
                with sql_conn(inst, trusted=False, user=self.a_user.get().strip(), password=self.a_pwd.get()) as conn:
                    self._alog("Bases principales")
                    catalogs = [
                        "DB_Directory",
                        "predeterminada",
                        "generalessql",
                        "CompacwAdmin",
                        "repositorioadminpaq",
                        ("Nomgenerales", "nomGenerales"),
                    ]
                    for item in catalogs:
                        tried = False
                        if isinstance(item, tuple):
                            err1 = None
                            for cand in item:
                                try:
                                    name, mdf, ldf = attach_catalog_by_name(conn, data_root + os.sep, cand)
                                    self._alog(f"   [OK] {name}: {mdf} | {os.path.basename(ldf) if ldf else '(rebuild log)'}")
                                    tried = True
                                    break
                                except Exception as ex1:
                                    err1 = str(ex1)
                            if not tried:
                                self._alog(f"   [WARN] Nomgenerales/nomGenerales: {err1}")
                        else:
                            try:
                                name, mdf, ldf = attach_catalog_by_name(conn, data_root + os.sep, item)
                                self._alog(f"   [OK] {name}: {mdf} | {os.path.basename(ldf) if ldf else '(rebuild log)'}")
                            except Exception as ex1:
                                self._alog(f"   [WARN] {item}: {ex1}")

                    self._alog(" Adjuntando ")
                    idx = self._scan_mdfs(data_root) 
                    adj_ok, adj_fail = set(), set()

                    all_names = sorted(n for n in idx.keys() if n not in self._SYSTEM_DB_NAMES)

                    for n in all_names:
                        mdf, ldf = idx[n]
                        try:
                            if self._db_exists(conn, n):
                                self._alog(f" {n}: ya existe")
                                continue
                            if n in self._SYSTEM_DB_NAMES:
                                self._alog(f"  {n}: excluida (sistema)")
                                continue

                            self._alog(f"   intentando: {n}  {mdf}  {('['+ldf+']' if ldf else '(sin LDF)')}")
                            self._attach_one(conn, n, mdf, ldf)
                            self._alog(f"   [OK] {n}")
                            adj_ok.add(n)
                        except Exception as ex:
                            self._alog(f"   [ERR] {n}: {ex}")
                            adj_fail.add(n)

                    self._alog("CHECKDB")
                    try:
                        for db in ["DB_Directory","predeterminada","generalessql","CompacwAdmin","repositorioadminpaq","Nomgenerales","nomGenerales"]:
                            if self._db_exists(conn, db):
                                conn.cursor().execute(f"DBCC CHECKDB({self._qident(db)}) WITH NO_INFOMSGS;")
                                self._alog(f"   CHECKDB {db}: OK")
                        for n in sorted(adj_ok):
                            try:
                                conn.cursor().execute(f"DBCC CHECKDB({self._qident(n)}) WITH NO_INFOMSGS;")
                                self._alog(f"   CHECKDB {n}: OK")
                            except Exception as ex2:
                                self._alog(f"   CHECKDB {n}: {ex2}")
                    except Exception as ex:
                        self._alog(f"   CHECKDB: {ex}")

                self._alog("Migración finalizada.")
                self.after(0, lambda: messagebox.showinfo("Adjuntar", "Proceso finalizado."))
            except Exception as ex:
                self._alog(f"[ERROR] Adjuntar: {ex}")
                self.after(0, lambda: messagebox.showerror("Adjuntar", str(ex)))

        threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    try:
        ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(ROOT_DIR)
    except Exception:
        pass
    App().mainloop()
