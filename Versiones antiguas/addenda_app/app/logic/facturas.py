import xml.etree.ElementTree as ET

def insertar_addenda(xml_in, xml_out, addenda_element):
    """
    Inserta un nodo de addenda dentro de un CFDI timbrado.
    Si el nodo <Addenda> ya existe, agrega dentro del existente.
    """
    NS = "http://www.sat.gob.mx/cfd/4"
    ET.register_namespace("cfdi", NS)

    tree = ET.parse(xml_in)
    root = tree.getroot()

    # Buscar nodo Addenda existente
    addenda = root.find(f"{{{NS}}}Addenda")
    if addenda is None:
        addenda = ET.SubElement(root, f"{{{NS}}}Addenda")

    # Agregar la addenda personalizada dentro de Addenda
    addenda.append(addenda_element)

    # Guardar el XML final
    tree.write(xml_out, encoding="utf-8", xml_declaration=True)
