# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

def select_code(parent, title: str, items: list[tuple[str, str]], current: str) -> str | None:
    """
    Muestra un diálogo simple (código, nombre).
    - items: lista de tuplas (codigo, nombre)
    - retorna código seleccionado o None
    """
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    win.geometry("640x420")

    code_var = tk.StringVar(value=current or "")

    top = ttk.Frame(win)
    top.pack(fill="x", padx=10, pady=8)

    ttk.Label(top, text="Buscar:").pack(side="left")
    ent = ttk.Entry(top, textvariable=code_var, width=28)
    ent.pack(side="left", padx=6)
    ent.focus_set()

    cols = ("codigo", "nombre")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
    tree.pack(fill="both", expand=True, padx=10, pady=(0,8))

    tree.heading("codigo", text="Código")
    tree.heading("nombre", text="Nombre")
    tree.column("codigo", width=160, anchor="w")
    tree.column("nombre", width=420, anchor="w")

    for c, n in items:
        tree.insert("", "end", values=(c, n))

    btns = ttk.Frame(win); btns.pack(fill="x", padx=10, pady=8)
    result = {"code": None}

    def do_filter(*_):
        q = (code_var.get() or "").strip().lower()
        for iid in tree.get_children(""):
            tree.delete(iid)
        for c, n in items:
            if not q or q in c.lower() or q in (n or "").lower():
                tree.insert("", "end", values=(c, n))

    def accept(*_):
        sel = tree.focus()
        if sel:
            vals = tree.item(sel, "values")
            result["code"] = vals[0]
        win.destroy()

    def cancel(*_):
        result["code"] = None
        win.destroy()

    ttk.Button(btns, text="Aceptar", command=accept).pack(side="right")
    ttk.Button(btns, text="Cancelar", command=cancel).pack(side="right", padx=(0,8))

    ent.bind("<KeyRelease>", do_filter)
    tree.bind("<Double-1>", accept)
    tree.bind("<Return>", accept)
    win.bind("<Escape>", cancel)

    win.wait_window()
    return result["code"]
