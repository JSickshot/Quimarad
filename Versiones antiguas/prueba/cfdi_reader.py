import xml.etree.ElementTree as ET

def obtener_datos_basicos(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    folio = root.attrib.get("Folio", "SinFolio")
    receptor = root.find(".//{*}Receptor")
    rfc = receptor.attrib.get("Rfc") if receptor is not None else "SinRFC"
    return {"folio": folio, "rfc": rfc}
