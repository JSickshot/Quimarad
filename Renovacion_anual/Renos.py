import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import ttk, Menu
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
import sys

if getattr(sys, 'frozen', False):
    script_dir = sys._MEIPASS 
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))

excel_file = None
for f in os.listdir(script_dir):
    if f.startswith("Renos_anual") and (f.endswith(".xls") or f.endswith(".xlsx")):
        excel_file = os.path.join(script_dir, f)
        break

db_file = os.path.join(script_dir, 'data.db')

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

def inicializar_bd_desde_excel():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Clientes (
        rfc TEXT PRIMARY KEY,
        nombre_empresa TEXT NOT NULL,
        contacto TEXT,
        correo_contacto TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rfc TEXT,
        nombre_producto TEXT,
        serie TEXT UNIQUE,
        fecha_caducidad TEXT,
        estado TEXT DEFAULT 'Pendiente',
        FOREIGN KEY (rfc) REFERENCES Clientes(rfc)
    )
    ''')

    cursor.execute("SELECT COUNT(*) FROM Productos")
    if cursor.fetchone()[0] > 0:
        return

    if not excel_file or not os.path.exists(excel_file):
        return

    df = pd.read_excel(excel_file)
    df['Fecha Caducidad'] = pd.to_datetime(df['Fecha Caducidad'], errors='coerce').dt.strftime('%Y-%m-%d')

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR IGNORE INTO Clientes (rfc, nombre_empresa, contacto, correo_contacto)
            VALUES (?, ?, ?, ?)
        ''', (row['RFC'], row['Nombre Empresa'], row['Contacto'], row['Correo Contacto']))

        cursor.execute('''
            INSERT OR IGNORE INTO Productos (rfc, nombre_producto, serie, fecha_caducidad, estado)
            VALUES (?, ?, ?, ?, 'Pendiente')
        ''', (row['RFC'], row['Producto'], row['Serie'], row['Fecha Caducidad']))

    conn.commit()

inicializar_bd_desde_excel()

def licencias_por_vencer():
    today = datetime.today()
    primer_dia_mes = today.replace(day=1)
    ultimo_dia_proximo_mes = (primer_dia_mes + relativedelta(months=2)).replace(day=1) - timedelta(days=1)

    cursor.execute('''
        SELECT Clientes.nombre_empresa, Clientes.rfc, Clientes.contacto, Clientes.correo_contacto, 
               Productos.nombre_producto, Productos.serie, Productos.fecha_caducidad, Productos.estado
        FROM Clientes
        JOIN Productos ON Clientes.rfc = Productos.rfc
        WHERE DATE(Productos.fecha_caducidad) BETWEEN ? AND ?
        ORDER BY DATE(Productos.fecha_caducidad) ASC
    ''', (primer_dia_mes.date(), ultimo_dia_proximo_mes.date()))

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
        ORDER BY DATE(Productos.fecha_caducidad) ASC
    ''', (f'%{valor}%', f'%{valor}%', f'%{valor}%', f'%{valor}%')) 
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
            nombre = valores[0]
            contacto = valores[3]
            serie = valores[5]
            texto_copiado += f"{nombre}\n\n{serie}\n\n{contacto}"
        root.clipboard_clear()
        root.clipboard_append(texto_copiado.strip())
        root.update()

def mostrar_menu(event):
    if tree.selection():
        menu.post(event.x_root, event.y_root)

root = tk.Tk()
root.title("Renovaciones 2025")

frame = tk.Frame(root)
frame.pack(pady=10)

entry_busqueda = tk.Entry(frame, width=70, font=("Arial", 12)) 
entry_busqueda.pack(side=tk.LEFT, padx=10)

btn_buscar = tk.Button(frame, text="Buscar", command=lambda: mostrar_resultados(buscar_cliente(entry_busqueda.get())))
btn_buscar.pack(side=tk.LEFT)

btn_mostrar_todas = tk.Button(frame, text="Mostrar Todas", command=lambda: mostrar_resultados(licencias_por_vencer()))
btn_mostrar_todas.pack(side=tk.LEFT)

columns = ("Empresa", "RFC", "Contacto", "Correo", "Producto", "Serie", "Fecha Caducidad", "Estado")
tree = ttk.Treeview(root, columns=columns, show='headings', height=50)

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=200)

tree.pack(pady=20)

tree.tag_configure('red', background='red')
tree.tag_configure('orange', background='orange')
tree.tag_configure('yellow', background='lightyellow')
tree.tag_configure('blue', background='lightblue')
tree.tag_configure('green', background='lightgreen')

menu = Menu(root, tearoff=0)
menu.add_command(label="Pendiente", command=lambda: cambiar_estado("Pendiente"))
menu.add_command(label="Atendido", command=lambda: cambiar_estado("Atendido"))
menu.add_command(label="En proceso", command=lambda: cambiar_estado("En proceso"))

tree.bind("<Button-3>", mostrar_menu)
tree.bind("<Double-1>", filtrar_por_rfc)
tree.bind("<Control-c>", copiar)

mostrar_resultados(licencias_por_vencer())

root.mainloop()
conn.close()
