import os, sys, subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from database import (
    init_db, add_cliente, update_cliente,
    list_clientes, registrar_addenda, list_addendas
)
from xml_utils import integrar_addenda


class AddendaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Generador de Addenda")
        self.geometry("950x600")
        self.cfdi_path = None
        self.create_widgets()
        self.refresh_all()

    # -------- UI --------
    def create_widgets(self):
        f = ttk.Frame(self, padding=10)
        f.pack(fill="x")

        # Cliente existente
        ttk.Label(f, text="Cliente existente:").grid(row=0, column=0, sticky="e")
        self.clientes_var = tk.StringVar()
        self.combo_clientes = ttk.Combobox(f, textvariable=self.clientes_var,
                                           state="readonly", width=30)
        self.combo_clientes.grid(row=0, column=1, sticky="w")
        self.combo_clientes.bind("<<ComboboxSelected>>", self.on_cliente_combo)

        # Datos cliente
        ttk.Label(f, text="Nombre:").grid(row=1, column=0, sticky="e")
        self.entry_cliente = ttk.Entry(f, width=30); self.entry_cliente.grid(row=1, column=1)
        ttk.Label(f, text="Proveedor:").grid(row=2, column=0, sticky="e")
        self.entry_prov = ttk.Entry(f, width=30); self.entry_prov.grid(row=2, column=1)
        ttk.Label(f, text="Orden compra:").grid(row=3, column=0, sticky="e")
        self.entry_orden = ttk.Entry(f, width=30); self.entry_orden.grid(row=3, column=1)

        btn_frame = ttk.Frame(f); btn_frame.grid(row=4, column=1, sticky="w", pady=5)
        ttk.Button(btn_frame, text="Agregar", command=self.add_cliente).pack(side="left")
        ttk.Button(btn_frame, text="Actualizar", command=self.update_cliente).pack(side="left", padx=5)

        # Tipo Addenda
        ttk.Label(f, text="Tipo Addenda:").grid(row=5, column=0, sticky="e")
        self.tipo = tk.StringVar(value="Soriana Reverse")
        ttk.Combobox(f, textvariable=self.tipo,
                     values=["Soriana Reverse", "Soriana", "Walmart"],
                     state="readonly", width=28).grid(row=5, column=1, sticky="w")

        # CFDI
        ttk.Button(f, text="Seleccionar CFDI", command=self.select_cfdi).grid(row=6, column=1, sticky="w", pady=5)

        # Datos Soriana Reverse
        sf = ttk.LabelFrame(self, text="Datos Soriana Reverse", padding=10)
        sf.pack(fill="x", padx=10, pady=10)
        ttk.Label(sf, text="NoProveedor:").grid(row=0, column=0, sticky="e")
        self.no_prov = ttk.Entry(sf, width=30); self.no_prov.grid(row=0, column=1)
        ttk.Label(sf, text="OrdenCompra:").grid(row=1, column=0, sticky="e")
        self.orden_compra = ttk.Entry(sf, width=30); self.orden_compra.grid(row=1, column=1)

        ttk.Button(self, text="Generar Addenda", command=self.generar_addenda).pack(pady=10)

        # Tabla clientes
        ttk.Label(self, text="Clientes registrados:").pack()
        self.table_clientes = ttk.Treeview(self, columns=("Nombre","Proveedor","Orden"), show="headings", height=4)
        for c in ("Nombre","Proveedor","Orden"):
            self.table_clientes.heading(c, text=c); self.table_clientes.column(c, width=150)
        self.table_clientes.pack(fill="x", padx=10, pady=5)

        # Historial
        ttk.Label(self, text="Historial de addendas (doble clic abre XML):").pack()
        self.table_add = ttk.Treeview(self, columns=("Cliente","Tipo","Archivo","Fecha"), show="headings", height=6)
        for c in ("Cliente","Tipo","Archivo","Fecha"):
            w=200 if c=="Archivo" else 150
            self.table_add.heading(c, text=c); self.table_add.column(c, width=w)
        self.table_add.pack(fill="both", expand=True, padx=10, pady=5)
        self.table_add.bind("<Double-1>", self.open_xml)

    # -------- Lógica --------
    def refresh_all(self):
        self.refresh_clients()
        self.refresh_addendas()

    def refresh_clients(self):
        for i in self.table_clientes.get_children(): self.table_clientes.delete(i)
        for r in list_clientes():
            self.table_clientes.insert("", "end", values=r)
        self.combo_clientes["values"] = [r[0] for r in list_clientes()]

    def refresh_addendas(self):
        for i in self.table_add.get_children(): self.table_add.delete(i)
        for r in list_addendas():
            self.table_add.insert("", "end", values=r)

    def add_cliente(self):
        if not self.entry_cliente.get().strip():
            messagebox.showerror("Error", "Nombre obligatorio"); return
        add_cliente(self.entry_cliente.get().strip(),
                    self.entry_prov.get().strip(),
                    self.entry_orden.get().strip())
        self.refresh_clients()

    def update_cliente(self):
        if not self.entry_cliente.get().strip():
            messagebox.showerror("Error", "Selecciona o escribe cliente"); return
        update_cliente(self.entry_cliente.get().strip(),
                       self.entry_prov.get().strip(),
                       self.entry_orden.get().strip())
        messagebox.showinfo("OK", "Cliente actualizado")
        self.refresh_clients()

    def on_cliente_combo(self, e=None):
        nombre = self.clientes_var.get()
        for n,p,o in list_clientes():
            if n==nombre:
                self.entry_cliente.delete(0, tk.END); self.entry_cliente.insert(0,n)
                self.entry_prov.delete(0, tk.END); self.entry_prov.insert(0,p)
                self.entry_orden.delete(0, tk.END); self.entry_orden.insert(0,o)
                break

    def select_cfdi(self):
        f = filedialog.askopenfilename(title="Seleccionar CFDI XML", filetypes=[("XML","*.xml")])
        if f: self.cfdi_path = f

    def generar_addenda(self):
        if not self.cfdi_path:
            messagebox.showerror("Error","Selecciona un CFDI"); return
        cliente = self.entry_cliente.get().strip()
        if not cliente:
            messagebox.showerror("Error","Cliente requerido"); return
        datos = {"NoProveedor": self.no_prov.get().strip(),
                 "OrdenCompra": self.orden_compra.get().strip()}
        if not all(datos.values()):
            messagebox.showerror("Error","Completa datos Soriana Reverse"); return
        out = integrar_addenda(self.cfdi_path, datos)
        registrar_addenda(cliente, self.tipo.get(), out)
        messagebox.showinfo("OK", f"Addenda generada:\n{out}")
        self.refresh_addendas()

    def open_xml(self, e=None):
        item = self.table_add.focus()
        if not item: return
        path = self.table_add.item(item)["values"][2]
        if not os.path.exists(path):
            messagebox.showerror("Error","Archivo no encontrado"); return
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform.startswith("darwin"):
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])


if __name__ == "__main__":
    from database import init_db
    init_db()
    AddendaApp().mainloop()
