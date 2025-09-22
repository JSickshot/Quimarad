import xmlschema

def parse_xsd(xsd_path):
    """
    Analiza un XSD y devuelve una estructura recursiva
    con todos los elementos, atributos y restricciones.
    """
    schema = xmlschema.XMLSchema(xsd_path)
    elements = {}
    for name, elem in schema.elements.items():
        elements[name] = get_element_info(elem)
    return elements

def get_element_info(elem):
    info = {
        "name": elem.name,
        "type": str(elem.type.name) if elem.type else "string",
        "attributes": {},
        "children": [],
        "restrictions": {}
    }

    for attr_name, attr in elem.attributes.items():
        info["attributes"][attr_name] = {
            "type": str(attr.type.name) if attr.type else "string",
            "required": attr.use == "required"
        }

    if hasattr(elem.type, "facets") and elem.type.facets:
        for facet_name, facet in elem.type.facets.items():
            if hasattr(facet, "value"):
                info["restrictions"][facet_name] = facet.value

    
    if hasattr(elem.type, "enumeration") and elem.type.enumeration:
        info["restrictions"]["enumeration"] = [v for v in elem.type.enumeration]

   
    if hasattr(elem.type, "content") and elem.type.content:
        for child in elem.type.content.iter_elements():
            info["children"].append(get_element_info(child))

    return info
