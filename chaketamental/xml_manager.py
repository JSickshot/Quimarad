import xml.etree.ElementTree as ET

def load_xml(path):
    tree = ET.parse(path)
    return tree, tree.getroot()

def save_xml(tree, path):
    tree.write(path, encoding="utf-8", xml_declaration=True)

def ensure_unqualified_addenda(root):
    """
    Garantiza que exista <Addenda> SIN prefijo (no cfdi:).
    Si existe cfdi:Addenda, la reutiliza en lugar de duplicar.
    """
    # ¿ya hay Addenda sin prefijo?
    addenda = root.find("Addenda")
    if addenda is not None:
        return addenda

    # ¿hay cfdi:Addenda?
    cfdi_ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
    addenda_cfdi = root.find("cfdi:Addenda", cfdi_ns)
    if addenda_cfdi is not None:
        # No vamos a duplicar: usaremos la que está
        return addenda_cfdi

    # Crear nueva sin prefijo
    return ET.SubElement(root, "Addenda")

def insert_by_path(parent, path, value):
    """
    Inserta valor siguiendo rutas 'A/B/C' o 'A/B@attr'.
    Crea nodos intermedios si no existen.
    """
    if not value:
        return

    # Atributo
    if "@" in path:
        elem_path, attr = path.split("@", 1)
        curr = parent
        for tag in [p for p in elem_path.split("/") if p]:
            found = curr.find(tag)
            if found is None:
                found = ET.SubElement(curr, tag)
            curr = found
        curr.set(attr, value)
    else:
        curr = parent
        parts = [p for p in path.split("/") if p]
        for i, tag in enumerate(parts):
            if i == len(parts) - 1:
                leaf = ET.SubElement(curr, tag)
                leaf.text = value
            else:
                found = curr.find(tag)
                if found is None:
                    found = ET.SubElement(curr, tag)
                curr = found

def build_addenda(root, addenda_root_name, entries_dict):
    """
    Construye bajo <Addenda> un nodo raíz con el nombre del XSD (p.ej. DSCargaRemisionProv)
    y debajo coloca la estructura de entries (paths -> valores).
    """
    addenda = ensure_unqualified_addenda(root)

    # Opcional: eliminar previo nodo de la misma raíz para regenerar limpio
    for child in list(addenda):
        if child.tag == addenda_root_name:
            addenda.remove(child)

    cont = ET.SubElement(addenda, addenda_root_name)

    # Insertar cada campo por su ruta
    for path, value in entries_dict.items():
        insert_by_path(cont, path, value)
