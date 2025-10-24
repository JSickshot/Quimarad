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
    node = {}
    complex_type = elem.find("xs:complexType", XS_NS)

    node["__attrs__"] = _parse_attributes(complex_type)

    container = None
    if complex_type is not None:
        container = (complex_type.find("xs:sequence", XS_NS)
                     or complex_type.find("xs:all", XS_NS)
                     or complex_type.find("xs:choice", XS_NS))

    children = _parse_children(container)
    if not children:
        
        return node  

    for ch in children:
        ch_name = ch.get("name")
        if not ch_name:
            continue
        node[ch_name] = _parse_element(ch)

    return node

def parse_xsd(path):
   
    tree = ET.parse(path)
    root = tree.getroot()

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
    paths = []

    for attr in struct.get("__attrs__", []):
        if parent_path:
            paths.append(f"{parent_path}@{attr}")
        else:
            paths.append(f"@{attr}")

    for k, v in struct.items():
        if k == "__attrs__":
            continue
        sub_path = f"{parent_path}/{k}" if parent_path else k
        if isinstance(v, dict) and (set(v.keys()) - {"__attrs__"}):
            
            paths.extend(flatten_structure(v, sub_path))
        else:
            
            paths.extend(flatten_structure(v, sub_path))
            paths.append(sub_path)

    return paths
