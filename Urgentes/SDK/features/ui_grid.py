import tkinter as tk
from tkinter import ttk

CATALOG_KIND_BY_COLUMN = {
    "Concepto Código <F3>": "concepto",
    "Serie": "serie",
    "Cliente Código <F3>": "cliente",
    "Producto Código <F3>": "producto",
    "Agente Código <F3>": "agente",
    "Almacén Código <F3>": "almacen",
    "Moneda Id <F3>": "moneda",
}

class EditableGrid(ttk.Treeview):

    def __init__(self, master, columns, height=18):
        super().__init__(master, columns=columns, show="headings", height=height)
        self._editor: tk.Entry | None = None
        self._popup: tk.Toplevel | None = None
        self._catalogs_getter = None
        self._last_col = "#1"

        # Scrollbars + GRID
        self._xscroll = tk.Scrollbar(master, orient="horizontal", command=self.xview)
        self._yscroll = tk.Scrollbar(master, orient="vertical", command=self.yview)
        self.configure(xscrollcommand=self._xscroll.set, yscrollcommand=self._yscroll.set)
        self.grid(row=0, column=0, sticky="nsew")
        self._xscroll.grid(row=1, column=0, sticky="ew")
        self._yscroll.grid(row=0, column=1, sticky="ns")
        master.rowconfigure(0, weight=1); master.columnconfigure(0, weight=1)

        # Columnas
        for col in columns:
            self.heading(col, text=col)
            w = 190 if ("Código" in col or "Observaciones" in col or "Texto" in col) else 130
            self.column(col, width=w, anchor="w")

        # Eventos (fluido, sin doble clic)
        self.bind("<Button-1>", self._on_click_edit, add="+")
        self.bind("<Key>", self._type_to_edit, add="+")
        for seq, fn in [("<Return>", self._enter_down),
                        ("<Tab>", self._tab_right),
                        ("<Shift-Tab>", self._tab_left),
                        ("<Up>", self._arrow_up),
                        ("<Down>", self._arrow_down),
                        ("<Left>", self._arrow_left),
                        ("<Right>", self._arrow_right)]:
            self.bind(seq, fn, add="+")
        self.bind("<<TreeviewSelect>>", self._on_select, add="+")
        self.bind("<Delete>", lambda e: self.delete_selected())

    # ---------- API pública ----------
    def enable_catalogs(self, catalogs_getter):
        self._catalogs_getter = catalogs_getter

    def add_row(self, values=None):
        vals = values or [""] * len(self["columns"])
        self.insert("", tk.END, values=vals)

    def delete_selected(self):
        self._commit_editor()
        for it in self.selection():
            self.delete(it)

    def clear_sheet(self):
        self._commit_editor()
        for it in self.get_children():
            self.delete(it)

    def paste_from_clipboard(self):
        self._commit_editor()
        try:
            raw = self.clipboard_get()
        except Exception:
            raw = ""
        if not raw.strip():
            return
        lines = [l for l in raw.replace("\r","").split("\n") if l.strip()]
        sep = "\t" if ("\t" in lines[0]) else ","
        first = [h.strip() for h in lines[0].split(sep)]
        has_headers = (first == list(self["columns"]))
        start = 1 if has_headers else 0
        for ln in lines[start:]:
            parts = [p.strip() for p in ln.split(sep)]
            row = [(parts[i] if i < len(self["columns"]) else "") for i in range(len(self["columns"]))]
            self.add_row(row)

    def get_headers_and_rows(self):
        self._commit_editor()
        headers = list(self["columns"])
        rows = []
        for it in self.get_children():
            vals = self.item(it, "values")
            row = { headers[i]: (vals[i] if i < len(vals) else "") for i in range(len(headers)) }
            if any((row[h] or "").strip() for h in headers):
                rows.append(row)
        return headers, rows

    # ---------- edición ----------
    def _on_click_edit(self, event):
        if self.identify("region", event.x, event.y) != "cell":
            return
        row = self.identify_row(event.y)
        col = self.identify_column(event.x)
        if not row or not col:
            return
        self.selection_set(row)
        self.focus(row)
        self._last_col = col
        self.after(1, lambda r=row, c=col: self._start_editor(r, c))

    def _on_select(self, _event=None):
        self._commit_editor()
        row, col = self._current_row_col(default_col=self._last_col)
        if row and col:
            self.after(1, lambda r=row, c=col: self._start_editor(r, c))

    def _current_row_col(self, default_col="#1"):
        sel = self.selection()
        if not sel:
            children = self.get_children()
            if not children:
                return None, None
            self.selection_set(children[0]); sel = self.selection()
        row = sel[0]
        px = self.winfo_pointerx() - self.winfo_rootx()
        col = self.identify_column(px) or default_col
        return row, col

    def _start_editor(self, row_id, col_id, preset_text=None):
        self._commit_editor()
        self._last_col = col_id
        bbox = self.bbox(row_id, col_id)
        if not bbox:
            self.see(row_id)
            self.after(10, lambda: self._start_editor(row_id, col_id, preset_text))
            return
        x, y, w, h = bbox
        value = self.set(row_id, col_id)

        self._editor = tk.Entry(self)
        self._editor.insert(0, preset_text if preset_text is not None else value)
        if preset_text:
            self._editor.icursor(len(preset_text))
        else:
            self._editor.select_range(0, tk.END)
        self._editor.place(x=x, y=y, width=w, height=h)
        self._editor.focus()

        # Navegación/guardado
        self._editor.bind("<Return>",    lambda e: self._save_and_move(row_id, col_id, down=True))
        self._editor.bind("<Tab>",       lambda e: self._save_and_move(row_id, col_id, next_cell=True))
        self._editor.bind("<Shift-Tab>", lambda e: self._save_and_move(row_id, col_id, prev_cell=True))
        self._editor.bind("<Escape>",    lambda e: self._cancel_editor())
        # CORRECCIÓN: no cerrar si el foco va al popup
        self._editor.bind("<FocusOut>",  lambda e: self._on_editor_focus_out())

        # F3/autocomplete
        heading = self.heading(col_id)['text']
        kind = CATALOG_KIND_BY_COLUMN.get(heading)
        if kind and self._catalogs_getter:
            self._editor.bind("<KeyRelease>", lambda e: self._maybe_popup(kind))
            self._editor.bind("<F3>",         lambda e: self._maybe_popup(kind, force=True))
        else:
            self._close_popup()

    def _on_editor_focus_out(self):
        """Si el foco se va a un widget dentro del popup, NO cierres el editor."""
        try:
            w = self.focus_get()
            if self._popup and w and (w.winfo_toplevel() is self._popup):
                return
        except Exception:
            pass
        self._commit_editor()

    def _commit_editor(self):
        if not self._editor:
            return
        cur = self.focus()
        col = self._last_col
        if cur and col:
            try:
                self.set(cur, col, self._editor.get())
            except Exception:
                pass
        self._close_popup()
        self._editor.destroy()
        self._editor = None

    def _cancel_editor(self):
        self._close_popup()
        if self._editor:
            self._editor.destroy()
            self._editor = None

    def _save_and_move(self, item, column, down=False, next_cell=False, prev_cell=False):
        self._commit_editor()
        cols = list(self["columns"]); col_idx = cols.index(column[1:])
        rows = list(self.get_children()); row_idx = rows.index(item)

        if next_cell:
            new_col_idx = col_idx + 1
            if new_col_idx < len(cols):
                self._start_editor(item, f"#{new_col_idx+1}")
            else:
                next_row = rows[row_idx+1] if row_idx+1 < len(rows) else item
                self._start_editor(next_row, "#1")
            return "break"
        if prev_cell:
            new_col_idx = col_idx - 1
            if new_col_idx >= 0:
                self._start_editor(item, f"#{new_col_idx+1}")
            else:
                prev_row = rows[row_idx-1] if row_idx-1 >= 0 else item
                self._start_editor(prev_row, f"#{len(cols)}")
            return "break"
        if down:
            next_row = rows[row_idx+1] if row_idx+1 < len(rows) else item
            self._start_editor(next_row, column)
            return "break"

    # ---------- navegación desde el Tree ----------
    def _enter_down(self, _e):
        row, col = self._current_row_col(default_col=self._last_col)
        if row and col:
            return self._save_and_move(row, col, down=True)

    def _tab_right(self, _e):
        row, col = self._current_row_col(default_col=self._last_col)
        if row and col:
            return self._save_and_move(row, col, next_cell=True)

    def _tab_left(self, _e):
        row, col = self._current_row_col(default_col=self._last_col)
        if row and col:
            return self._save_and_move(row, col, prev_cell=True)

    def _arrow_move(self, drow: int, dcol: int):
        self._commit_editor()
        rows = list(self.get_children())
        if not rows:
            return
        cur = self.focus() or rows[0]
        cols = list(self["columns"])
        col_idx = int(self._last_col[1:]) - 1
        new_row_idx = max(0, min(len(rows)-1, rows.index(cur) + drow))
        new_col_idx = max(0, min(len(cols)-1, col_idx + dcol))
        self.selection_set(rows[new_row_idx]); self.focus(rows[new_row_idx])
        self._last_col = f"#{new_col_idx+1}"
        self._start_editor(rows[new_row_idx], self._last_col)

    def _arrow_up(self, e):    self._arrow_move(-1, 0); return "break"
    def _arrow_down(self, e):  self._arrow_move(+1, 0); return "break"
    def _arrow_left(self, e):  self._arrow_move(0, -1); return "break"
    def _arrow_right(self, e): self._arrow_move(0, +1); return "break"

    # ---------- Edición al teclear ----------
    def _type_to_edit(self, event):
        if not event.char or len(event.char) != 1 or ord(event.char) < 32:
            return
        if not self._editor:
            row, col = self._current_row_col(default_col=self._last_col)
            if row and col:
                self._start_editor(row, col, preset_text=event.char)

    # ---------- Popup F3 / autocomplete ----------
    def _maybe_popup(self, kind: str, force=False):
        if not self._editor or not self._catalogs_getter:
            return
        catalogs = self._catalogs_getter()
        items = catalogs.get(kind) if catalogs else []
        q = self._editor.get().strip().lower()
        res = []
        for it in items or []:
            if not q and not force:
                continue
            if not q and force:
                res.append(it)
            else:
                if q in (it.get("codigo","").lower()) or q in (it.get("nombre","").lower()):
                    res.append(it)
            if len(res) >= 60:
                break
        if not res:
            self._close_popup(); return

        x = self._editor.winfo_x()
        y = self._editor.winfo_y() + self._editor.winfo_height()
        w = self._editor.winfo_width()
        if self._popup:
            self._popup.destroy()
        self._popup = tk.Toplevel(self)
        self._popup.wm_overrideredirect(True)
        self._popup.wm_geometry(f"{w}x220+{self.winfo_rootx()+x}+{self.winfo_rooty()+y}")

        lb = tk.Listbox(self._popup)
        for it in res:
            lb.insert(tk.END, f"{it.get('codigo','')}  —  {it.get('nombre','')}")
        lb.pack(fill=tk.BOTH, expand=True)
        # CORRECCIÓN: NO hacer focus_set() para que el Entry siga con el foco
        lb.bind("<Return>",    lambda e, lb=lb: self._pick(lb))
        lb.bind("<Double-1>",  lambda e, lb=lb: self._pick(lb))
        lb.bind("<Escape>",    lambda e: self._close_popup())

    def _pick(self, lb):
        sel = lb.curselection()
        if not sel:
            self._close_popup(); return
        code = lb.get(sel[0]).split("  —  ", 1)[0].strip()
        self._editor.delete(0, tk.END)
        self._editor.insert(0, code)
        self._close_popup()

    def _close_popup(self):
        if self._popup:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
