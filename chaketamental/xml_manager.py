import xml.etree.ElementTree as ET

def load_xml(xml_path):
    tree = ET.parse(xml_path)
    return tree

def insert_addenda(tree, addenda_element):
    root = tree.getroot()
    ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}  # Ajustar versión CFDI si aplica
    complemento = root.find("cfdi:Complemento", ns)

    if complemento is not None:
        if root.find("cfdi:Addenda", ns) is not None:
            root.remove(root.find("cfdi:Addenda", ns))
        root.append(addenda_element)
    else:
        root.append(addenda_element)

    return tree

def save_xml(tree, path):
    tree.write(path, encoding="utf-8", xml_declaration=True)
