# ui/app.py
import os
import datetime as _dt
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from typing import Optional

from PIL import Image, ImageTk  # pip install pillow

from settings import (
    APP_TITLE,
    QCG_LOGO_PATH,
    DEFAULT_SQL_INSTANCE,
    DEFAULT_SQL_USER,
    DEFAULT_SQL_PASSWORD,
)
from ui.theme import apply_theme

# Núcleo
from core.sql import sql_conn, run_tsql
from core.attach import attach_catalog_by_name
from core.files import copy_data_tree
from core.scripts import (
    tsql_contabilidad,
    tsql_nominas,
    tsql_comercial,
    tsql_add,
    tsql_checkdb_all,  # <-- CHECKDB
)
from core.sysops import (
    service_name_from_instance,
    stop_service,
    start_service,
    robocopy,
    SysOpError,
)


class App(tk.Tk):
    """
    Inicio con 2 botones:
      1) Copiar Data/Empresas (detener servicio → copiar a Escritorio\Migracion → iniciar servicio)
      2) Attach (copiar DATA origen→destino y adjuntar todo + CHECKDB rápido)
    """

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x860")
        self.minsize(1040, 800)
        self._logo_img: Optional[ImageTk.PhotoImage] = None

        # Tema QCG (usa el logo para derivar colores; con fallback negro/grises)
        apply_theme(self, QCG_LOGO_PATH)

        self._build_shell()
        self._build_home()
        self._build_copy_page()
        self._build_attach_page()
        self.show_frame("home")

    # ===== Shell =====
    def _build_shell(self):
        self.header = ttk.Frame(self)
        self.header.pack(fill="x", padx=16, pady=(12, 8))

        self.title_lbl = ttk.Label(self.header, text=APP_TITLE, style="Header.TLabel")
        self.title_lbl.pack(side="left")

        right = ttk.Frame(self.header)
        right.pack(side="right")
        self._load_logo(right)

        self.stack = ttk.Frame(self)
        self.stack.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.frames: dict[str, ttk.Frame] = {}

    def _load_logo(self, parent: ttk.Frame):
        try:
            if os.path.exists(QCG_LOGO_PATH):
                img = Image.open(QCG_LOGO_PATH)
                img.thumbnail((140, 48))
                self._logo_img = ImageTk.PhotoImage(img)
                ttk.Label(parent, image=self._logo_img).pack()
            else:
                ttk.Label(parent, text="QCG").pack()
        except Exception:
            ttk.Label(parent, text="QCG").pack()

    def show_frame(self, key: str):
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)

    # ===== HOME =====
    def _build_home(self):
        home = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["home"] = home

        wrapper = ttk.Frame(home)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(wrapper, text="¿Qué deseas hacer?", font=("Segoe UI Semibold", 16)).pack(pady=(0, 12))

        ttk.Button(
            wrapper,
            text="1) Copiar DATA/Empresas (servicio + robocopy)",
            style="Accent.TButton",
            command=lambda: self.show_frame("copy"),
        ).pack(fill="x", padx=4, pady=8)

        ttk.Button(
            wrapper,
            text="2) Attach (copiar DATA → instancia + adjuntar todo)",
            style="Accent.TButton",
            command=lambda: self.show_frame("attach"),
        ).pack(fill="x", padx=4, pady=8)

    # ===== PAGE 1: Copiar =====
    def _build_copy_page(self):
        page = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["copy"] = page

        tb = ttk.Frame(page)
        tb.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(tb, text="← Regresar", command=lambda: self.show_frame("home")).pack(side="left")
        ttk.Label(tb, text="1) Copiar DATA/Empresas a Escritorio\\Migracion", font=("Segoe UI Semibold", 13)).pack(
            side="left", padx=12
        )

        instf = ttk.LabelFrame(page, text="Instancia (para detener/iniciar servicio)")
        instf.pack(fill="x", padx=16, pady=(12, 10))
        r1 = ttk.Frame(instf)
        r1.pack(fill="x", pady=(4, 2))
        ttk.Label(r1, text="Instancia SQL (ej. localhost\\COMPAC):").pack(side="left")
        self.m_instance = tk.StringVar(value=DEFAULT_SQL_INSTANCE)
        ttk.Entry(r1, textvariable=self.m_instance, width=44).pack(side="left", padx=(8, 16))

        srcf = ttk.LabelFrame(page, text="Rutas de ORIGEN")
        srcf.pack(fill="x", padx=16, pady=(0, 10))
        r2 = ttk.Frame(srcf)
        r2.pack(fill="x", pady=(4, 2))
        ttk.Label(r2, text="DATA ORIGEN:").pack(side="left")
        self.m_data_src = tk.StringVar()
        ttk.Entry(r2, textvariable=self.m_data_src, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r2, text="Elegir…", command=lambda: self._pick_dir(self.m_data_src)).pack(side="left")

        r3 = ttk.Frame(srcf)
        r3.pack(fill="x", pady=(2, 2))
        ttk.Label(r3, text="Empresas (origen):").pack(side="left")
        self.m_emp_src = tk.StringVar(value=r"C:\Compac\Empresas")
        ttk.Entry(r3, textvariable=self.m_emp_src, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r3, text="Elegir…", command=lambda: self._pick_dir(self.m_emp_src)).pack(side="left")

        dstf = ttk.LabelFrame(page, text="Destino raíz")
        dstf.pack(fill="x", padx=16, pady=(0, 10))
        r4 = ttk.Frame(dstf)
        r4.pack(fill="x", pady=(4, 2))
        ttk.Label(r4, text="Carpeta 'Migracion' (en Escritorio):").pack(side="left")
        self.m_root_dst = tk.StringVar(value=self._default_migracion_root())
        ttk.Entry(r4, textvariable=self.m_root_dst, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r4, text="Elegir…", command=lambda: self._pick_dir(self.m_root_dst)).pack(side="left")

        actions = ttk.Frame(page)
        actions.pack(fill="x", padx=16, pady=(6, 8))
        ttk.Button(
            actions,
            text="Detener servicio → Copiar DATA (/E) → Copiar Empresas (estructura) → Iniciar servicio",
            style="Accent.TButton",
            command=self._run_copy_flow,
        ).pack(side="left")

        logf = ttk.Frame(page)
        logf.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        ttk.Label(logf, text="Log (Copia DATA/Empresas)").pack(anchor="w")
        self.m_log = tk.Text(logf, height=18, wrap="word")
        self.m_log.pack(fill="both", expand=True)

        ttk.Label(
            page,
            text="* Ejecuta como Administrador para detener/arrancar servicio y copiar en carpetas protegidas.",
            foreground="#666",
        ).pack(anchor="w", padx=20)

    # ===== PAGE 2: Attach =====
    def _build_attach_page(self):
        page = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["attach"] = page

        tb = ttk.Frame(page)
        tb.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(tb, text="← Regresar", command=lambda: self.show_frame("home")).pack(side="left")
        ttk.Label(tb, text="2) Copiar DATA a instancia + Adjuntar todo", font=("Segoe UI Semibold", 13)).pack(
            side="left", padx=12
        )

        connf = ttk.LabelFrame(page, text="Conexión (SQL Authentication)")
        connf.pack(fill="x", padx=16, pady=(12, 10))
        r1 = ttk.Frame(connf)
        r1.pack(fill="x", pady=(4, 2))
        ttk.Label(r1, text="Instancia SQL (ej. localhost\\COMPAC):").pack(side="left")
        self.a_instance = tk.StringVar(value=DEFAULT_SQL_INSTANCE)
        ttk.Entry(r1, textvariable=self.a_instance, width=44).pack(side="left", padx=(8, 16))
        r2 = ttk.Frame(connf)
        r2.pack(fill="x", pady=(2, 2))
        ttk.Label(r2, text="Usuario:").pack(side="left")
        self.a_user = tk.StringVar(value=DEFAULT_SQL_USER)
        ttk.Entry(r2, textvariable=self.a_user, width=24).pack(side="left", padx=(8, 16))
        ttk.Label(r2, text="Contraseña:").pack(side="left")
        self.a_pwd = tk.StringVar(value=DEFAULT_SQL_PASSWORD)
        ttk.Entry(r2, textvariable=self.a_pwd, width=24, show="•").pack(side="left", padx=(8, 16))
        ttk.Button(connf, text="Probar conexión", command=self._test_conn_attach).pack(pady=(6, 4), anchor="w")

        pathf = ttk.LabelFrame(page, text="Rutas DATA (origen → destino de instancia)")
        pathf.pack(fill="x", padx=16, pady=(0, 10))
        r3 = ttk.Frame(pathf)
        r3.pack(fill="x", pady=(4, 2))
        ttk.Label(r3, text="DATA ORIGEN:").pack(side="left")
        self.a_data_src = tk.StringVar()
        ttk.Entry(r3, textvariable=self.a_data_src, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r3, text="Elegir…", command=lambda: self._pick_dir(self.a_data_src)).pack(side="left")
        r4 = ttk.Frame(pathf)
        r4.pack(fill="x", pady=(2, 4))
        ttk.Label(r4, text="DATA DESTINO (instancia nueva):").pack(side="left")
        self.a_data_dst = tk.StringVar()
        ttk.Entry(r4, textvariable=self.a_data_dst, width=80).pack(side="left", padx=(8, 8))
        ttk.Button(r4, text="Elegir…", command=lambda: self._pick_dir(self.a_data_dst)).pack(side="left")

        actions = ttk.Frame(page)
        actions.pack(fill="x", padx=16, pady=(6, 8))
        ttk.Button(
            actions,
            text="Copiar DATA (.mdf/.ldf) → Adjuntar catálogos + Comercial + Contabilidad + Nóminas + ADD (1/2/3) + CHECKDB",
            style="Accent.TButton",
            command=self._run_attach_flow,
        ).pack(side="left")

        logf = ttk.Frame(page)
        logf.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        ttk.Label(logf, text="Log (Attach)").pack(anchor="w")
        self.a_log = tk.Text(logf, height=18, wrap="word")
        self.a_log.pack(fill="both", expand=True)

    # ===== Helpers =====
    def _pick_dir(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Selecciona carpeta")
        if d:
            var.set(d)

    def _default_migracion_root(self) -> str:
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        return os.path.join(desk, "Migracion")

    def _tstamp(self) -> str:
        return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    def _mlog(self, msg: str):
        self.m_log.insert("end", msg + "\n")
        self.m_log.see("end")
        self.update_idletasks()

    def _alog(self, msg: str):
        self.a_log.insert("end", msg + "\n")
        self.a_log.see("end")
        self.update_idletasks()

    # ===== Acciones: Copiar =====
    def _run_copy_flow(self):
        instance = self.m_instance.get().strip()
        data_src = self.m_data_src.get().strip()
        emp_src = self.m_emp_src.get().strip()
        root_dst = self.m_root_dst.get().strip()

        if not instance:
            messagebox.showwarning("Instancia", "Indica la instancia (p. ej. localhost\\COMPAC).")
            return
        if not data_src or not os.path.isdir(data_src):
            messagebox.showwarning("DATA ORIGEN", "Selecciona una carpeta válida de DATA ORIGEN.")
            return
        if not emp_src or not os.path.isdir(emp_src):
            messagebox.showwarning("Empresas (origen)", "Selecciona una carpeta válida de Empresas (origen).")
            return
        if not root_dst:
            messagebox.showwarning("Migracion", "Indica carpeta raíz para 'Migracion'.")
            return

        os.makedirs(root_dst, exist_ok=True)
        data_dst = os.path.join(root_dst, f"DATA_{self._tstamp()}")
        emp_dst = os.path.join(root_dst, f"Empresas_{self._tstamp()}")
        os.makedirs(data_dst, exist_ok=True)
        os.makedirs(emp_dst, exist_ok=True)

        # 1) Detener servicio
        try:
            svc = service_name_from_instance(instance)
            self._mlog(f"> Deteniendo servicio {svc} … (requiere admin)")
            out = stop_service(svc)
            self._mlog(out)
        except SysOpError as ex:
            self._mlog(f"[ERROR] Servicio: {ex}")
            messagebox.showerror("Servicio", str(ex))
            return

        # 2) Copiar DATA (con archivos) → /E
        try:
            self._mlog(f"> ROBOCOPY DATA (con archivos): {data_src}  →  {data_dst}")
            out = robocopy(data_src, data_dst, ["/E"])
            self._mlog(out)
        except Exception as ex:
            self._mlog(f"[ERROR] ROBOCOPY DATA: {ex}")
            messagebox.showerror("ROBOCOPY DATA", str(ex))

        # 3) Copiar estructura Empresas → /E /XF *.*
        try:
            self._mlog(f"> ROBOCOPY Empresas (estructura): {emp_src}  →  {emp_dst}")
            out = robocopy(emp_src, emp_dst, ["/E", "/XF", "*.*"])
            self._mlog(out)
        except Exception as ex:
            self._mlog(f"[ERROR] ROBOCOPY Empresas: {ex}")
            messagebox.showerror("ROBOCOPY Empresas", str(ex))

        # 4) Iniciar servicio
        try:
            svc = service_name_from_instance(instance)
            self._mlog(f"> Iniciando servicio {svc} …")
            out = start_service(svc)
            self._mlog(out)
        except SysOpError as ex:
            self._mlog(f"[ERROR] Servicio: {ex}")
            messagebox.showerror("Servicio", str(ex))
            return

        self._mlog(f"✓ Migración lista. Carpeta raíz: {root_dst}")
        messagebox.showinfo("Migración", f"Listo. Revisa:\n{root_dst}")

    # ===== Acciones: Attach =====
    def _test_conn_attach(self):
        inst = self.a_instance.get().strip()
        if not inst:
            messagebox.showwarning("Instancia", "Indica la instancia (p. ej. localhost\\COMPAC).")
            return
        try:
            with sql_conn(inst, trusted=False, user=self.a_user.get().strip(), password=self.a_pwd.get()) as conn:
                cur = conn.cursor()
                cur.execute("SELECT @@SERVERNAME, SYSTEM_USER, DB_NAME()")
                s, u, db = cur.fetchone()
            self._alog(f"[OK] Conexión: {s} — Usuario: {u} — DB: {db}")
            messagebox.showinfo("Conexión", "Conexión exitosa.")
        except Exception as ex:
            self._alog(f"[ERROR] Conexión: {ex}")
            messagebox.showerror("Conexión", str(ex))

    def _run_attach_flow(self):
        inst = self.a_instance.get().strip()
        data_src = self.a_data_src.get().strip()
        data_dst = self.a_data_dst.get().strip()
        if not inst:
            messagebox.showwarning("Instancia", "Indica la instancia SQL (p. ej. localhost\\COMPAC).")
            return
        if not data_src or not os.path.isdir(data_src):
            messagebox.showwarning("DATA ORIGEN", "Selecciona una carpeta válida de DATA ORIGEN.")
            return
        if not data_dst:
            messagebox.showwarning("DATA DESTINO", "Selecciona una carpeta de DATA DESTINO.")
            return

        # 1) Copiar .mdf/.ldf (sin sobrescribir)
        try:
            self._alog(f"> Copiando .mdf/.ldf: {data_src}  →  {data_dst}")
            copied = copy_data_tree(data_src, data_dst, skip_existing=True)
            if copied:
                for _, d in copied:
                    self._alog(f"  copiado: {os.path.basename(d)}")
            else:
                self._alog("  (no había archivos nuevos por copiar)")
        except Exception as ex:
            self._alog(f"[ERROR] Copia DATA: {ex}")
            messagebox.showerror("Copia DATA", str(ex))
            return

        data_path_for_sql = data_dst if data_dst.endswith("\\") else (data_dst + "\\")

        # 2) Adjuntar + queries + CHECKDB
        try:
            with sql_conn(inst, trusted=False, user=self.a_user.get().strip(), password=self.a_pwd.get()) as conn:
                # Adjuntar catálogos en orden
                self._alog("> Adjuntando catálogos base…")
                for db in ["DB_Directory", "predeterminada", "generalessql", "CompacwAdmin", "repositorioadminpaq", "nomGenerales"]:
                    try:
                        name, mdf, ldf = attach_catalog_by_name(conn, data_path_for_sql, db)
                        self._alog(f"  [OK] {name}: {os.path.basename(mdf)} | {os.path.basename(ldf)}")
                    except Exception as ex1:
                        self._alog(f"  [WARN] {db}: {ex1}")

                # Comercial → Contabilidad → Nóminas
                self._alog("> Comercial…")
                run_tsql(conn, tsql_comercial(data_path_for_sql))
                self._alog("  [OK] Comercial")

                self._alog("> Contabilidad…")
                run_tsql(conn, tsql_contabilidad(data_path_for_sql))
                self._alog("  [OK] Contabilidad")

                self._alog("> Nóminas…")
                run_tsql(conn, tsql_nominas(data_path_for_sql))
                self._alog("  [OK] Nóminas")

                # ADD casos 1 → 2 → 3
                self._alog("> ADD — Caso 1 (mastlog.ldf + nombre + .ldf)…")
                run_tsql(conn, tsql_add(data_path_for_sql, 1))
                self._alog("  [OK] Caso 1")

                self._alog("> ADD — Caso 2 (nombre + _log.ldf)…")
                run_tsql(conn, tsql_add(data_path_for_sql, 2))
                self._alog("  [OK] Caso 2")

                self._alog("> ADD — Caso 3 (nombre + .ldf)…")
                run_tsql(conn, tsql_add(data_path_for_sql, 3))
                self._alog("  [OK] Caso 3")

                # CHECKDB automático (rápido)
                self._alog("> CHECKDB rápido (PHYSICAL_ONLY) en todas las bases…")
                run_tsql(conn, tsql_checkdb_all(quick=True))
                self._alog("  [OK] CHECKDB finalizado.")

            self._alog("✓ Proceso finalizado.")
            messagebox.showinfo("Adjuntar", "Copia, adjuntos/queries y CHECKDB completados.")
        except Exception as ex:
            self._alog(f"[ERROR] Adjuntar: {ex}")
            messagebox.showerror("Adjuntar", str(ex))


if __name__ == "__main__":
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(ROOT_DIR)
    App().mainloop()
