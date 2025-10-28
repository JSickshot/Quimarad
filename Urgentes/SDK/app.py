# app.py
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from datetime import datetime

from features.ui_grid import InvoiceGrid
from features.factura_loader import FacturaLoader
from features.catalogs import CatalogManager, get_next_folio
from sdk.loader import get_sdk

EMPRESAS_BASE = Path(r"C:\Compac\Empresas")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CONTPAQi Comercial — Carga de facturas (captura + F3)")
        self.geometry("1280x780")

        self.sdk=None; self.catalogs=None; self.empresa_abierta=False; self.empresa_actual=None

        top = ttk.Frame(self); top.pack(fill=tk.X, padx=10, pady=(10,6))
        ttk.Label(top, text="Empresa:").pack(side=tk.LEFT)
        self.cbo_emp=ttk.Combobox(top, width=90); self.cbo_emp.pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Empresas ad*", command=self._scan_empresas_ad).pack(side=tk.LEFT)
        ttk.Button(top, text="Seleccionar…", command=self._pick_empresa).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Abrir empresa", command=self._open_empresa).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Cargar catálogos (F3)", command=self._load_catalogs).pack(side=tk.LEFT, padx=12)
        self.lbl_cat=ttk.Label(top, text="Catálogos: 0"); self.lbl_cat.pack(side=tk.LEFT, padx=10)

        self.grid = InvoiceGrid(
            self,
            on_lookup_f3=self._on_lookup_f3,          # compat
            on_commit_cell=self._on_commit_cell,
            show_filters=False,
            get_items=self._get_items_for_dropdown,   # <- dropdown desplegable
        )
        self.grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,6))
        self.grid.add_row({"cFecha": datetime.now().strftime("%Y/%m/%d")})

        bar = ttk.Frame(self); bar.pack(fill=tk.X, padx=10, pady=(0,6))
        ttk.Button(bar, text="Ajustar columnas", command=self.grid.autosize_columns).pack(side=tk.LEFT)
        ttk.Button(bar, text="Previsualizar", command=self._preview).pack(side=tk.RIGHT, padx=8)
        ttk.Button(bar, text="Crear factura", command=self._crear_factura).pack(side=tk.RIGHT)

        self.log = ScrolledText(self, height=9); self.log.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0,8))
        self.status = ttk.Label(self, anchor="w",
                                text="F3/Alt+↓ abre desplegable. Fecha: YYYY/MM/DD, DD/MM/YYYY o YYYYMMDD.")
        self.status.pack(fill=tk.X, padx=10, pady=(0,8))

        self._scan_empresas_ad()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- infra ----------
    def _log(self, s): self.log.insert(tk.END, s+"\n"); self.log.see(tk.END)
    def _err(self, s): messagebox.showerror("Error", s)

    def _ensure_sdk(self):
        if self.sdk: return True
        try:
            self.sdk = get_sdk(); self._log("[SDK] OK.")
            return True
        except Exception as e:
            self._err(str(e)); return False

    def _scan_empresas_ad(self):
        vals=[]
        base=EMPRESAS_BASE
        if base.exists():
            for ch in sorted(base.iterdir(), key=lambda p: p.name.lower()):
                if ch.is_dir() and ch.name.lower().startswith("ad"): vals.append(str(ch))
        self.cbo_emp["values"]=vals
        if vals and not self.cbo_emp.get().strip(): self.cbo_emp.set(vals[0])

    def _pick_empresa(self):
        base=EMPRESAS_BASE if EMPRESAS_BASE.exists() else Path("C:\\")
        d=filedialog.askdirectory(title="Selecciona carpeta de la EMPRESA", initialdir=str(base))
        if d: self.cbo_emp.set(d)

    def _open_empresa(self):
        if not self._ensure_sdk(): return
        ruta=self.cbo_emp.get().strip()
        if not ruta: self._err("Selecciona la carpeta de la empresa."); return
        try:
            if not (self.empresa_abierta and self.empresa_actual==ruta):
                self.sdk.abre_empresa(ruta)
                self.empresa_abierta=True; self.empresa_actual=ruta
                self._log(f"[Empresa] Abierta: {ruta}")
            self._load_catalogs()
        except Exception as e:
            self.empresa_abierta=False; self.empresa_actual=None; self._err(str(e))

    def _load_catalogs(self):
        if not (self._ensure_sdk() and self.empresa_abierta): return
        self.catalogs = CatalogManager(self.sdk)
        self.catalogs.load_all(logger=self._log)
        self.lbl_cat.config(text="Catálogos: F3 listo")

    # ---------- dropdown data ----------
    def _get_items_for_dropdown(self, field):
        # Si no hay catálogos, intenta cargarlos automáticamente
        if not self.catalogs or not any(self.catalogs.get_dict().values()):
            try: self._load_catalogs()
            except Exception: pass
        if not self.catalogs:
            return []
        d=self.catalogs.get_dict()
        key_map={
            "cCodConcepto":"concepto","cCodProyecto":"proyecto","cSerie":"serie",
            "cCodCteProv":"cliente","cIdMoneda":"moneda","cCodAgente":"agente",
            "cCodProducto":"producto","cCodAlmacen":"almacen"
        }
        return d.get(key_map.get(field,""), []) or []

    # ---------- F3 (modo cuadro, no usado porque hay dropdown; dejamos stub) ----------
    def _on_lookup_f3(self, field, current_value):
        return current_value

    # ---------- fecha/folio/validación por código ----------
    def _normalize_date(self, s):
        s=(s or "").strip()
        if not s: return s
        t=s.replace("\\","/").replace("-","/").replace(".","/")
        parts=t.split("/")
        try:
            if len(parts)==3:
                if len(parts[0])==4: y,m,d=parts
                else: d,m,y=parts
                from datetime import datetime
                return datetime(int(y),int(m),int(d)).strftime("%Y%m%d")
            if len(s)==8 and s.isdigit(): return s
        except Exception:
            pass
        return s

    def _on_commit_cell(self, row_index, field, new_value):
        row=self.grid.get_row_cached(row_index)

        # Normaliza fecha a YYYYMMDD en cuanto se escribe
        if field=="cFecha":
            norm=self._normalize_date(new_value)
            if norm!=new_value:
                self.grid.set_cell(row_index,"cFecha",norm)
            return

        # Validación por código (cliente/concepto) si el usuario teclea directo
        if self.catalogs and new_value:
            try:
                if field=="cCodCteProv" and self.catalogs.find_cliente:
                    info=self.catalogs.find_cliente(new_value)
                    if info:
                        self.status.config(text=f"Cliente: {info.get('codigo')} — {info.get('nombre')}")
                if field=="cCodConcepto" and self.catalogs.find_concepto:
                    info=self.catalogs.find_concepto(new_value)
                    if info:
                        self.status.config(text=f"Concepto: {info.get('codigo')} — {info.get('nombre')}")
            except Exception:
                pass

        # Folio sugerido cuando hay concepto/serie
        if field in ("cCodConcepto","cSerie") and self.sdk:
            conc = new_value if field=="cCodConcepto" else (row.get("cCodConcepto") or "")
            serie= new_value if field=="cSerie"       else (row.get("cSerie") or "")
            if conc:
                folio=get_next_folio(self.sdk, conc, serie)
                if folio:
                    self.grid.set_cell(row_index,"cFolio",folio)
                    self.status.config(text=f"Folio sugerido: {conc}/{serie} → {folio}")

    # ---------- acciones ----------
    def _preview(self):
        rows=self.grid.get_rows()
        self._log("== Preview ==")
        for r in rows[:10]: self._log(str(r))

    def _crear_factura(self):
        if not (self._ensure_sdk() and self.empresa_abierta): return
        mapping=[
            ("cCodConcepto","Concepto Código <F3>"),("cCodProyecto","Proyecto Codigo <F3>"),
            ("cFecha","Fecha"),("cSerie","Serie"),("cFolio","Folio"),
            ("cCodCteProv","Cliente Código <F3>"),("cIdMoneda","Moneda Id <F3>"),
            ("cTipoCambio","Tipo de Cambio"),("cCodAgente","Agente Código <F3>"),
            ("cCodProducto","Producto Código <F3>"),("cCodAlmacen","Almacén Código <F3>"),
            ("cUnidades","Cantidad"),("cPrecio","Precio Unitario"),
            ("cDesc1","Descuento 1 (%)"),("cDesc2","Descuento 2 (%)"),
            ("cDesc3","Descuento 3 (%)"),("cIVA","IVA (%)"),
        ]
        headers=[t for _,t in mapping]
        rows=[]
        for g in self.grid.get_rows():
            r={}
            for k,t in mapping:
                v=g.get(k,"");  r[t] = self._normalize_date(v) if k=="cFecha" else v
            rows.append(r)

        loader=FacturaLoader(self.sdk, tolerant=True, logger=self._log)
        try:
            loader.crear_desde_tabla(headers, rows, usar_primer_renglon_para_encabezado=True, simular=False)
            messagebox.showinfo("OK","Factura creada.")
        except Exception as e:
            self._err(str(e))

    def _on_close(self):
        try:
            if self.sdk:
                try: self.sdk.cierra_empresa()
                except Exception: pass
                try: self.sdk.terminar()
                except Exception: pass
        finally:
            self.destroy()

if __name__=="__main__":
    App().mainloop()
