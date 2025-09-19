import sqlite3

DB_NAME = "addenda.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            proveedor TEXT,
            orden_compra TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS addendas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            tipo_addenda TEXT,
            archivo_xml TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

def add_cliente(nombre, proveedor, orden):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO clientes(nombre, proveedor, orden_compra) VALUES(?,?,?)",
            (nombre, proveedor, orden),
        )

def update_cliente(nombre, proveedor, orden):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "UPDATE clientes SET proveedor=?, orden_compra=? WHERE nombre=?",
            (proveedor, orden, nombre),
        )

def list_clientes():
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT nombre, proveedor, orden_compra FROM clientes").fetchall()

def registrar_addenda(cliente, tipo, archivo_xml):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO addendas(cliente, tipo_addenda, archivo_xml) VALUES (?,?,?)",
            (cliente, tipo, archivo_xml),
        )

def list_addendas():
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            "SELECT cliente, tipo_addenda, archivo_xml, fecha FROM addendas ORDER BY fecha DESC"
        ).fetchall()
