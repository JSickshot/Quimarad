import xml.etree.ElementTree as ET

# ===================== Utilidades XSD =====================

XS_NS = "http://www.w3.org/2001/XMLSchema"
NSMAP = {"xs": XS_NS}

def _text(s):
    return (s or "").strip()

def _collect_complex_types(root):
    """Indexa complexTypes y simpleTypes (atributos e hijos)."""
    complex_types = {}
    simple_types = set()

    for ct in root.findall("xs:complexType", NSMAP):
        name = ct.get("name")
        if not name:
            continue
        attrs = []
        for a in ct.findall(".//xs:attribute", NSMAP):
            attrs.append({
                "name": a.get("name"),
                "type": a.get("type") or "xs:string",
                "use": a.get("use", "optional")
            })
        children = []
        for e in ct.findall(".//xs:sequence/xs:element", NSMAP):
            children.append({
                "name": e.get("name"),
                "type": e.get("type"),
                "minOccurs": e.get("minOccurs", "1"),
                "maxOccurs": e.get("maxOccurs", "1"),
                "ref": e.get("ref")
            })
        complex_types[name] = {"attrs": attrs, "children": children}

    for st in root.findall("xs:simpleType", NSMAP):
        name = st.get("name")
        if name:
            simple_types.add(name)

    return complex_types, simple_types

def _resolve_element_shape(elem, complex_types, root):
    """Devuelve dict homogéneo con name, attrs, children, min/maxOccurs, ref."""
    name = elem.get("name")
    el_type = elem.get("type")
    minO = elem.get("minOccurs", "1")
    maxO = elem.get("maxOccurs", "1")
    ref = elem.get("ref")

    shape = {
        "name": name,
        "type": el_type,
        "minOccurs": minO,
        "maxOccurs": maxO,
        "attrs": [],
        "children": [],
        "ref": ref
    }

    # Resolver por ref (básico)
    if ref and not name:
        ref_name = ref.split(":")[-1]
        ref_elem = root.find(f"xs:element[@name='{ref_name}']", NSMAP)
        if ref_elem is not None:
            return _resolve_element_shape(ref_elem, complex_types, root)

    # complexType inline
    cplx = elem.find("xs:complexType", NSMAP)
    if cplx is not None:
        for a in cplx.findall(".//xs:attribute", NSMAP):
            shape["attrs"].append({
                "name": a.get("name"),
                "type": a.get("type") or "xs:string",
                "use": a.get("use", "optional")
            })
        for e in cplx.findall(".//xs:sequence/xs:element", NSMAP):
            shape["children"].append(_resolve_element_shape(e, complex_types, root))
        return shape

    # Tipo referenciado
    if el_type:
        tname = el_type.split(":")[-1]
        if tname in complex_types:
            ct = complex_types[tname]
            # atributos del tipo
            shape["attrs"].extend(ct["attrs"])
            # hijos del tipo
            for e in ct["children"]:
                child = {
                    "name": e["name"],
                    "type": e.get("type"),
                    "minOccurs": e.get("minOccurs", "1"),
                    "maxOccurs": e.get("maxOccurs", "1"),
                    "attrs": [],
                    "children": [],
                    "ref": e.get("ref")
                }
                # Resolver nietos si el hijo es ComplexType referenciado
                if child["type"]:
                    ct_child = child["type"].split(":")[-1]
                    if ct_child in complex_types:
                        ct2 = complex_types[ct_child]
                        child["attrs"].extend(ct2["attrs"])
                        for g in ct2["children"]:
                            grand = {
                                "name": g["name"],
                                "type": g.get("type"),
                                "minOccurs": g.get("minOccurs", "1"),
                                "maxOccurs": g.get("maxOccurs", "1"),
                                "attrs": [],
                                "children": [],
                                "ref": g.get("ref")
                            }
                            # no profundizamos infinitamente para mantener rendimiento
                            child["children"].append(grand)
                shape["children"].append(child)

    return shape

def cargar_xsd(ruta_xsd):
    """
    Lee un XSD y devuelve una lista de 'shapes' de elementos raíz.
    Cada shape: {name, attrs:[{name,type,use}], children:[shape], minOccurs, maxOccurs}
    """
    tree = ET.parse(ruta_xsd)
    root = tree.getroot()
    complex_types, _ = _collect_complex_types(root)

    shapes = []
    for elem in root.findall("xs:element", NSMAP):
        shapes.append(_resolve_element_shape(elem, complex_types, root))
    return shapes

def guardar_xsd(shapes, ruta_guardado="xsd_guardado.xml"):
    """Guarda el esquema parseado (ligero) para reusar."""
    def write_shape(parent, sh):
        e = ET.SubElement(parent, "element",
                          name=sh.get("name") or "",
                          type=sh.get("type") or "",
                          minOccurs=sh.get("minOccurs", "1"),
                          maxOccurs=sh.get("maxOccurs", "1"))
        for a in sh.get("attrs", []):
            ET.SubElement(e, "attribute",
                          name=a.get("name") or "",
                          type=a.get("type") or "xs:string",
                          use=a.get("use", "optional"))
        chs = ET.SubElement(e, "children")
        for c in sh.get("children", []):
            write_shape(chs, c)

    root = ET.Element("xsd_shapes")
    for s in shapes:
        write_shape(root, s)
    ET.ElementTree(root).write(ruta_guardado, encoding="utf-8", xml_declaration=True)

def cargar_xsd_guardado(ruta_guardado="xsd_guardado.xml"):
    """Reconstruye shapes guardados por guardar_xsd."""
    def read_shape(e):
        sh = {
            "name": e.get("name"),
            "type": e.get("type"),
            "minOccurs": e.get("minOccurs", "1"),
            "maxOccurs": e.get("maxOccurs", "1"),
            "attrs": [],
            "children": [],
            "ref": None
        }
        for a in e.findall("attribute"):
            sh["attrs"].append({
                "name": a.get("name"),
                "type": a.get("type"),
                "use": a.get("use", "optional")
            })
        cc = e.find("children")
        if cc is not None:
            for c in cc.findall("element"):
                sh["children"].append(read_shape(c))
        return sh

    tree = ET.parse(ruta_guardado)
    root = tree.getroot()
    shapes = [read_shape(e) for e in root.findall("element")]
    return shapes

# ===================== Lectura CFDI =====================

def extraer_datos_factura(xml_path):
    """Devuelve (datos_header, conceptos) desde un CFDI v4.0."""
    ns = {
        "cfdi": "http://www.sat.gob.mx/cfd/4",
        "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"
    }
    tree = ET.parse(xml_path)
    root = tree.getroot()

    datos = {
        "Total": root.get("Total", ""),
        "SubTotal": root.get("SubTotal", ""),
        "Moneda": root.get("Moneda", ""),
        "Fecha": root.get("Fecha", ""),
        "Folio": root.get("Folio", ""),
        "Serie": root.get("Serie", ""),
        "TipoDeComprobante": root.get("TipoDeComprobante", ""),
        "Version": root.get("Version", ""),
    }

    # Emisor / Receptor
    emisor = root.find("cfdi:Emisor", ns)
    if emisor is not None:
        datos["RfcEmisor"] = emisor.get("Rfc", "")
        datos["NombreEmisor"] = emisor.get("Nombre", "")

    receptor = root.find("cfdi:Receptor", ns)
    if receptor is not None:
        datos["RfcReceptor"] = receptor.get("Rfc", "")
        datos["NombreReceptor"] = receptor.get("Nombre", "")

    # UUID timbre
    uuid = ""
    tfd = root.find("cfdi:Complemento/tfd:TimbreFiscalDigital", ns)
    if tfd is not None:
        uuid = tfd.get("UUID", "")
    datos["UUID"] = uuid

    # IVA traslado 002 (si existe)
    traslado = root.find("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado[@Impuesto='002']", ns)
    if traslado is not None:
        datos["ImporteIVA"] = traslado.get("Importe", "")
        datos["Impuesto"] = traslado.get("Impuesto", "002")

    # Conceptos
    conceptos = []
    for c in root.findall("cfdi:Conceptos/cfdi:Concepto", ns):
        conceptos.append({
            "NoIdentificacion": c.get("NoIdentificacion", ""),
            "Cantidad": c.get("Cantidad", ""),
            "ValorUnitario": c.get("ValorUnitario", ""),
            "Importe": c.get("Importe", ""),
            "Descripcion": c.get("Descripcion", "")
        })

    return datos, conceptos

# ===================== Heurísticas de autollenado =====================

CFDI_TO_ADDENDA_HINTS = {
    "Total": ["montoTotal", "Total", "ImporteTotal"],
    "SubTotal": ["SubTotal", "Subtotal", "ImporteSubtotal"],
    "Moneda": ["moneda@tipoMoneda", "TipoMoneda", "Moneda"],
    "Fecha": ["fecha", "FechaRemision", "FechaFactura"],
    "Folio": ["folioFiscal", "Remision", "FolioFactura", "Folio"],
    "Serie": ["serie", "SerieFactura"],
    "TipoDeComprobante": ["TipoDocumentoFiscal", "tipoDocumento", "TipoDocumento"],
    "Version": ["version"],

    "RfcEmisor": ["proveedor@codigo", "Proveedor", "CodigoProveedor"],
    "NombreEmisor": ["proveedor@nombre", "NombreProveedor"],

    "RfcReceptor": ["destino@codigo", "CodigoDestino", "Destino"],
    "NombreReceptor": ["destino@nombre", "NombreDestino"],

    "ImporteIVA": ["IVA", "otrosCargos@monto", "ImpuestoIVA", "IvaTotal"],
    "Impuesto": ["otrosCargos@codigo"],

    "ConceptoNoIdentificacion": ["Codigo", "SKU", "Articulo", "CodigoProducto"],
    "ConceptoCantidad": ["CantidadUnidadCompra", "Cantidad"],
    "ConceptoValorUnitario": ["CostoNetoUnidadCompra", "PrecioUnitario", "ValorUnitario"],
    "ConceptoPorcentajeIVA": ["PorcentajeIVA"],
}

def _norm(s): return _text(s).lower()

def _candidate_matches(field_name, candidates):
    n = _norm(field_name)
    for cand in candidates:
        if _norm(cand) in n or n in _norm(cand):
            return True
    return False

def sugerir_autovalores(shapes, datos_cfdi, conceptos):
    """Devuelve dict ruta->valor para elementos y atributos sugeridos desde el CFDI."""
    autovals = {}
    index = []
    for k, v in datos_cfdi.items():
        if not v:
            continue
        if k in CFDI_TO_ADDENDA_HINTS:
            for destino in CFDI_TO_ADDENDA_HINTS[k]:
                index.append((destino, v))

    def walk(sh, path):
        name = sh.get("name") or ""
        cur_path = f"{path}/{name}" if path and name else (name or path)

        # Atributos del elemento
        for a in sh.get("attrs", []):
            ruta_attr = f"{cur_path}@{a['name']}"
            valor = ""
            for destino, val in index:
                if _candidate_matches(destino, [a['name'], ruta_attr, cur_path]):
                    valor = val
                    break
            if valor:
                autovals[ruta_attr] = valor

        # Texto de elemento (por nombre)
        if name:
            for k_cfdi, destinos in CFDI_TO_ADDENDA_HINTS.items():
                for d in destinos:
                    if _norm(d) == _norm(name) or _candidate_matches(name, [d]):
                        val = datos_cfdi.get(k_cfdi, "")
                        if val:
                            autovals[cur_path] = val
                            break

        # Conceptos → Artículos (heurística rápida sobre el primero)
        if conceptos:
            first = conceptos[0]
            if _norm(name) in ("codigo", "sku", "articulo"):
                if first.get("NoIdentificacion"):
                    autovals[cur_path] = first["NoIdentificacion"]
            if _norm(name) in ("cantidadunidadcompra", "cantidad"):
                if first.get("Cantidad"):
                    autovals[cur_path] = first["Cantidad"]
            if _norm(name) in ("costonetounidadcompra", "preciounitario", "valorunitario"):
                if first.get("ValorUnitario"):
                    autovals[cur_path] = first["ValorUnitario"]
            if _norm(name) == "porcentajeiva":
                autovals[cur_path] = "16.00"

        for c in sh.get("children", []):
            walk(c, cur_path)

    for s in shapes:
        walk(s, "")

    return autovals
