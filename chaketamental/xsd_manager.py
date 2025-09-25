import xml.etree.ElementTree as ET

XS_NS = {"xs": "http://www.w3.org/2001/XMLSchema"}

def _parse_attributes(complex_type):
    attrs = []
    if complex_type is None:
        return attrs
    for a in complex_type.findall("xs:attribute", XS_NS):
        name = a.get("name")
        if name:
            attrs.append(name)
    return attrs

def _parse_children(container):
    items = []
    if container is None:
        return items
    for child in container.findall("xs:element", XS_NS):
        items.append(child)
    return items

def _parse_element(elem):
    """
    Devuelve dict:
    {
      "__attrs__": ["Id","RowOrder", ...],
      "Remision": { ... },
      "Pedidos": { ... },
      "CampoLeaf": {}   # hoja
    }
    """
    node = {}
    complex_type = elem.find("xs:complexType", XS_NS)

    # atributos
    node["__attrs__"] = _parse_attributes(complex_type)

    # hijos (sequence | all | choice)
    container = None
    if complex_type is not None:
        container = (complex_type.find("xs:sequence", XS_NS)
                     or complex_type.find("xs:all", XS_NS)
                     or complex_type.find("xs:choice", XS_NS))

    children = _parse_children(container)
    if not children:
        # hoja (simpleType o sin hijos)
        return node  # solo atributos si hubiera

    for ch in children:
        ch_name = ch.get("name")
        if not ch_name:
            continue
        node[ch_name] = _parse_element(ch)

    return node

def parse_xsd(path):
    """
    Retorna (root_name, struct) donde struct es la jerarquía del root element.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    # Tomamos el PRIMER xs:element 'global' como raíz de la addenda
    root_elem = None
    for e in root.findall("./xs:element", XS_NS):
        root_elem = e
        break

    if root_elem is None:
        raise ValueError("No se encontró un <xs:element> raíz en el XSD.")

    root_name = root_elem.get("name") or "AddendaRoot"
    struct = _parse_element(root_elem)
    return root_name, struct

def flatten_structure(struct, parent_path=""):
    """
    Convierte la jerarquía en una lista de rutas para generar el formulario.
    Incluye atributos como 'Nodo@Atributo' y hojas como 'Nodo/SubNodo/.../Leaf'.
    """
    paths = []

    # atributos del nodo actual
    for attr in struct.get("__attrs__", []):
        if parent_path:
            paths.append(f"{parent_path}@{attr}")
        else:
            paths.append(f"@{attr}")

    # hijos
    for k, v in struct.items():
        if k == "__attrs__":
            continue
        sub_path = f"{parent_path}/{k}" if parent_path else k
        if isinstance(v, dict) and (set(v.keys()) - {"__attrs__"}):
            # tiene hijos; recursivo
            paths.extend(flatten_structure(v, sub_path))
        else:
            # es hoja (sin más hijos)
            paths.extend(flatten_structure(v, sub_path))  # primero atributos, si hubiera
            paths.append(sub_path)

    return paths
