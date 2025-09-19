import tkinter as tk
from tkinter import filedialog, messagebox
from db import init_db, guardar_cliente, obtener_clientes
from cfdi_reader import obtener_datos_basicos
from xml_writer import insertar_addenda
from addendas import generica, walmart
import os

init_db()

def generar():
    archivo = filedialog.askopenfilename(title="Selecciona CFDI XML",
                                         filetypes=[("XML files","*.xml")])
    if not archivo:
        return

    datos_cfdi = obtener_datos_basicos(archivo)
    nombre = entry_nombre.get()
    proveedor = entry_proveedor.get()
    orden = entry_orden.get()
    tipo = tipo_var.get()

    if not all([nombre, proveedor, orden]):
        messagebox.showerror("Error", "Completa todos los campos")
        return


    guardar_cliente(nombre, proveedor, orden)

    datos_addenda = {"proveedor": proveedor, "orden": orden}
    if tipo == "Genérica":
        nodo = generica.crear_addenda(datos_addenda)
    else:
        nodo = walmart.crear_addenda(datos_addenda)

    salida = os.path.splitext(archivo)[0] + "_addenda.xml"
    insertar_addenda(archivo, salida, nodo)

    messagebox.showinfo("Listo",
        f"Addenda generada.\nArchivo: {os.path.basename(salida)}\n"
        f"Folio CFDI: {datos_cfdi['folio']} RFC: {datos_cfdi['rfc']}")

root = tk.Tk()
root.title("Mini Generador de Addendas")

frame = tk.Frame(root, padx=10, pady=10)
frame.pack()

tk.Label(frame, text="Nombre cliente:").grid(row=0, column=0, sticky="e")
entry_nombre = tk.Entry(frame); entry_nombre.grid(row=0, column=1)

tk.Label(frame, text="Proveedor:").grid(row=1, column=0, sticky="e")
entry_proveedor = tk.Entry(frame); entry_proveedor.grid(row=1, column=1)

tk.Label(frame, text="Orden de compra:").grid(row=2, column=0, sticky="e")
entry_orden = tk.Entry(frame); entry_orden.grid(row=2, column=1)

tipo_var = tk.StringVar(value="Genérica")
tk.Label(frame, text="Tipo Addenda:").grid(row=3, column=0, sticky="e")
tk.OptionMenu(frame, tipo_var, "Genérica", "Walmart").grid(row=3, column=1)

tk.Button(frame, text="Generar Addenda", command=generar).grid(row=4, column=0,
                                                              columnspan=2, pady=10)

root.mainloop()
