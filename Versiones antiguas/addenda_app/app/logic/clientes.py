from app.models.cliente import guardar_cliente, obtener_clientes

def guardar_historial(nombre, proveedor, orden, tipo, fecha):
    guardar_cliente(nombre, proveedor, orden, tipo, fecha)

def listar_historial():
    return obtener_clientes()
