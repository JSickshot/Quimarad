import xml.etree.ElementTree as ET

def crear_addenda(datos):
    nodo = ET.Element("AddendaWalmart")
    ET.SubElement(nodo, "NumProveedor").text = datos["proveedor"]
    ET.SubElement(nodo, "PO").text = datos["orden"]
    return nodo
