import sqlite3

def init_db():
    conn = sqlite3.connect("addenda.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            proveedor TEXT,
            orden_compra TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_cliente(nombre, proveedor, orden):
    conn = sqlite3.connect("addenda.db")
    c = conn.cursor()
    c.execute("INSERT INTO clientes(nombre, proveedor, orden_compra) VALUES (?,?,?)",
              (nombre, proveedor, orden))
    conn.commit()
    conn.close()

def obtener_clientes():
    conn = sqlite3.connect("addenda.db")
    c = conn.cursor()
    c.execute("SELECT nombre, proveedor, orden_compra FROM clientes")
    data = c.fetchall()
    conn.close()
    return data
