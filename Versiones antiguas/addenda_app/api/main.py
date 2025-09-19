import os
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from xml.etree import ElementTree as ET
import subprocess
import sys

DB_NAME = "addenda.db"


# ==================== Base de Datos ====================

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            proveedor TEXT,
            orden_compra TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS addendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            tipo_addenda TEXT,
            archivo_xml TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")


def add_cliente(nombre, proveedor, orden):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO clientes(nombre, proveedor, orden_compra)
            VALUES (?, ?, ?)""", (nombre, proveedor, orden))
        conn.commit()


def list_clientes():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT nombre, proveedor, orden_compra FROM clientes")
        return c.fetchall()


def registrar_addenda(cliente, tipo, archivo_xml):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO addendas(cliente, tipo_addenda, archivo_xml) VALUES (?, ?, ?)",
            (cliente, tipo, archivo_xml),
        )
        conn.commit()


def list_addendas():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT cliente, tipo_addenda, archivo_xml, fecha FROM addendas ORDER BY fecha DESC"
        )
        return c.fetchall()


# ==================== Lógica de XML ====================

def integrar_addenda(cfdi_path, addenda_data):
    """
    Inserta o crea el nodo <Addenda> con datos de Soriana Reverse.
    """
    tree = ET.parse(cfdi_path)
    root = tree.getroot()

    # Busca el nodo Addenda o créalo
    addenda_node = root.find("{*}Addenda")
    if addenda_node is None:
        addenda_node = ET.SubElement(root, "Addenda")

    # Nodo SorianaReverse
    soriana = ET.SubElement(addenda_node, "SorianaReverse")
    for k, v in addenda_data.items():
        ET.SubElement(soriana, k).text = v

    # Guardar
    base, ext = os.path.splitext(cfdi_path)
    out_path = base + "_con_addenda.xml"
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return out_path


# ==================== Interfaz ====================

class AddendaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Generador de Addenda")
        self.geometry("900x600")
        self.create_widgets()
        self.refresh_client_table()
        self.refresh_client_combo()
        self.refresh_addenda_table()

    def create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        # ---- Selección de cliente existente ----
        ttk.Label(frame, text="Cliente existente:").grid(row=0, column=0, sticky="e")
        self.clientes_var = tk.StringVar()
        self.combo_clientes = ttk.Combobox(frame, textvariable=self.clientes_var,
                                           state="readonly", width=30)
        self.combo_clientes.grid(row=0, column=1, sticky="w")
        self.combo_clientes.bind("<<ComboboxSelected>>", self.on_cliente_combo)

        # ---- Alta de nuevo cliente ----
        ttk.Label(frame, text="Cliente (nuevo):").grid(row=1, column=0, sticky="e")
        self.entry_cliente = ttk.Entry(frame, width=30)
        self.entry_cliente.grid(row=1, column=1, sticky="w")

        ttk.Label(frame, text="Proveedor:").grid(row=2, column=0, sticky="e")
        self.entry_proveedor = ttk.Entry(frame, width=30)
        self.entry_proveedor.grid(row=2, column=1, sticky="w")

        ttk.Label(frame, text="Orden de compra:").grid(row=3, column=0, sticky="e")
        self.entry_orden = ttk.Entry(frame, width=30)
        self.entry_orden.grid(row=3, column=1, sticky="w")

        ttk.Button(frame, text="Agregar cliente", command=self.add_cliente).grid(row=4, column=1, pady=5, sticky="w")

        # ---- Tipo de addenda ----
        ttk.Label(frame, text="Tipo Addenda:").grid(row=5, column=0, sticky="e")
        self.addenda_tipo = tk.StringVar(value="Soriana Reverse")
        ttk.Combobox(frame, textvariable=self.addenda_tipo,
                     values=["Soriana Reverse", "Soriana", "Walmart"],
                     state="readonly", width=28).grid(row=5, column=1, sticky="w")

        # ---- CFDI ----
        ttk.Button(frame, text="Seleccionar CFDI", command=self.seleccionar_cfdi).grid(row=6, column=1, pady=5, sticky="w")
        self.cfdi_path = None

        # ---- Datos específicos Soriana Reverse ----
        sep = ttk.LabelFrame(self, text="Datos Soriana Reverse", padding=10)
        sep.pack(fill="x", padx=10, pady=10)

        ttk.Label(sep, text="NoProveedor:").grid(row=0, column=0, sticky="e")
        self.no_proveedor = ttk.Entry(sep, width=30)
        self.no_proveedor.grid(row=0, column=1, sticky="w")

        ttk.Label(sep, text="OrdenCompra:").grid(row=1, column=0, sticky="e")
        self.orden_compra = ttk.Entry(sep, width=30)
        self.orden_compra.grid(row=1, column=1, sticky="w")

        # ---- Botón generar ----
        ttk.Button(self, text="Generar Addenda", command=self.generar_addenda).pack(pady=10)

        # ---- Tabla de clientes ----
        ttk.Label(self, text="Clientes registrados:").pack()
        self.table_clientes = ttk.Treeview(self, columns=("Nombre", "Proveedor", "Orden"), show="headings", height=4)
        for col in ("Nombre", "Proveedor", "Orden"):
            self.table_clientes.heading(col, text=col)
            self.table_clientes.column(col, width=150)
        self.table_clientes.pack(fill="x", padx=10, pady=5)

        # ---- Historial addendas ----
        ttk.Label(self, text="Historial de addendas generadas: (doble clic para abrir)").pack()
        self.table_addendas = ttk.Treeview(
            self,
            columns=("Cliente", "Tipo", "Archivo", "Fecha"),
            show="headings",
            height=6,
        )
        for col in ("Cliente", "Tipo", "Archivo", "Fecha"):
            self.table_addendas.heading(col, text=col)
            width = 200 if col == "Archivo" else 150
            self.table_addendas.column(col, width=width)
        self.table_addendas.pack(fill="both", expand=True, padx=10, pady=5)
        self.table_addendas.bind("<Double-1>", self.abrir_xml_seleccionado)

    # ---------- Funciones UI ----------
    def add_cliente(self):
        nombre = self.entry_cliente.get().strip()
        prov = self.entry_proveedor.get().strip()
        orden = self.entry_orden.get().strip()
        if not nombre:
            messagebox.showerror("Error", "El nombre del cliente es obligatorio.")
            return
        add_cliente(nombre, prov, orden)
        self.entry_cliente.delete(0, tk.END)
        self.entry_proveedor.delete(0, tk.END)
        self.entry_orden.delete(0, tk.END)
        self.refresh_client_table()
        self.refresh_client_combo()

    def seleccionar_cfdi(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar CFDI XML", filetypes=[("XML files", "*.xml")]
        )
        if file_path:
            self.cfdi_path = file_path
            messagebox.showinfo("CFDI seleccionado", f"Archivo: {os.path.basename(file_path)}")

    def generar_addenda(self):
        if not self.cfdi_path:
            messagebox.showerror("Error", "Debes seleccionar un CFDI.")
            return

        cliente_sel = self.clientes_var.get() or self.entry_cliente.get().strip()
        if not cliente_sel:
            messagebox.showerror("Error", "Debes seleccionar o dar de alta un cliente.")
            return

        addenda_info = {
            "NoProveedor": self.no_proveedor.get().strip(),
            "OrdenCompra": self.orden_compra.get().strip(),
        }
        if not all(addenda_info.values()):
            messagebox.showerror("Error", "Completa los datos de Soriana Reverse.")
            return

        out_file = integrar_addenda(self.cfdi_path, addenda_info)
        registrar_addenda(cliente_sel, self.addenda_tipo.get(), out_file)
        messagebox.showinfo("Éxito", f"Addenda generada en:\n{out_file}")

        self.refresh_addenda_table()

    def refresh_client_table(self):
        for row in self.table_clientes.get_children():
            self.table_clientes.delete(row)
        for r in list_clientes():
            self.table_clientes.insert("", tk.END, values=r)

    def refresh_client_combo(self):
        self.combo_clientes["values"] = [r[0] for r in list_clientes()]

    def refresh_addenda_table(self):
        for row in self.table_addendas.get_children():
            self.table_addendas.delete(row)
        for r in list_addendas():
            self.table_addendas.insert("", tk.END, values=r)

    def on_cliente_combo(self, event=None):
        nombre = self.clientes_var.get()
        for row in list_clientes():
            if row[0] == nombre:
                _, prov, orden = row
                self.entry_cliente.delete(0, tk.END)
                self.entry_cliente.insert(0, nombre)
                self.entry_proveedor.delete(0, tk.END)
                self.entry_proveedor.insert(0, prov)
                self.entry_orden.delete(0, tk.END)
                self.entry_orden.insert(0, orden)
                break

    def abrir_xml_seleccionado(self, event):
        item = self.table_addendas.focus()
        if not item:
            return
        archivo = self.table_addendas.item(item)["values"][2]
        if not os.path.exists(archivo):
            messagebox.showerror("Error", f"Archivo no encontrado:\n{archivo}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(archivo)  # Windows
            elif sys.platform.startswith("darwin"):
                subprocess.call(["open", archivo])  # Mac
            else:
                subprocess.call(["xdg-open", archivo])  # Linux
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")


# ==================== MAIN ====================

if __name__ == "__main__":
    init_db()
    app = AddendaApp()
    app.mainloop()
