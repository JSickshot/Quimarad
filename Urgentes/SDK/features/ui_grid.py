# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

# Define tus columnas (mantengo las habituales)
GRID_COLUMNS = [
    ("cId",                 "Id <F3>",                 80),
    ("cTipoCambio",         "Tipo de Cambio",          110),
    ("cCodAgente",          "Agente Código <F3>",      140),
    ("cCodigoProducto",     "Producto Código <F3>",    180),
    ("cCodAlmacen",         "Almacén Código <F3>",     150),
    ("cCantidad",           "Cantidad",                 90),
    ("cPrecioUnitario",     "Precio Unitario",         110),
    ("cDesc1",              "Descuento 1 (%)",         120),
    ("cDesc2",              "Descuento 2 (%)",         120),
    ("cDesc3",              "Descuento 3 (%)",         120),
    ("cIva",                "IVA (%)",                  80),
    ("cDocumento",          "Documento",               120),
]

# Campos que soportan F3 desde la grilla
CAT_FIELDS = {"cCodigoProducto","cCodAlmacen","cCodAgente"}

class GridEditor(ttk.Frame):
    def __init__(self, master, on_change=None, on_dropdown=None, on_f3=None):
        super().__init__(master)
        self.on_change   = on_change
        self.on_dropdown = on_dropdown
        self.on_f3       = on_f3
        self._iid = None

        # Scrollbars
        self.tree = ttk.Treeview(self, columns=[f for f,_,_ in GRID_COLUMNS], show="headings", height=15)
        vs = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        for f, h, w in GRID_COLUMNS:
            self.tree.heading(f, text=h)
            self.tree.column(f, width=w, anchor="w")

        # Eventos
        self.tree.bind("<Double-1>", self._edit_cell)
        self.tree.bind("<Return>",   self._edit_cell)
        self.tree.bind("<Control-v>", self._paste_clipboard)

        # Context menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Insertar", command=lambda: self.append_row([]))
        self.menu.add_command(label="Duplicar", command=self.duplicate_selected)
        self.menu.add_command(label="Eliminar", command=self.delete_selected)
        self.tree.bind("<Button-3>", self._popup)

    # ---- helpers ----
    def _popup(self, event):
        try:
            self.tree.selection_set(self.tree.identify_row(event.y))
        except Exception:
            pass
        self.menu.tk_popup(event.x_root, event.y_root)

    def autosize(self):
        self.update_idletasks()

    def clear_all(self):
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)

    def append_row(self, values):
        # Rellena a longitud de columnas
        row = []
        for i, (f,h,w) in enumerate(GRID_COLUMNS):
            val = ""
            if isinstance(values, (list,tuple)):
                if i < len(values): val = values[i]
            elif isinstance(values, dict):
                val = values.get(h, "")
            row.append("" if val is None else str(val))
        iid = self.tree.insert("", "end", values=row)
        self.tree.see(iid)
        self.tree.selection_set(iid)

    def duplicate_selected(self):
        sel = self.tree.selection()
        if not sel: return
        for iid in sel:
            vals = [self.tree.set(iid, f) for f,_,_ in GRID_COLUMNS]
            self.append_row(vals)

    def delete_selected(self):
        sel = self.tree.selection()
        for iid in sel:
            self.tree.delete(iid)

    # ---- edición ----
    def _edit_cell(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return
        rowid = self.tree.identify_row(event.y)
        colid = self.tree.identify_column(event.x)
        if not rowid or not colid: return
        self._iid = rowid
        col_index = int(colid.replace("#","")) - 1
        col_field, col_header, _ = GRID_COLUMNS[col_index]
        x, y, w, h = self.tree.bbox(rowid, colid)
        value = self.tree.set(rowid, col_field)

        # Editor
        top = tk.Toplevel(self); top.overrideredirect(True)
        top.geometry(f"{w+2}x{h+2}+{self.winfo_rootx()+x}+{self.winfo_rooty()+y}")
        e = ttk.Entry(top); e.insert(0, value); e.select_range(0, "end"); e.focus()
        e.pack(fill="both", expand=True)

        def save(ev=None):
            val = e.get()
            self.tree.set(rowid, col_field, val)
            if self.on_change: 
                try: self.on_change(col_field, val)
                except Exception: pass
            top.destroy()

        def cancel(ev=None): top.destroy()

        def f3(ev=None):
            if self.on_f3 and (col_field in CAT_FIELDS):
                try:
                    code = self.on_f3(col_field)
                    if code:
                        self.tree.set(rowid, col_field, code)
                except Exception:
                    pass
            top.destroy()

        e.bind("<Return>", save)
        e.bind("<Escape>", cancel)
        e.bind("<F3>", f3)
        e.bind("<FocusOut>", lambda ev: save())

    # ---- pegado desde Excel/CSV ----
    def _paste_clipboard(self, event=None):
        try:
            data = self.clipboard_get()
        except Exception:
            return
        lines = [l for l in data.splitlines() if l.strip()]
        if not lines: return
        for line in lines:
            parts = line.split("\t")  # desde Excel
            self.append_row(parts)
