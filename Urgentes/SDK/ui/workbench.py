# ui/workbench.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, csv, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from features.catalogs import (
    conceptos, clientes, productos, almacenes, agentes, monedas, series
)
from features.factura_loader import FacturaLoader
from features.ui_grid import GridEditor, GRID_COLUMNS
from features.select_dialog import select_code

APP_TITLE = "Carga Masiva — CONTPAQi Comercial (Premium)"

class Workbench(tk.Tk):
    def __init__(self, sdk=None):
        super().__init__()
        self.title(APP_TITLE); self.geometry("1320x760")

        self.sdk = sdk
        if not self.sdk:
            messagebox.showerror("SDK", "Workbench requiere un SDK ya inicializado.")
            self.destroy(); return
        self.cache: dict[str, list[tuple[str,str]]] = {}

        # Barra superior
        top = ttk.Frame(self); top.pack(fill="x", padx=10, pady=(10,6))
        self.lbl_sdk = ttk.Label(top, text=f"SDK listo: {getattr(self.sdk,'sdk_dir','(desconocido)')}")
        self.lbl_sdk.pack(side="left", padx=(0,10))
        ttk.Button(top, text="Catálogos (F3)", command=self._load_cats).pack(side="left", padx=4)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(top, text="Importar Excel/CSV", command=self._import_excel).pack(side="left", padx=4)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(top, text="Simular", command=lambda: self._crear(simular=True)).pack(side="left", padx=6)
        ttk.Button(top, text="Crear",   command=lambda: self._crear(simular=False)).pack(side="left", padx=6)

        # Log
        self.txt = tk.Text(self, height=8); self.txt.pack(fill="x", padx=10, pady=(0,6))
        self._log("Workbench listo.")

        # Encabezado
        hdr = ttk.LabelFrame(self, text="Datos del documento"); hdr.pack(fill="x", padx=10, pady=(0,8))

        self.v_conc   = tk.StringVar()
        self.v_fecha  = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self.v_serie  = tk.StringVar()
        self.v_folio  = tk.StringVar()
        self.v_cte    = tk.StringVar()
        self.v_moneda = tk.StringVar(value="1")
        self.v_tc     = tk.StringVar(value="1.0000")
        self.v_agente = tk.StringVar()

        def L(r,c,t): ttk.Label(hdr, text=t).grid(row=r,column=c,sticky="e",padx=(6,4),pady=3)
        def E(r,c,var,w=14):
            e=ttk.Entry(hdr,textvariable=var,width=w); e.grid(row=r,column=c,sticky="w",padx=(0,10),pady=3); return e
        def F3(r,c,fn): ttk.Button(hdr,text="F3",width=3,command=fn).grid(row=r,column=c,sticky="w",padx=(0,10))

        L(0,0,"Concepto:"); E(0,1,self.v_conc,18); F3(0,2,lambda: self._pick("cCodConcepto", self.v_conc))
        L(0,3,"Fecha:");    E(0,4,self.v_fecha,12); ttk.Button(hdr,text="Hoy",width=4,
                 command=lambda:self.v_fecha.set(datetime.now().strftime("%d/%m/%Y"))).grid(row=0,column=5,sticky="w",padx=(0,10))
        L(0,6,"Serie:");    E(0,7,self.v_serie,8)
        L(0,8,"Folio:");    E(0,9,self.v_folio,8)

        L(1,0,"Cliente:");  E(1,1,self.v_cte,18); F3(1,2,lambda: self._pick("cCodCteProv", self.v_cte))
        L(1,3,"Moneda:");   E(1,4,self.v_moneda,8); F3(1,5,lambda: self._pick("cIdMoneda", self.v_moneda))
        L(1,6,"Tipo cambio:"); E(1,7,self.v_tc,10)
        L(1,8,"Agente:");  E(1,9,self.v_agente,12); F3(1,10,lambda: self._pick("cCodAgente", self.v_agente))

        # Alta rápida de movimiento
        fast = ttk.LabelFrame(self, text="Alta rápida de movimiento"); fast.pack(fill="x", padx=10, pady=(0,8))
        self.v_prod = tk.StringVar(); self.v_alm  = tk.StringVar()
        self.v_cant = tk.StringVar(value="1"); self.v_prec = tk.StringVar(value="0")
        self.v_iva  = tk.StringVar(value="16"); self.v_d1   = tk.StringVar(value="0")

        def EL(frm, txt, col, var, w=14, with_f3=False, f3field=""):
            ttk.Label(frm, text=txt).grid(row=0,column=col,sticky="e",padx=(6,4))
            e=ttk.Entry(frm,textvariable=var,width=w); e.grid(row=0,column=col+1,sticky="w",padx=(0,8))
            if with_f3:
                ttk.Button(frm, text="F3", width=3,
                           command=lambda: self._pick(f3field, var)).grid(row=0, column=col+2, sticky="w")
            return e

        EL(fast,"Producto",0,self.v_prod,18,True,"cCodigoProducto")
        EL(fast,"Almacén", 3,self.v_alm,10,True,"cCodAlmacen")
        EL(fast,"Cant.",   6,self.v_cant,8)
        EL(fast,"Precio",  8,self.v_prec,8)
        EL(fast,"IVA %",  10,self.v_iva,6)
        EL(fast,"Desc1 %",12,self.v_d1,6)
        ttk.Button(fast, text="Agregar", width=10, command=self._agregar_mov_rapido)\
            .grid(row=0, column=14, sticky="w", padx=6)

        # Grid
        body = ttk.LabelFrame(self, text="1 Movimientos"); body.pack(fill="both", expand=True, padx=10, pady=(0,10))
        self.grid = GridEditor(self); self.grid.pack(fill="both", expand=True, padx=6, pady=6)

        # cargar catálogos (empresa ya está abierta)
        self._load_cats()

    def _log(self, s: str):
        self.txt.insert("end", f"{datetime.now().strftime('%H:%M:%S')} {s}\n")
        self.txt.see("end")

    def _load_cats(self):
        try:
            self.cache = {
                "cCodConcepto":    conceptos(self.sdk),
                "cCodCteProv":     clientes(self.sdk),
                "cCodigoProducto": productos(self.sdk),
                "cCodAlmacen":     almacenes(self.sdk),
                "cCodAgente":      agentes(self.sdk),
                "cIdMoneda":       monedas(self.sdk),
                "cSerie":          series(self.sdk),
            }
            if not self.v_moneda.get().strip(): self.v_moneda.set("1")
            if not self.v_serie.get().strip():
                sers = [c for c,_ in self.cache.get("cSerie", [])]
                if "1" in sers: self.v_serie.set("1")
            for k,v in self.cache.items(): self._log(f"[Cat] {k}: {len(v)}")
        except Exception as e:
            self._log(f"[Cat] Error: {e}")
            self.cache = {}

    def _pick(self, field: str, var: tk.StringVar):
        items = self.cache.get(field) or []
        code = select_code(self, f"Seleccione {field}", items, var.get())
        if code: var.set(code)

    def _agregar_mov_rapido(self):
        if not (self.v_prod.get() or "").strip():
            return
        mov = {
            "Producto Código <F3>": self.v_prod.get().strip(),
            "Almacén Código <F3>":  self.v_alm.get().strip(),
            "Cantidad":             self.v_cant.get().strip(),
            "Precio Unitario":      self.v_prec.get().strip(),
            "IVA (%)":              self.v_iva.get().strip(),
            "Descuento 1 (%)":      self.v_d1.get().strip(),
        }
        values = []
        by_field = {h: v for h, v in mov.items()}
        for _fid, header, _w in GRID_COLUMNS:
            values.append(by_field.get(header, ""))
        self.grid.append_row(values)
        self.grid.autosize()
        self.v_cant.set("1"); self.v_prec.set("0"); self.v_d1.set("0")

    def _rows_from_grid(self):
        out=[]
        for iid in self.grid.tree.get_children(""):
            rec={}
            for f,h,_ in GRID_COLUMNS:
                rec[h]=self.grid.tree.set(iid,f)
            out.append(rec)
        return out

    def _crear(self, simular: bool):
        rows = self._rows_from_grid() or [{}]
        enc = rows[0]
        enc["Concepto Código <F3>"] = self.v_conc.get().strip()
        enc["Fecha (dd/mm/aaaa)"]   = self.v_fecha.get().strip()
        enc["Serie"]                = self.v_serie.get().strip()
        enc["Folio"]                = self.v_folio.get().strip()
        enc["Cliente Código <F3>"]  = self.v_cte.get().strip()
        enc["Moneda Id <F3>"]       = self.v_moneda.get().strip()
        enc["Tipo de Cambio"]       = self.v_tc.get().strip()
        enc["Agente Código <F3>"]   = self.v_agente.get().strip()

        try:
            loader = FacturaLoader(self.sdk, tolerant=True, logger=self._log)
            loader.crear_desde_tabla(
                headers=[h for _,h,_ in GRID_COLUMNS],
                rows=rows,
                usar_primer_renglon_para_encabezado=True,
                simular=simular
            )
            self._log(f"Documento {'simulado' if simular else 'creado'}")
        except Exception as e:
            self._log(f"Error al crear: {e}")
            messagebox.showerror("Crear", str(e))

# Compat export
try:
    Workbench
except NameError:
    WorkbenchApp = Workbench

__all__ = ["WorkbenchApp"]
