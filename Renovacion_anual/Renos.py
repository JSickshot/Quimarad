import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import ttk, Menu
from datetime import datetime

db_file = 'data.db'

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

#bd

def licencias_por_vencer():
    today = datetime.today()
    primer_dia_mes = today.replace(day=1)
    ultimo_dia_proximo_mes = (primer_dia_mes.replace(month=today.month + 2, day=1) - pd.Timedelta(days=1)).date()

    cursor.execute('''
    SELECT Clientes.nombre_empresa, Clientes.rfc, Clientes.contacto, Clientes.correo_contacto, 
           Productos.nombre_producto, Productos.serie, Productos.fecha_caducidad, Productos.estado
    FROM Clientes
    JOIN Productos ON Clientes.rfc = Productos.rfc
    WHERE DATE(Productos.fecha_caducidad) BETWEEN ? AND ?
    ORDER BY DATE(Productos.fecha_caducidad) ASC
    ''', (primer_dia_mes.date(), ultimo_dia_proximo_mes))

    return cursor.fetchall()

def buscar_cliente(valor):
    cursor.execute('''
    SELECT Clientes.nombre_empresa, Clientes.rfc, Clientes.contacto, Clientes.correo_contacto, 
           Productos.nombre_producto, Productos.serie, Productos.fecha_caducidad, Productos.estado
    FROM Clientes
    LEFT JOIN Productos ON Clientes.rfc = Productos.rfc
    WHERE Clientes.nombre_empresa LIKE ? 
       OR Clientes.rfc LIKE ? 
       OR Productos.serie LIKE ? 
       OR Productos.nombre_producto LIKE ?
       OR Productos.serie LIKE ?
    ORDER BY DATE(Productos.fecha_caducidad) ASC
    ''', (f'%{valor}%', f'%{valor}%', f'%{valor}%', f'%{valor}%', f'%{valor}%')) 
    return cursor.fetchall()

def mostrar_resultados(resultados):
    today = datetime.today().date()

    for row in tree.get_children():
        tree.delete(row)

    for resultado in resultados:
        fecha_cad_str = resultado[6]
        fecha_cad = datetime.strptime(fecha_cad_str, '%Y-%m-%d').date()
        estado = resultado[7]

        if estado == "Atendido":
            color = 'green'
        elif estado == "En proceso":
            color = 'blue'
        elif fecha_cad < today:
            color = 'red'
        elif (fecha_cad - today).days <= 30:
            color = 'orange'
        else:
            color = 'yellow'

        tree.insert('', 'end', values=resultado, tags=(color,))

def filtrar_por_rfc(event):
    seleccion = tree.selection()
    if seleccion:
        rfc = tree.item(seleccion[0], 'values')[1] 
        mostrar_resultados(buscar_cliente(rfc))

def cambiar_estado(estado):
    seleccion = tree.selection()
    if seleccion:
        for item in seleccion:
            valores = tree.item(item, 'values')
            serie = valores[5]
            cursor.execute('''
            UPDATE Productos SET estado = ? WHERE serie = ?
            ''', (estado, serie))
            conn.commit()

        mostrar_resultados(licencias_por_vencer())


def copiar(event):
    seleccion = tree.selection()
    if seleccion:
        texto_copiado = ""
        for item in seleccion:
            valores = tree.item(item, 'values')
            serie = valores[5]
            nombre = valores[0]
            texto_copiado += nombre + "\n" + "\n" +  + serie 
        root.clipboard_clear()
        root.clipboard_append(texto_copiado.strip())
        root.update() 

def mostrar_menu(event):
    seleccion = tree.selection()
    if seleccion:
        menu.post(event.x_root, event.y_root)


#interfaz tkinter
root = tk.Tk()
root.title("Renovación 2025")

frame = tk.Frame(root)
frame.pack(pady=10)

entry_busqueda = tk.Entry(frame, width=70, font=("Arial", 12)) 
entry_busqueda.pack(side=tk.LEFT, padx=10)

btn_buscar = tk.Button(frame, text="Buscar", command=lambda: mostrar_resultados(buscar_cliente(entry_busqueda.get())))
btn_buscar.pack(side=tk.LEFT)

btn_mostrar_todas = tk.Button(frame, text="Mostrar Todas", command=lambda: mostrar_resultados(licencias_por_vencer()))
btn_mostrar_todas.pack(side=tk.LEFT)


columns = ("Empresa", "RFC", "Contacto", "Correo", "Producto", "Serie", "Fecha Caducidad", "Estado")
tree = ttk.Treeview(root, columns=columns, show='headings', height=30) 


for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=200)

tree.pack(pady=20)

tree.tag_configure('red', background='red')
tree.tag_configure('orange', background='orange')
tree.tag_configure('yellow', background='yellow')
tree.tag_configure('blue', background='lightblue')
tree.tag_configure('green', background='lightgreen')

menu = Menu(root, tearoff=0)
menu.add_command(label="Pendiente", command=lambda: cambiar_estado("Pendiente"))
menu.add_command(label="Atendido", command=lambda: cambiar_estado("Atendido"))

tree.bind("<Button-3>", mostrar_menu)
tree.bind("<Double-1>", filtrar_por_rfc)
tree.bind("<Control-c>", copiar) 

mostrar_resultados(licencias_por_vencer())

root.mainloop()

conn.close()