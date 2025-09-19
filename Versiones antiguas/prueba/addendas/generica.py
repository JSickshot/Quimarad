import xml.etree.ElementTree as ET

def crear_addenda(datos):
    nodo = ET.Element("AddendaGenerica")
    ET.SubElement(nodo, "Proveedor").text = datos["proveedor"]
    ET.SubElement(nodo, "OrdenCompra").text = datos["orden"]
    return nodo
