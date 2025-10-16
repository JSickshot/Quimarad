import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
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
from core.attach_task import run_attach_task 

class App(tk.Tk):
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
        ttk.Label(self.header, text="Migración CONTPAQi", style="Header.TLabel").grid(row=0, column=0, sticky="w")
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
                img = Image.open(logo_path); img.thumbnail((140, 48))
                self._logo_img = ImageTk.PhotoImage(img)
                ttk.Label(parent, image=self._logo_img).grid(row=0, column=1, sticky="e")
            else:
                ttk.Label(parent, text="QCG").grid(row=0, column=1, sticky="e")
        except Exception:
            ttk.Label(parent, text="QCG").grid(row=0, column=1, sticky="e")

    def show_frame(self, key: str):
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)

    def _build_home(self):
        home = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["home"] = home
        wrapper = ttk.Frame(home); wrapper.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Button(wrapper, text="1) Copiar DATA/Empresas", style="Accent.TButton",
                   command=lambda: self.show_frame("copy")).pack(fill="x", padx=4, pady=8)
        ttk.Button(wrapper, text="2) Attach", style="Accent.TButton",
                   command=lambda: self.show_frame("attach")).pack(fill="x", padx=4, pady=8)

    def _build_copy_page(self):
        page = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["copy"] = page
        tb = ttk.Frame(page); tb.pack(fill="x", padx=12, pady=(12, 4))
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
        ttk.Button(actions, text="Iniciar copia", style="Accent.TButton",
                   command=self._run_copy_flow).pack(side="left")

        ttk.Label(page, text="Ejecuta como Administrador", foreground="#666").pack(anchor="w", padx=20, pady=(6, 12))

    def _build_attach_page(self):
        page = ttk.Frame(self.stack, style="Card.TFrame")
        self.frames["attach"] = page

        tb = ttk.Frame(page); tb.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(tb, text=" Regresar", command=lambda: self.show_frame("home")).pack(side="left")
        ttk.Label(tb, text="Adjuntar (copiar DATA + attach)", font=("Segoe UI Semibold", 13)).pack(side="left", padx=12)

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
        ttk.Button(actions, text="Iniciar proceso", style="Accent.TButton",
                   command=self._run_attach_flow).pack(side="left")

        logf = ttk.Frame(page); logf.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        ttk.Label(logf, text="Log (Attach)").pack(anchor="w")
        self.a_log = tk.Text(logf, height=18, wrap="word"); self.a_log.pack(fill="both", expand=True)

    def _pick_dir(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Selecciona carpeta")
        if d: var.set(d)

    def _default_migracion_root(self) -> str:
        from pathlib import Path
        return str(Path.home() / "Desktop" / "Migracion")

    def _alog(self, msg: str):
        def _do():
            self.a_log.insert("end", msg + "\n"); self.a_log.see("end")
        self.after(0, _do)

    def _run_copy_flow(self):
        def worker():
            try:
                zip_path, emp_dst = run_copy_task(
                    instance=self.m_instance.get().strip(),
                    data_src=self.m_data_src.get().strip(),
                    emp_src=self.m_emp_src.get().strip(),
                    root_dst=self.m_root_dst.get().strip(),
                )
                messagebox.showinfo("Migración",
                                    f"Listo.\nZIP DATA:\n{zip_path}\n\nEmpresas:\n{emp_dst}")
            except Exception as ex:
                messagebox.showerror("Copia", str(ex))
        threading.Thread(target=worker, daemon=True).start()

    def _test_conn_attach(self):
        messagebox.showinfo("Conexión", "Usa 'Iniciar proceso' para ejecutar y validar credenciales.")

    def _run_attach_flow(self):
        def worker():
            try:
                run_attach_task(
                    instance=self.a_instance.get().strip(),
                    user=self.a_user.get().strip(),
                    password=self.a_pwd.get(),
                    data_src=self.a_data_src.get().strip(),
                    data_dst=self.a_data_dst.get().strip(),
                    log_cb=self._alog,  
                )
                messagebox.showinfo("Adjuntar", "Proceso completado.")
            except Exception as ex:
                self._alog(f"[ERROR] Adjuntar: {ex}")
                messagebox.showerror("Adjuntar", str(ex))
        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(ROOT_DIR)
    App().mainloop()
