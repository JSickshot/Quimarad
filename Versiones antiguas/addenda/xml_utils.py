import os
from xml.etree import ElementTree as ET

def integrar_addenda(cfdi_path, addenda_data):
    """
    Inserta o crea el nodo <Addenda> con datos de Soriana Reverse.
    """
    tree = ET.parse(cfdi_path)
    root = tree.getroot()

    addenda_node = root.find("{*}Addenda")
    if addenda_node is None:
        addenda_node = ET.SubElement(root, "Addenda")

    soriana = ET.SubElement(addenda_node, "SorianaReverse")
    for k, v in addenda_data.items():
        ET.SubElement(soriana, k).text = v

    base, _ = os.path.splitext(cfdi_path)
    out_path = base + "_con_addenda.xml"
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return out_path
