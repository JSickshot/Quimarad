import sqlite3

DB_FILE = "addenda.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            proveedor TEXT,
            orden_compra TEXT,
            tipo_addenda TEXT,
            fecha TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_cliente(nombre, proveedor, orden, tipo, fecha):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO clientes(nombre, proveedor, orden_compra, tipo_addenda, fecha) VALUES (?,?,?,?,?)",
        (nombre, proveedor, orden, tipo, fecha)
    )
    conn.commit()
    conn.close()

def obtener_clientes():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT nombre, proveedor, orden_compra, tipo_addenda, fecha FROM clientes")
    data = c.fetchall()
    conn.close()
    return data
