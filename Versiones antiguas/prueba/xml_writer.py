import xml.etree.ElementTree as ET

def insertar_addenda(xml_in, xml_out, addenda_element):
    NS = "http://www.sat.gob.mx/cfd/4"    
    ET.register_namespace("cfdi", NS)     

    tree = ET.parse(xml_in)
    root = tree.getroot()

    addenda = ET.SubElement(root, f"{{{NS}}}Addenda")
    addenda.append(addenda_element)

    tree.write(xml_out, encoding="utf-8", xml_declaration=True)