import xml.etree.ElementTree as ET

def crear_addenda(datos):
    
    nodo = ET.Element("AddendaSoriana")
    ET.SubElement(nodo, "Proveedor").text = datos['proveedor']
    ET.SubElement(nodo, "Remision").text = datos['orden']
    ET.SubElement(nodo, "Consecutivo").text = '0'
    ET.SubElement(nodo, "FechaRemision").text = datos.get('fecha', '2025-09-18')
    return nodo
