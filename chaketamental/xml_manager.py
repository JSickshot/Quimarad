import xml.etree.ElementTree as ET

def asegurar_addenda(root):
    """
    Devuelve el nodo <Addenda> (SIN prefijo). Si no está, lo crea así.
    """
    # Buscar sin prefijo
    addenda = root.find("Addenda")
    if addenda is not None:
        return addenda

    # Buscar con prefijo (por si existe) y convertir: limpiarlo y crear nuevo sin prefijo
    for child in list(root):
        tag = child.tag
        if tag.endswith("}Addenda"):
            # mover contenido a uno sin prefijo
            new_addenda = ET.Element("Addenda")
            for sub in list(child):
                child.remove(sub)
                new_addenda.append(sub)
            # reemplazar el nodo
            root.remove(child)
            root.append(new_addenda)
            return new_addenda

    # Crear nuevo
    return ET.SubElement(root, "Addenda")

def construir_addenda(root_cfdi, shapes, valores_form):
    """
    Inserta bajo <Addenda> los elementos definidos por 'shapes'
    usando 'valores_form' (dict de rutas->texto/attr). Nodos SIN namespace.
    """
    addenda = asegurar_addenda(root_cfdi)

    # limpiar addenda anterior
    for ch in list(addenda):
        addenda.remove(ch)

    def set_attrs(node_path, elem):
        prefix = f"{node_path}@"
        for k, v in valores_form.items():
            if not v:
                continue
            if k.startswith(prefix):
                attr = k.split("@", 1)[1]
                elem.set(attr, v)

    def build_elem(sh, path, parent):
        name = sh.get("name") or "Elemento"
        cur_path = f"{path}/{name}" if path and name else (name or path)
        elem = ET.SubElement(parent, name)

        if cur_path in valores_form and (valores_form[cur_path] or "").strip():
            elem.text = valores_form[cur_path].strip()

        set_attrs(cur_path, elem)

        for c in sh.get("children", []):
            build_elem(c, cur_path, elem)

    for s in shapes:
        build_elem(s, "", addenda)

    return addenda
