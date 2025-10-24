import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

from sdk import get_sdk
from features.factura_loader import FacturaLoader, COLUMNS_ALL
from features.ui_grid import EditableGrid
from features.catalogs import CatalogManager

EMPRESAS_BASE = Path(r"C:\Compac\Empresas")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Carga masiva")
        self.geometry("1360x800")

        self.sdk = None
        try:
            self.sdk = get_sdk()
            messagebox.showinfo("SDK", "SDK cargado correctamente.")
        except Exception as e:
            messagebox.showerror("SDK", str(e))

        self.simular = tk.BooleanVar(value=False)

        # Top: empresa
        top = ttk.Frame(self); top.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(top, text="Empresa:").pack(side=tk.LEFT)
        self.cbo_emp = ttk.Combobox(top, width=90)
        self.cbo_emp.pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Empresas ad*", command=self._scan_empresas_ad).pack(side=tk.LEFT)
        ttk.Button(top, text="Seleccionar…", command=self._pick_empresa).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Abrir empresa", command=self._open_empresa).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(top, text="Simular (no guarda)", variable=self.simular).pack(side=tk.LEFT, padx=16)

        # Catálogos
        cat = ttk.Frame(self); cat.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(cat, text="Cargar catálogos (F3)", command=self._load_catalogs).pack(side=tk.LEFT)
        self.lbl_cat = ttk.Label(cat, text="Catálogos: 0", width=50, anchor="w")
        self.lbl_cat.pack(side=tk.LEFT, padx=10)

        # Grid (tipo Excel) -> OJO: EditableGrid se autocoloca con GRID
        grid_frame = ttk.Frame(self); grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        self.grid = EditableGrid(grid_frame, columns=COLUMNS_ALL, height=20)
        self.grid.enable_catalogs(lambda: self.catalogs)  # getter perezoso

        # Acciones hoja
        act = ttk.Frame(self); act.pack(fill=tk.X, padx=10, pady=4)
        ttk.Button(act, text="Agregar renglón", command=self.grid.add_row).pack(side=tk.LEFT)
        ttk.Button(act, text="Eliminar renglón", command=self.grid.delete_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(act, text="Pegar desde Excel", command=self.grid.paste_from_clipboard).pack(side=tk.LEFT, padx=6)
        ttk.Button(act, text="Limpiar", command=self.grid.clear_sheet).pack(side=tk.LEFT, padx=6)
        ttk.Button(act, text="Previsualizar", command=self._preview).pack(side=tk.RIGHT, padx=8)
        ttk.Button(act, text="Crear factura", command=self._crear_factura).pack(side=tk.RIGHT)

        # Log
        self.log = ScrolledText(self, height=12)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        # Estado
        self.catalogs = CatalogManager(self.sdk) if self.sdk else None
        self._scan_empresas_ad()
        self.grid.add_row()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -------- util ----------
    def _log(self, s): self.log.insert(tk.END, s + "\n"); self.log.see(tk.END); self.update_idletasks()

    # -------- empresas ----------
    def _scan_empresas_ad(self):
        values = []
        if EMPRESAS_BASE.exists():
            for ch in sorted(EMPRESAS_BASE.iterdir(), key=lambda p: p.name.lower()):
                if ch.is_dir() and ch.name.lower().startswith("ad"):
                    values.append(str(ch))
        self.cbo_emp["values"] = values
        if values and not self.cbo_emp.get().strip():
            self.cbo_emp.set(values[0])

    def _pick_empresa(self):
        base = EMPRESAS_BASE if EMPRESAS_BASE.exists() else Path("C:\\")
        d = filedialog.askdirectory(title="Selecciona carpeta de la EMPRESA", initialdir=str(base))
        if d: self.cbo_emp.set(d)

    def _open_empresa(self):
        try:
            if not self.sdk or not self.sdk.loaded:
                messagebox.showerror("SDK", "SDK no cargado."); return
            ruta = self.cbo_emp.get().strip()
            if not ruta:
                messagebox.showerror("Empresa", "Escribe o elige una empresa."); return
            self.sdk.abre_empresa(ruta)
            messagebox.showinfo("Empresa", f"Empresa abierta:\n{ruta}")
            self._load_catalogs() 
        except Exception as e:
            messagebox.showerror("Empresa", str(e))

    def _load_catalogs(self):
        if not self.catalogs:
            messagebox.showerror("Catálogos", "SDK no cargado."); return
        try:
            total = self.catalogs.load_all(self._log)
            self.lbl_cat.config(text=f"Catálogos: {total} entradas")
            messagebox.showinfo("Catálogos", "Listo. En columnas con <F3> escribe o presiona F3 para sugerencias.")
        except Exception as e:
            messagebox.showerror("Catálogos", str(e))

    def _preview(self):
        headers, rows = self.grid.get_headers_and_rows()
        if not rows:
            messagebox.showinfo("Previsualizar", "Sin renglones."); return
        self._log("== Previsualización (primeros 10) ==")
        for r in rows[:10]:
            self._log(f"{r.get('Producto Código <F3>', '')} x {r.get('Cantidad','')} @ {r.get('Precio Unitario','')} (alm {r.get('Almacén Código <F3>','') or '1'})")

    def _crear_factura(self):
        if not self.sdk or not self.sdk.loaded:
            messagebox.showerror("SDK", "SDK no cargado."); return
        if not self.cbo_emp.get().strip():
            messagebox.showerror("Empresa", "Abre una empresa."); return

        headers, rows = self.grid.get_headers_and_rows()
        if not rows:
            messagebox.showerror("Datos", "No hay renglones."); return

        loader = FacturaLoader(self.sdk, tolerant=True, logger=self._log)
        try:
            loader.crear_desde_tabla(headers, rows, usar_primer_renglon_para_encabezado=True, simular=self.simular.get())
            if not self.simular.get():
                messagebox.showinfo("OK", "Factura creada y guardada.")
        except Exception as e:
            messagebox.showerror("Cargar", str(e))

    def _on_close(self):
        try:
            if self.sdk:
                self.sdk.cierra_empresa(); self.sdk.terminar()
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
