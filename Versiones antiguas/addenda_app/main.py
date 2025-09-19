import tkinter as tk
from tkinter import ttk, messagebox

def actualizar_formulario(*args):
    # Ocultar todos los frames primero
    frame_reverse.grid_remove()
    
    tipo = tipo_var.get()
    if tipo == "Soriana Reverse":
        frame_reverse.grid(row=6, column=0, columnspan=2, pady=10)
    else:
        # Solo los campos básicos
        frame_reverse.grid_remove()

# --- Ventana principal ---
root = tk.Tk()
root.title("Generador de Addendas Dinámico")

frame = tk.Frame(root, padx=10, pady=10)
frame.grid(row=0, column=0)

# Campos básicos
tk.Label(frame, text="Nombre cliente:").grid(row=0, column=0, sticky="e")
entry_nombre = tk.Entry(frame); entry_nombre.grid(row=0, column=1)

tk.Label(frame, text="Proveedor:").grid(row=1, column=0, sticky="e")
entry_proveedor = tk.Entry(frame); entry_proveedor.grid(row=1, column=1)

tk.Label(frame, text="Orden de compra:").grid(row=2, column=0, sticky="e")
entry_orden = tk.Entry(frame); entry_orden.grid(row=2, column=1)

# Tipo de addenda
tipo_var = tk.StringVar()
tipo_var.set("Walmart")
ttk.OptionMenu(frame, tipo_var, "Walmart", "La Comercial", "Soriana Reverse").grid(row=3, column=1)
tipo_var.trace("w", actualizar_formulario)

# --- Frame Soriana Reverse ---
frame_reverse = tk.Frame(frame, padx=5, pady=5, relief="groove", borderwidth=2)

tk.Label(frame_reverse, text="Folio de Recibo:").grid(row=0, column=0, sticky="e")
entry_folio = tk.Entry(frame_reverse); entry_folio.grid(row=0, column=1)

tk.Label(frame_reverse, text="Fecha:").grid(row=1, column=0, sticky="e")
entry_fecha = tk.Entry(frame_reverse); entry_fecha.grid(row=1, column=1)
entry_fecha.insert(0, "2025-09-18")

# Tabla de productos
productos = ttk.Treeview(frame_reverse, columns=("Código","Descripción","Cantidad","Precio","Importe"), show="headings")
for col in productos["columns"]:
    productos.heading(col, text=col)
productos.grid(row=2, column=0, columnspan=2)

def agregar_producto():
    codigo = entry_codigo.get()
    desc = entry_desc.get()
    cant = entry_cant.get()
    precio = entry_precio.get()
    importe = float(cant) * float(precio)
    productos.insert("", "end", values=(codigo, desc, cant, precio, f"{importe:.2f}"))

tk.Label(frame_reverse, text="Código").grid(row=3, column=0)
entry_codigo = tk.Entry(frame_reverse); entry_codigo.grid(row=3, column=1)
tk.Label(frame_reverse, text="Descripción").grid(row=4, column=0)
entry_desc = tk.Entry(frame_reverse); entry_desc.grid(row=4, column=1)
tk.Label(frame_reverse, text="Cantidad").grid(row=5, column=0)
entry_cant = tk.Entry(frame_reverse); entry_cant.grid(row=5, column=1)
tk.Label(frame_reverse, text="Precio Unitario").grid(row=6, column=0)
entry_precio = tk.Entry(frame_reverse); entry_precio.grid(row=6, column=1)
tk.Button(frame_reverse, text="Agregar Producto", command=agregar_producto).grid(row=7, column=0, columnspan=2, pady=5)

# Totales
tk.Label(frame_reverse, text="Subtotal").grid(row=8, column=0, sticky="e")
entry_subtotal = tk.Entry(frame_reverse); entry_subtotal.grid(row=8, column=1)
tk.Label(frame_reverse, text="IVA").grid(row=9, column=0, sticky="e")
entry_iva = tk.Entry(frame_reverse); entry_iva.grid(row=9, column=1)
tk.Label(frame_reverse, text="Total").grid(row=10, column=0, sticky="e")
entry_total = tk.Entry(frame_reverse); entry_total.grid(row=10, column=1)

frame_reverse.grid_remove()

root.mainloop()
