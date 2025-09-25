import re

def _norm(s):
    # Normaliza claves: minúsculas, sin espacios, guiones, underscores o dos puntos
    return re.sub(r"[\s_\-:]+", "", (s or "").strip().lower())

def build_cfdi_index(xml_root):
    """
    Indexa TODOS los atributos/textos del CFDI en un dict {clave_normalizada: valor}.
    Se incluyen claves redundantes para mayor facilidad de mapeo.
    """
    idx = {}

    for elem in xml_root.iter():
        local = elem.tag.split("}")[-1]  # quitar namespace
        # texto de nodo
        if elem.text and elem.text.strip():
            key = _norm(local)
            idx.setdefault(key, elem.text.strip())
            idx.setdefault(_norm(f"{local}_text"), elem.text.strip())

        # atributos
        for k, v in elem.attrib.items():
            k_norm = _norm(k)
            idx.setdefault(k_norm, v)
            idx.setdefault(_norm(f"{local}_{k}"), v)

    # Sinónimos útiles para CFDI
    def copy_if(srcs, dst):
        for s in srcs:
            if s in idx:
                idx.setdefault(dst, idx[s])

    copy_if(["subtotal", "comprobante_subtotal"], "subtotal")
    copy_if(["total", "comprobante_total"], "total")
    copy_if(["totalimpuestostrasladados", "impuestos_totalimpuestostrasladados", "traslado_importe"], "iva")
    copy_if(["moneda", "comprobante_moneda"], "moneda")
    copy_if(["folio", "comprobante_folio"], "folio")
    copy_if(["fecha", "comprobante_fecha"], "fecha")
    copy_if(["rfc", "emisor_rfc", "receptor_rfc"], "rfc")
    copy_if(["noidentificacion", "concepto_noidentificacion"], "codigo")
    copy_if(["valorunitario", "concepto_valorunitario"], "valorunitario")
    copy_if(["cantidad", "concepto_cantidad"], "cantidad")
    copy_if(["importe", "concepto_importe"], "importe")

    return idx

def guess_value_for_field(field_path, cfdi_idx):
    """
    Heurística: intenta rellenar automáticamente un campo del XSD
    usando el índice del CFDI timbrado.
    Retorna (valor, editable_bool) -> editable=False si es autollenado.
    """
    name = field_path.split("/")[-1]  # último segmento o '@Atributo'
    if "@" in name:
        name = name.split("@", 1)[1]  # nombre del atributo

    n = _norm(name)

    # 1) Coincidencia directa
    if n in cfdi_idx:
        return cfdi_idx[n], False

    # 2) Coincidencia flexible: buscar claves que contengan el nombre
    for k, v in cfdi_idx.items():
        if n in k:
            return v, False

    # 3) Reglas específicas comunes en addendas (retail / automotriz)
    alias = {
        "subtotal": ["subtotal", "subtotales", "sub_total"],
        "total": ["total", "importetotal", "importe"],
        "iva": ["iva", "totalimpuestostrasladados", "impuestos", "traslado_importe"],
        "moneda": ["moneda", "tipomoneda", "comprobante_moneda"],
        "folio": ["folio", "foliocomprobante", "remision"],
        "fecha": ["fecha", "fecharevision", "fecharemision"],
        "rfc": ["rfc", "emisorrfc", "receptorrfc"],
        "codigo": ["codigo", "noidentificacion"],
        "cantidad": ["cantidad", "concepto_cantidad", "cantidadunidadcompra"],
        "valorunitario": ["valorunitario", "costonetounidadcompra"],
        "importe": ["importe", "concepto_importe"],
    }
    for canonico, keys in alias.items():
        if n == canonico or any(n == _norm(k) for k in keys):
            # toma el mejor match disponible
            for key in keys:
                kn = _norm(key)
                if kn in cfdi_idx:
                    return cfdi_idx[kn], False

    # 4) No encontrado -> usuario lo captura
    return "", True
