# features/ui_grid.py
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

GRID_COLUMNS = [
    ("cCodConcepto", "Concepto Código <F3>", 160),
    ("cCodProyecto", "Proyecto Codigo <F3>", 150),
    ("cFecha", "Fecha", 95),
    ("cSerie", "Serie", 70),
    ("cFolio", "Folio", 70),
    ("cCodCteProv", "Cliente Código <F3>", 160),
    ("cIdMoneda", "Moneda Id <F3>", 120),
    ("cTipoCambio", "Tipo de Cambio", 120),
    ("cCodAgente", "Agente Código <F3>", 150),
    ("cCodProducto", "Producto Código <F3>", 180),
    ("cCodAlmacen", "Almacén Código <F3>", 150),
    ("cUnidades", "Cantidad", 90),
    ("cPrecio", "Precio Unitario", 120),
    ("cDesc1", "Descuento 1 (%)", 120),
    ("cDesc2", "Descuento 2 (%)", 120),
    ("cDesc3", "Descuento 3 (%)", 120),
    ("cIVA", "IVA (%)", 90),
]

LOOKUP_FIELDS = {
    "cCodConcepto","cCodProyecto","cSerie","cCodCteProv","cIdMoneda",
    "cCodAgente","cCodProducto","cCodAlmacen"
}

class _Dropdown(ttk.Frame):
    """Dropdown flotante anclado a la celda con filtro incremental."""
    def __init__(self, master, items, on_pick):
        super().__init__(master, borderwidth=1, relief="solid")
        self.on_pick = on_pick
        self._all = items[:]
        self._filtered = []
        self.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(self)
        self.entry.grid(row=0, column=0, sticky="ew", padx=4, pady=(4,2))
        self.list = tk.Listbox(self, height=8, activestyle="dotbox")
        self.list.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0,4))
        self.rowconfigure(1, weight=1)

        self.entry.bind("<KeyRelease>", lambda e: self._apply(self.entry.get()))
        self.entry.bind("<Down>", lambda e: (self.list.focus_set(), "break"))
        self.entry.bind("<Escape>", lambda e: self._close())
        self.entry.bind("<Return>", lambda e: self._accept())
        self.list.bind("<Return>", lambda e: self._accept())
        self.list.bind("<Double-1>", lambda e: self._accept())
        self.list.bind("<Escape>", lambda e: self._close())
        self.bind("<FocusOut>", lambda e: self.after(50, self._close))

        self._apply("")
        self.entry.focus_set()

    def _apply(self, q):
        q=(q or "").lower().strip()
        if not q:
            self._filtered = self._all[:200]
        else:
            self._filtered = [
                x for x in self._all
                if q in (x.get("codigo","").lower()) or q in (x.get("nombre","").lower())
            ][:200]
        self.list.delete(0, tk.END)
        for it in self._filtered:
            self.list.insert(tk.END, f"{it.get('codigo','')} — {it.get('nombre','')}")
        if self._filtered:
            self.list.selection_set(0); self.list.see(0)

    def _accept(self):
        idx=self.list.curselection()
        if not idx or not self._filtered:
            self._close(); return
        code=self._filtered[idx[0]].get("codigo","")
        self.on_pick(code)
        self._close()

    def _close(self):
        try: self.destroy()
        except Exception: pass

class InvoiceGrid(ttk.Frame):
    """Grid estilo Excel: edición en vivo, crucetas/Tab/Enter, F3/Alt+↓ desplegable."""
    def __init__(self, master, on_lookup_f3=None, on_commit_cell=None, show_filters=False, get_items=None):
        super().__init__(master)
        self.on_lookup_f3 = on_lookup_f3
        self.on_commit_cell = on_commit_cell
        self.get_items = get_items
        self._data=[]
        self._editor=None; self._col=None; self._iid=None; self._dd=None
        self._build()
        self._bind()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, columns=[k for k,_,_ in GRID_COLUMNS],
                                 show="headings", selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        for key, text, width in GRID_COLUMNS:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="w")
        vsb=ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb=ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        vsb.grid(row=0, column=1, sticky="ns", pady=6)
        hsb.grid(row=1, column=0, sticky="ew", padx=6, pady=(0,6))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    # ------ datos ------
    def set_rows(self, rows): self._data=[dict(r) for r in rows]; self._paint()
    def get_rows(self): self._sync(); return [dict(r) for r in self._data]
    def get_row_cached(self, i): return dict(self._data[i]) if 0<=i<len(self._data) else {}

    def add_row(self, defaults=None):
        self._sync()
        r={k:"" for k,_,_ in GRID_COLUMNS}
        if defaults: r.update(defaults)
        self._data.append(r); self._insert(len(self._data)-1, r, select=True)
        self._start_edit_current()

    def delete_row(self):
        sel=self.tree.selection()
        if not sel: return
        i=self.tree.index(sel[0])
        self._data.pop(i); self.tree.delete(sel[0])

    # ------ pintado ------
    def _paint(self):
        self.tree.delete(*self.tree.get_children())
        for i,r in enumerate(self._data): self._insert(i,r)

    def _insert(self, i, r, select=False):
        vals=[r.get(k,"") for k,_,_ in GRID_COLUMNS]
        iid=self.tree.insert("", "end", values=vals)
        if select: self.tree.selection_set(iid); self.tree.focus(iid); self.tree.see(iid)

    # ------ edición / navegación ------
    def _bind(self):
        tv=self.tree
        tv.bind("<Button-1>", self._click)
        tv.bind("<Double-1>", self._click)
        tv.bind("<Key>", self._type_edit, add="+")
        for k in ("<Return>","<KP_Enter>","<Tab>","<Shift-Tab>","<Up>","<Down>","<Left>","<Right>"):
            tv.bind(k, self._nav)
        tv.bind("<F3>", self._open_dropdown)
        tv.bind("<Alt-Down>", self._open_dropdown)
        tv.bind("<Control-v>", lambda e: self.paste_clipboard())
        tv.bind("<Control-V>", lambda e: self.paste_clipboard())

    def paste_clipboard(self):
        self._sync()
        try: raw=self.clipboard_get()
        except Exception: return
        raw=raw.replace("\r","")
        lines=[l for l in raw.split("\n") if l.strip()]
        if not lines: return
        sep="\t" if "\t" in lines[0] else ","
        start_col=(self._current_col() or 1)-1
        for ln in lines:
            parts=[p.strip() for p in ln.split(sep)]
            row={k:"" for k,_,_ in GRID_COLUMNS}
            for i,(k,_,_) in enumerate(GRID_COLUMNS):
                src=start_col+i
                if src<len(parts): row[k]=parts[src]
            self._data.append(row)
        self._paint()

    def _click(self, e):
        self.tree.focus_set()
        if self.tree.identify("region", e.x, e.y)!="cell": return
        r=self.tree.identify_row(e.y); c=self.tree.identify_column(e.x)
        if not r: return
        self.tree.selection_set(r); self.tree.focus(r)
        self._start_editor(r, c)

    def _type_edit(self, e):
        if e.keysym in ("Shift_L","Shift_R","Control_L","Control_R","Alt_L","Alt_R"): return
        if self._editor is None:
            self._start_edit_current()
            if self._editor is not None and len(e.char)==1 and e.char.isprintable():
                self._editor.delete(0,"end"); self._editor.insert(0,e.char); self._editor.icursor("end")

    def _nav(self, e):
        # navegación tipo Excel (siempre rompemos el manejo por defecto)
        if e.keysym in ("Return","KP_Enter","Tab"):
            self._move_col(1);  return "break"
        if e.keysym == "Left":
            self._move_col(-1); return "break"
        if e.keysym == "Right":
            self._move_col(1);  return "break"
        if e.keysym == "Up":
            self._move_row(-1); return "break"
        if e.keysym == "Down":
            self._move_row(1);  return "break"
        # Shift+Tab
        if e.keysym == "Tab" and (e.state & 0x0001):
            self._move_col(-1); return "break"

    def _move_col(self, d):
        self._sync()
        sel=self.tree.selection()
        if not sel:
            ch=self.tree.get_children()
            if not ch: return
            self.tree.selection_set(ch[0]); self.tree.focus(ch[0]); self._start_edit_current(); return
        iid=sel[0]; col=self._current_col() or 1
        col=max(1, min(len(GRID_COLUMNS), col+d))
        self._start_editor(iid, f"#{col}")

    def _move_row(self, d):
        self._sync()
        sel=self.tree.selection()
        if not sel:
            ch=self.tree.get_children()
            if not ch: return
            self.tree.selection_set(ch[0]); self.tree.focus(ch[0]); self._start_edit_current(); return
        iid=sel[0]; i=self.tree.index(iid)+d
        i=max(0, min(len(self.tree.get_children())-1, i))
        tgt=self.tree.get_children()[i]
        col=self._current_col() or 1
        self.tree.selection_set(tgt); self.tree.focus(tgt); self.tree.see(tgt)
        self._start_editor(tgt, f"#{col}")

    def _start_edit_current(self):
        sel=self.tree.selection()
        if not sel:
            self.add_row(); return
        self._start_editor(sel[0], f"#{self._current_col() or 1}")

    def _start_editor(self, iid, colid):
        self._close_dropdown()
        self._destroy_editor()
        bbox=self.tree.bbox(iid,colid)
        if not bbox: return
        x,y,w,h=bbox
        ci=int(colid.replace("#",""))
        field=GRID_COLUMNS[ci-1][0]
        val=self.tree.set(iid, field)

        ed=ttk.Entry(self.tree); ed.insert(0,val)
        ed.place(x=x,y=y,width=w,height=h)
        ed.focus_set(); ed.icursor("end")

        # edición en vivo
        ed.bind("<KeyRelease>", lambda e: self._live(field))

        # cerrar editor sin perder cambios
        ed.bind("<Escape>", lambda e: self._destroy_editor())
        ed.bind("<FocusOut>", lambda e: self._destroy_editor())

        # mover DIRECTO (sin event_generate)
        ed.bind("<Return>",    lambda e: (self._destroy_editor(), self._move_col(1)))
        ed.bind("<KP_Enter>",  lambda e: (self._destroy_editor(), self._move_col(1)))
        ed.bind("<Tab>",       lambda e: (self._destroy_editor(), self._move_col(1)))
        ed.bind("<Shift-Tab>", lambda e: (self._destroy_editor(), self._move_col(-1)))
        ed.bind("<Left>",      lambda e: (self._destroy_editor(), self._move_col(-1)))
        ed.bind("<Right>",     lambda e: (self._destroy_editor(), self._move_col(1)))
        ed.bind("<Up>",        lambda e: (self._destroy_editor(), self._move_row(-1)))
        ed.bind("<Down>",      lambda e: (self._destroy_editor(), self._move_row(1)))

        # F3 / Alt+↓ -> lista
        ed.bind("<F3>",        self._open_dropdown)
        ed.bind("<Alt-Down>",  self._open_dropdown)

        self._editor=ed; self._col=ci; self._iid=iid
        self._live(field)

    def _live(self, field):
        if not self._editor: return
        v=self._editor.get()
        self.tree.set(self._iid, field, v)
        idx=self.tree.index(self._iid)
        self._data[idx][field]=v
        if self.on_commit_cell:
            self.on_commit_cell(idx, field, v)

    def _current_col(self): return self._col or 1

    def _destroy_editor(self):
        if self._editor is not None:
            try: self._editor.destroy()
            except Exception: pass
            self._editor=None; self._col=None; self._iid=None

    def _sync(self):
        # edición ya es en vivo
        pass

    # ------ dropdown ------
    def _open_dropdown(self, _e=None):
        if not self._editor:
            self._start_edit_current()
        if not self._editor: return "break"
        field = GRID_COLUMNS[self._col-1][0]
        if field not in LOOKUP_FIELDS:
            return "break"

        items = []
        if callable(self.get_items):
            try: items = self.get_items(field) or []
            except Exception: items=[]
        self._close_dropdown()

        x,y,w,h=self.tree.bbox(self._iid, f"#{self._col}")
        ax=self.tree.winfo_rootx()+x
        ay=self.tree.winfo_rooty()+y+h
        self._dd = _Dropdown(self, items, on_pick=lambda code: self._pick_from_dropdown(field, code))
        self._dd.place(x=ax - self.winfo_rootx(), y=ay - self.winfo_rooty(), width=max(w,260))
        return "break"

    def _pick_from_dropdown(self, field, code):
        if not self._editor: return
        self._editor.delete(0,"end"); self._editor.insert(0,code)
        self._live(field)

    def _close_dropdown(self):
        if self._dd is not None:
            try: self._dd.destroy()
            except Exception: pass
            self._dd=None

    # util
    def autosize_columns(self, min_w=80, max_w=260):
        import tkinter.font as tkfont
        f=tkfont.nametofont("TkDefaultFont")
        widths={k:max(min_w,min(max_w,f.measure(t)+24)) for k,t,_ in GRID_COLUMNS}
        for iid in self.tree.get_children():
            for k,_,_ in GRID_COLUMNS:
                txt=self.tree.set(iid,k) or ""
                widths[k]=max(widths[k], min(max_w, f.measure(str(txt))+24))
        for k,_,_ in GRID_COLUMNS: self.tree.column(k,width=widths[k])
