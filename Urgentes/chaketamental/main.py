# main.py
import os
import json
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET

# -------- Utilidades de red/XSD (URL) -------------
import urllib.parse
import urllib.request

XSD_CACHE_DIR = os.path.join(os.getcwd(), ".xsd_cache")
os.makedirs(XSD_CACHE_DIR, exist_ok=True)

def _es_url(s: str) -> bool:
    try:
        u = urllib.parse.urlparse(s)
        return u.scheme in ("http", "https")
    except Exception:
        return False

def _descargar_xsd(url: str) -> str:
    """
    Descarga un XSD desde internet a caché local y regresa la ruta del archivo.
    """
    if not _es_url(url):
        raise ValueError("La dirección no parece una URL válida.")
    nombre = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".xsd"
    destino = os.path.join(XSD_CACHE_DIR, nombre)
    urllib.request.urlretrieve(url, destino)
    if os.path.getsize(destino) == 0:
        raise IOError("El archivo descargado está vacío.")
    return destino

def cargar_xsd_desde_fuente(path_o_url: str) -> str:
    """Ruta local o URL http/https → ruta local."""
    if _es_url(path_o_url):
        return _descargar_xsd(path_o_url)
    if not os.path.exists(path_o_url):
        raise FileNotFoundError("No se encontró el archivo XSD especificado.")
    return path_o_url

# ========= Validación XSD (lxml opcional) =========
try:
    from lxml import etree as LET
    HAS_LXML = True
except Exception:
    HAS_LXML = False

# ================== Constantes =====================
CFDI_NS = "http://www.sat.gob.mx/cfd/4"
TFD_NS  = "http://www.sat.gob.mx/TimbreFiscalDigital"
CFDI    = "{%s}" % CFDI_NS
XS_NS   = "{http://www.w3.org/2001/XMLSchema}"

ET.register_namespace("cfdi", CFDI_NS)

CACHE_PATH = "xsd_autofill_cache.json"   # cache reglas inferidas por XSD

# ================= Utilidades XML ==================
def pretty_xml(tree: ET.ElementTree) -> None:
    try:
        ET.indent(tree, space="  ")
    except Exception:
        pass

def q(uri, local):
    return f"{{{uri}}}{local}" if uri else local

def generate_preview(tree: ET.ElementTree) -> str:
    try:
        ET.indent(tree, space="  ")
    except Exception:
        pass
    return ET.tostring(tree.getroot(), encoding="unicode")

# ============ Parseo XSD → Shapes (para UI) =======
def _xsd_get(el, name, default=None):
    return el.attrib.get(name, default)

def _xsd_q(tag):
    return f"{XS_NS}{tag}"

def parse_xsd_target_namespace(xsd_path: str) -> str:
    try:
        tree = ET.parse(xsd_path)
        root = tree.getroot()
        return root.attrib.get("targetNamespace", "") or ""
    except Exception:
        return ""

def _collect_attributes(ct):
    attrs = []
    for a in ct.findall(_xsd_q("attribute")):
        attrs.append({
            "name": _xsd_get(a, "name"),
            "type": _xsd_get(a, "type"),
            "use": _xsd_get(a, "use", "optional"),
            "fixed": _xsd_get(a, "fixed"),
            "default": _xsd_get(a, "default")
        })
    return attrs

def _resolve_type_map(schema_root):
    tmap = {}
    for ct in schema_root.findall(_xsd_q("complexType")):
        name = _xsd_get(ct, "name")
        if name:
            tmap[name] = ct
    return tmap

def _build_shape_from_complexType(ct, tmap, parent_path):
    shape = {"attributes": _collect_attributes(ct), "children": []}
    seq   = ct.find(_xsd_q("sequence"))
    allg  = ct.find(_xsd_q("all"))
    choice= ct.find(_xsd_q("choice"))
    group = seq or allg or choice
    if group is not None:
        for e in group.findall(_xsd_q("element")):
            shape["children"].append(_shape_from_element(e, tmap, parent_path))
    return shape

def _shape_from_element(el, tmap, parent_path):
    name      = el.attrib.get("name") or el.attrib.get("ref") or "Elemento"
    minOccurs = el.attrib.get("minOccurs", "1")
    maxOccurs = el.attrib.get("maxOccurs", "1")
    tp        = el.attrib.get("type")
    cur_path  = f"{parent_path}/{name}" if parent_path else name

    child_shape = {
        "name": name, "path": cur_path,
        "minOccurs": minOccurs, "maxOccurs": maxOccurs,
        "attributes": [], "children": [],
        "is_simple": False
    }

    inl = el.find(_xsd_q("complexType"))
    if inl is not None:
        inline_ct = _build_shape_from_complexType(inl, tmap, cur_path)
        child_shape["attributes"] = inline_ct["attributes"]
        child_shape["children"]   = inline_ct["children"]
        return child_shape

    if tp and ":" in tp:
        tp = tp.split(":", 1)[1]
    if tp and tp in tmap:
        ct = tmap[tp]
        ref_ct = _build_shape_from_complexType(ct, tmap, cur_path)
        child_shape["attributes"] = ref_ct["attributes"]
        child_shape["children"]   = ref_ct["children"]
        return child_shape

    # sin complexType -> elemento simple (texto)
    child_shape["is_simple"] = True
    return child_shape

def parse_xsd(xsd_path, root_element_name=None):
    tree = ET.parse(xsd_path)
    schema_root = tree.getroot()
    tmap = _resolve_type_map(schema_root)
    shapes = []
    for el in schema_root.findall(_xsd_q("element")):
        name = el.attrib.get("name")
        if root_element_name and name != root_element_name:
            continue
        shapes.append(_shape_from_element(el, tmap, parent_path=""))
    return shapes

# ======= Construcción Addenda dentro del CFDI ======
def construir_addenda(root_cfdi, valores_form, ns_cfg=None):
    """
    Inserta <cfdi:Addenda> con lo que hay en valores_form:
    {"roots": [ {"name": "...", "attributes": {...}, "text": "...", "children":[...]}, ... ]}
    """
    ET.register_namespace("cfdi", CFDI_NS)
    qname_cli = (lambda local: local)
    if ns_cfg and ns_cfg.get("uri"):
        ET.register_namespace(ns_cfg.get("prefix",""), ns_cfg["uri"])
        qname_cli = lambda local: q(ns_cfg["uri"], local)

    addenda = root_cfdi.find(CFDI + "Addenda")
    if addenda is None:
        addenda = ET.SubElement(root_cfdi, CFDI + "Addenda")

    for top in valores_form.get("roots", []):
        _emit_instance(addenda, top, qname_cli)

def _emit_instance(parent, inst, qname_cli):
    elem = ET.SubElement(parent, qname_cli(inst["name"]))
    for k, v in inst.get("attributes", {}).items():
        if v is None or v == "":
            continue
        elem.set(k, str(v))
    if "text" in inst and inst["text"] not in (None, ""):
        elem.text = str(inst["text"])
    for ch in inst.get("children", []):
        _emit_instance(elem, ch, qname_cli)

# ========= VALIDACIÓN contra XSD (con lxml) ========
def validate_addenda_subtree_with_xsd(cfdi_root: ET.Element, xsd_path: str, ns_uri: str = ""):
    if not HAS_LXML:
        return (False, "Validación deshabilitada: instala lxml (pip install lxml)")
    addenda = cfdi_root.find(CFDI + "Addenda")
    if addenda is None or len(list(addenda)) == 0:
        return (False, "No hay elementos dentro de <cfdi:Addenda> para validar.")

    target = None
    if ns_uri:
        for ch in list(addenda):
            if isinstance(ch.tag, str) and ch.tag.startswith("{"+ns_uri+"}"):
                target = ch; break
    if target is None:
        target = list(addenda)[0]

    xml_bytes = ET.tostring(target, encoding="utf-8", xml_declaration=True)
    try:
        parser = LET.XMLParser(load_dtd=False, no_network=False, recover=True)
        schema_doc = LET.parse(xsd_path, parser)
        schema = LET.XMLSchema(schema_doc)
    except Exception as e:
        return (False, f"XSD inválido o no se pudo cargar:\n{e}")

    try:
        doc = LET.fromstring(xml_bytes)
        ok = schema.validate(doc)
        if ok:
            return (True, "OK")
        log = schema.error_log
        if log:
            lineas = [f"Línea {e.line}: {e.message}" for e in log]
            return (False, "\n".join(lineas))
        return (False, "La Addenda no cumple el XSD.")
    except Exception as e:
        return (False, f"Error durante la validación:\n{e}")

# ======== Contexto desde CFDI =========
def extract_cfdi_context(cfdi_root: ET.Element) -> dict:
    ctx = {}
    comp = cfdi_root
    if comp is None:
        return ctx

    g = comp.attrib.get
    ctx["serie"]       = g("Serie")
    ctx["folio"]       = g("Folio")
    ctx["fecha"]       = g("Fecha")
    ctx["moneda"]      = g("Moneda")
    ctx["tipocambio"]  = g("TipoCambio")
    ctx["formapago"]   = g("FormaPago")
    ctx["metodopago"]  = g("MetodoPago")
    ctx["subtotal"]    = g("SubTotal") or g("SubTotal")
    ctx["total"]       = g("Total")
    ctx["lugar"]       = g("LugarExpedicion")
    ctx["nocert"]      = g("NoCertificado")
    ctx["sello"]       = g("Sello")

    em = comp.find(CFDI + "Emisor")
    re = comp.find(CFDI + "Receptor")
    if em is not None:
        gg = em.attrib.get
        ctx["emisor_rfc"]     = gg("Rfc")
        ctx["emisor_nombre"]  = gg("Nombre")
        ctx["emisor_regimen"] = gg("RegimenFiscal")
    if re is not None:
        gg = re.attrib.get
        ctx["receptor_rfc"]            = gg("Rfc")
        ctx["receptor_nombre"]         = gg("Nombre")
        ctx["receptor_uso"]            = gg("UsoCFDI")
        ctx["receptor_domiciliofiscal"]= gg("DomicilioFiscalReceptor")
        ctx["receptor_regimen"]        = gg("RegimenFiscalReceptor")

    # Concepto 1 (útil para retail)
    conceptos = comp.find(CFDI + "Conceptos")
    if conceptos is not None:
        c0 = conceptos.find(CFDI + "Concepto")
        if c0 is not None:
            cg = c0.attrib.get
            ctx["concepto1_cantidad"]      = cg("Cantidad")
            ctx["concepto1_descripcion"]   = cg("Descripcion")
            ctx["concepto1_noid"]          = cg("NoIdentificacion")
            ctx["concepto1_valorunit"]     = cg("ValorUnitario")
            ctx["concepto1_importe"]       = cg("Importe")
            ctx["concepto1_claveprodserv"] = cg("ClaveProdServ")
            ctx["concepto1_claveunidad"]   = cg("ClaveUnidad")

    # Impuestos
    iva_total  = 0.0
    ieps_total = 0.0
    otros_total= 0.0

    def _to_float(s):
        try:
            return float(s)
        except Exception:
            return 0.0

    imp = comp.find(CFDI + "Impuestos")
    if imp is not None:
        tot_tras = _to_float(imp.attrib.get("TotalImpuestosTrasladados", "0"))
        iva_total = max(iva_total, tot_tras)
        tras = imp.find(CFDI + "Traslados")
        if tras is not None:
            for t in tras.findall(CFDI + "Traslado"):
                imp_clave = t.attrib.get("Impuesto")
                importe   = _to_float(t.attrib.get("Importe", "0"))
                if imp_clave == "002":
                    iva_total = max(iva_total, importe) if iva_total else importe
                elif imp_clave == "003":
                    ieps_total += importe
                else:
                    otros_total += importe

    if conceptos is not None:
        for c in conceptos.findall(CFDI + "Concepto"):
            imp_c = c.find(CFDI + "Impuestos")
            if imp_c is None: continue
            tras_c = imp_c.find(CFDI + "Traslados")
            if tras_c is None: continue
            for t in tras_c.findall(CFDI + "Traslado"):
                imp_clave = t.attrib.get("Impuesto")
                importe   = _to_float(t.attrib.get("Importe", "0"))
                if imp_clave == "002":
                    iva_total += importe
                elif imp_clave == "003":
                    ieps_total += importe
                else:
                    otros_total += importe

    ctx["iva_total"]  = f"{iva_total:.2f}" if iva_total else None
    ctx["ieps_total"] = f"{ieps_total:.2f}" if ieps_total else None
    ctx["otros_imp"]  = f"{otros_total:.2f}" if otros_total else None

    # Timbre
    uuid = no_cert_sat = fecha_timbrado = sello_sat = None
    comp_comp = comp.find(CFDI + "Complemento")
    if comp_comp is not None:
        for ch in comp_comp:
            if isinstance(ch.tag, str) and ch.tag.startswith("{"+TFD_NS+"}"):
                uuid          = ch.attrib.get("UUID")
                no_cert_sat   = ch.attrib.get("NoCertificadoSAT")
                fecha_timbrado= ch.attrib.get("FechaTimbrado")
                sello_sat     = ch.attrib.get("SelloSAT")
                break
    ctx["uuid"]          = uuid
    ctx["nocertsat"]     = no_cert_sat
    ctx["fechatimbrado"] = fecha_timbrado
    ctx["sello_sat"]     = sello_sat
    return ctx

# ======== Heurística simple de autollenado =========
def guess_autofill_value_by_name(name: str, ctx: dict) -> str:
    if not name: return ""
    n = name.strip().lower()

    direct = {
        "rfcemisor":"emisor_rfc","emisor_rfc":"emisor_rfc",
        "rfcreceptor":"receptor_rfc","rfc_receptor":"receptor_rfc",
        "uuid":"uuid","folio":"folio","serie":"serie",
        "total":"total","subtotal":"subtotal",
        "moneda":"moneda","fechatimbrado":"fechatimbrado","fecha":"fecha",
        "formapago":"formapago","metodopago":"metodopago","tipocambio":"tipocambio",
        "nocertificado":"nocert","nocertificadosat":"nocertsat",
        "lugarexpedicion":"lugar","sellosat":"sello_sat","sello":"sello",
        "nombreemisor":"emisor_nombre","nombrereceptor":"receptor_nombre",
        "usocfdi":"receptor_uso","domiciliofiscalreceptor":"receptor_domiciliofiscal",
        "regimenfiscalreceptor":"receptor_regimen","regimenfiscalemisor":"emisor_regimen",
        "iva":"iva_total","ieps":"ieps_total","otrosimpuestos":"otros_imp",
        "descripcion":"concepto1_descripcion","cantidad":"concepto1_cantidad",
        "preciounitario":"concepto1_valorunit","montolinea":"concepto1_importe",
    }
    if n in direct:
        val = ctx.get(direct[n])
        if val is not None:
            return val

    def pick(*keys):
        for k in keys:
            if ctx.get(k):
                return ctx[k]
        return ""

    if "uuid" in n: return pick("uuid")
    if "emisor" in n and "rfc" in n: return pick("emisor_rfc")
    if "receptor" in n and "rfc" in n: return pick("receptor_rfc")
    if "rfc" in n: return pick("receptor_rfc","emisor_rfc")
    if "folio" in n: return pick("folio")
    if "serie" in n: return pick("serie")
    if "subtotal" in n: return pick("subtotal")
    if "iva" in n: return pick("iva_total")
    if "ieps" in n: return pick("ieps_total")
    if "total" in n: return pick("total")
    if "moneda" in n: return pick("moneda")
    if "fecha" in n and "timbr" in n: return pick("fechatimbrado")
    if "fecha" in n: return pick("fecha")
    if "metodo" in n: return pick("metodopago")
    if "forma" in n and "pago" in n: return pick("formapago")
    if "cambio" in n: return pick("tipocambio")
    if "lug" in n and "exped" in n: return pick("lugar")
    if "cert" in n and "sat" in n: return pick("nocertsat")
    if "cert" in n: return pick("nocert")
    if "sello" in n and "sat" in n: return pick("sello_sat")
    if "sello" in n: return pick("sello")
    if "descripcion" in n: return pick("concepto1_descripcion")
    if "cantidad" in n: return pick("concepto1_cantidad")
    if "precio" in n and "unit" in n: return pick("concepto1_valorunit")
    if "monto" in n or "importe" in n: return pick("concepto1_importe")
    return ""

# --------- Lectura de hints/keywords desde el XSD ----------
def _xsd_text(el):
    try:
        return "".join(el.itertext()).strip().lower()
    except Exception:
        return ""

def _xsd_first(el, tag_local):
    return el.find(f"{XS_NS}{tag_local}")

def _read_annotation_hints(xsd_elem):
    ann = _xsd_first(xsd_elem, "annotation")
    if ann is None:
        return ""
    buf = []
    for child in list(ann):
        if child.tag in (f"{XS_NS}documentation", f"{XS_NS}appinfo"):
            txt = _xsd_text(child)
            if txt:
                buf.append(txt)
    return " ".join(buf)

XSD_KEYWORDS_TO_CFDI = [
    (("uuid",), "uuid"),
    (("receptor","rfc"), "receptor_rfc"),
    (("emisor","rfc"), "emisor_rfc"),
    (("folio",), "folio"),
    (("serie",), "serie"),
    (("subtotal",), "subtotal"),
    (("total",), "total"),
    (("iva","impuesto al valor agregado"), "iva_total"),
    (("ieps",), "ieps_total"),
    (("otros","impuestos"), "otros_imp"),
    (("moneda",), "moneda"),
    (("fecha timbrado","fechatimbrado"), "fechatimbrado"),
    (("fecha",), "fecha"),
    (("metodo","pago"), "metodopago"),
    (("forma","pago"), "formapago"),
    (("tipo","cambio"), "tipocambio"),
    (("lugar","expedicion"), "lugar"),
    (("certificado","sat"), "nocertsat"),
    (("certificado",), "nocert"),
    (("sello","sat"), "sello_sat"),
    (("sello",), "sello"),
    (("descripcion","concepto"), "concepto1_descripcion"),
    (("cantidad","concepto"), "concepto1_cantidad"),
    (("precio","unitario"), "concepto1_valorunit"),
    (("monto","linea"), "concepto1_importe"),
]

def _decide_cfdi_key_by_name_and_hints(name: str, hint_text: str) -> str:
    n = (name or "").strip().lower()
    if not n and not hint_text:
        return ""
    name_to_key = {
        "uuid":"uuid","folio":"folio","serie":"serie","subtotal":"subtotal","total":"total",
        "moneda":"moneda","fechatimbrado":"fechatimbrado","fecha":"fecha","formapago":"formapago",
        "metodopago":"metodopago","tipocambio":"tipocambio","lugarexpedicion":"lugar",
        "nocertificado":"nocert","nocertificadosat":"nocertsat","sellosat":"sello_sat","sello":"sello",
        "rfcreceptor":"receptor_rfc","rfcemisor":"emisor_rfc"
    }
    if n in name_to_key:
        return name_to_key[n]
    hay = lambda words: all(w in hint_text for w in words)
    for keys, cfdi_key in XSD_KEYWORDS_TO_CFDI:
        if all(k in n for k in keys) or hay(keys):
            return cfdi_key
    return ""

def build_autofill_rules_from_xsd(xsd_path, root_element_name=None):
    rules = {}
    try:
        tree = ET.parse(xsd_path)
        schema_root = tree.getroot()

        def process_element(elem):
            el_name = elem.attrib.get("name") or elem.attrib.get("ref")
            hints_el = _read_annotation_hints(elem)
            inl = elem.find(_xsd_q("complexType"))
            if inl is not None:
                for a in inl.findall(_xsd_q("attribute")):
                    nm = a.attrib.get("name")
                    if not nm or a.attrib.get("fixed") or a.attrib.get("default"):
                        continue
                    k = _decide_cfdi_key_by_name_and_hints(nm, hints_el + " " + _read_annotation_hints(a))
                    if k: rules[nm] = k
                group = inl.find(_xsd_q("sequence")) or inl.find(_xsd_q("all")) or inl.find(_xsd_q("choice"))
                if group is not None:
                    for e in group.findall(_xsd_q("element")):
                        nm = e.attrib.get("name") or e.attrib.get("ref")
                        if not nm:
                            continue
                        has_complex = (e.find(_xsd_q("complexType")) is not None)
                        if not has_complex:
                            k = _decide_cfdi_key_by_name_and_hints(nm, hints_el + " " + _read_annotation_hints(e))
                            if k: rules[nm] = k
            else:
                if el_name:
                    k = _decide_cfdi_key_by_name_and_hints(el_name, hints_el)
                    if k: rules[el_name] = k

        for el in schema_root.findall(_xsd_q("element")):
            name = el.attrib.get("name")
            if root_element_name and name != root_element_name:
                continue
            process_element(el)

        return rules
    except Exception:
        return rules

# --------------- Cache reglas por XSD ---------------
def xsd_fingerprint(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
        return hashlib.sha1(data).hexdigest()
    except Exception:
        try:
            st = os.stat(path)
            mix = f"{os.path.basename(path)}|{st.st_size}|{int(st.st_mtime)}"
            return hashlib.sha1(mix.encode("utf-8")).hexdigest()
        except Exception:
            return os.path.basename(path)

def load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# -------- Helpers Addenda/XML -------------
def _localname(tag: str) -> str:
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag

def _elegir_hijo_addenda(cfdi_root):
    """Devuelve el Element objetivo dentro de <cfdi:Addenda>.
    Si hay más de uno, deja elegir."""
    addenda = cfdi_root.find(CFDI + "Addenda")
    if addenda is None:
        return None
    hijos = [ch for ch in list(addenda)]
    if not hijos:
        return None
    if len(hijos) == 1:
        return hijos[0]

    win = tk.Toplevel()
    win.title("Selecciona la Addenda a usar")
    ttk.Label(win, text="Este CFDI tiene varias addendas. Elige cuál usar:").pack(anchor="w", padx=10, pady=(10,6))
    lb = tk.Listbox(win, width=80, height=min(10, len(hijos)))
    for ch in hijos:
        tag = ch.tag
        ns = tag.split("}")[0][1:] if tag.startswith("{") else ""
        ln = tag.split("}",1)[1] if tag.startswith("{") else tag
        pista_attr = next(iter(ch.attrib.keys()), "")
        pista_child = (ch[0].tag.split("}",1)[1] if len(ch) else "")
        desc = f"{ln}   ns={ns or '—'}   attr={_localname(pista_attr) or '—'}   child={pista_child or '—'}"
        lb.insert(tk.END, desc)
    lb.pack(fill="both", expand=True, padx=10)

    choice = {"idx": 0}
    def ok():
        try: choice["idx"] = lb.curselection()[0]
        except Exception: choice["idx"] = 0
        win.destroy()
    ttk.Button(win, text="Usar seleccionado", command=ok).pack(pady=8)
    win.grab_set(); win.wait_window()
    return hijos[choice["idx"]]

def _walk_collect_simple_values(elem, out, path=""):
    """
    Recolecta:
      - Atributos: out[("attr", owner_local, attr_local, path)] = [lista de valores]
      - Texto:     out[("text", owner_local, "#text", path)]    = [lista de textos]
    Guarda listas y toma texto aunque existan hijos.
    """
    owner_local = _localname(elem.tag)
    cur_path = f"{path}/{owner_local}" if path else owner_local

    # atributos (normaliza ns/prefijos)
    for k, v in elem.attrib.items():
        if v in (None, ""):
            continue
        if isinstance(k, str) and k.startswith("{"):
            attr_local = k.split("}",1)[1].lower()
        else:
            attr_local = k.split(":",1)[-1].lower()
        if attr_local == "schemalocation":
            continue
        key = ("attr", owner_local, attr_local, cur_path)
        out.setdefault(key, []).append(v)

    # texto
    txt = (elem.text or "").strip()
    if txt:
        keyt = ("text", owner_local, "#text", cur_path)
        out.setdefault(keyt, []).append(txt)

    for ch in list(elem):
        _walk_collect_simple_values(ch, out, cur_path)

def parse_addenda_xml_values(path_or_xml_tree):
    """Devuelve diccionario de valores simples para prellenar el UI."""
    if isinstance(path_or_xml_tree, ET.ElementTree):
        tree = path_or_xml_tree
    else:
        tree = ET.parse(path_or_xml_tree)
    root = tree.getroot()

    # CFDI → entrar a Addenda (y elegir si hay varias)
    if _localname(root.tag).lower() == "comprobante":
        base = _elegir_hijo_addenda(root)
        if base is None:
            return {}
    else:
        base = root

    values = {}
    _walk_collect_simple_values(base, values)

    XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
    scl = base.attrib.get(XSI + "schemaLocation") or root.attrib.get(XSI + "schemaLocation")
    ns_uri = base.tag.split('}')[0][1:] if base.tag.startswith("{") else ""
    return {"values": values, "schemaLocation": scl, "ns_uri": ns_uri}

# =============== Helper índice n-ésimo ===============
def _pick_n(lista, n):
    """Devuelve el elemento n (1-based) o el primero si no alcanza."""
    if not lista:
        return None
    if n <= 0:
        n = 1
    return lista[n-1] if len(lista) >= n else lista[0]

# ================== UI App =========================
class AddendaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Addendados Universal (versátil, 1 archivo)")
        self.xml_path = None
        self.xsd_path = None
        self.cfdi_tree = None
        self.shapes = []
        self.xsd_ns_uri = ""   # targetNamespace detectado

        self.ns_prefix_var = tk.StringVar(value="cli")
        self.ns_uri_var    = tk.StringVar(value="")
        self.root_elem_name= tk.StringVar(value="")
        self.prefill_index_var = tk.IntVar(value=1)  # índice 1-based para ocurrencias

        self._cfdi_ctx      = {}
        self._entry_widgets = []  # [(entry, kind, owner_name)]
        self._field_names   = set()

        self._auto_rules = {}     # reglas inferidas para este XSD
        self._cache = load_cache()

        self._build_ui()

    # --------------- UI Build -----------------------
    def _build_ui(self):
        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Abrir CFDI XML...", command=self.abrir_cfdi)
        filem.add_command(label="Cargar XSD (archivo)...", command=self.cargar_xsd)
        filem.add_command(label="Cargar XSD desde URL...", command=self.cargar_xsd_url)
        filem.add_command(label="Tomar XSD desde schemaLocation del XML", command=self.cargar_xsd_desde_schemaLocation)
        filem.add_separator()
        filem.add_command(label="Importar Addenda desde XML (prefill)...", command=self.prefill_addenda_desde_xml)
        filem.add_command(label="Adjuntar Addenda desde XML (directo)...", command=self.adjuntar_addenda_desde_xml)
        filem.add_separator()
        filem.add_command(label="Salir", command=self.root.quit)
        menubar.add_cascade(label="Archivo", menu=filem)

        tools = tk.Menu(menubar, tearoff=0)
        tools.add_command(label="Autollenar desde CFDI", command=self.autollenar_desde_cfdi)
        menubar.add_cascade(label="Herramientas", menu=tools)

        self.root.config(menu=menubar)

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="NS prefix:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(top, textvariable=self.ns_prefix_var, width=8).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(top, text="NS URI:").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(top, textvariable=self.ns_uri_var, width=40).grid(row=0, column=3, sticky="w", padx=5, pady=2)

        ttk.Label(top, text="Elemento raíz:").grid(row=0, column=4, sticky="e", padx=5, pady=2)
        ttk.Entry(top, textvariable=self.root_elem_name, width=20).grid(row=0, column=5, sticky="w", padx=5, pady=2)

        ttk.Label(top, text="Prefill índice:").grid(row=0, column=6, sticky="e", padx=5, pady=2)
        tk.Spinbox(top, from_=1, to=999, textvariable=self.prefill_index_var, width=5).grid(row=0, column=7, sticky="w", padx=5, pady=2)

        hint = ttk.Label(top, text="Carga el XSD que toque (Soriana, Walmart, etc.) y dale prefill/adjuntar. Simple y sin drama.")
        hint.grid(row=1, column=0, columnspan=8, sticky="w", padx=5, pady=(0,8))

        # zona scroll form
        self.canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0)
        self.form_frame = ttk.Frame(self.canvas)
        self.vsb = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_frame = self.canvas.create_window((0,0), window=self.form_frame, anchor="nw")

        self.form_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Previsualizar (valida XSD)", command=self.previsualizar).pack(side="left")
        ttk.Button(bottom, text="Guardar Addenda en CFDI...", command=self.guardar_definitivo).pack(side="right")

        self._render_placeholder()

    # --------------- Scroll helpers -----------------
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _render_placeholder(self):
        for w in self.form_frame.winfo_children():
            w.destroy()
        self._entry_widgets.clear()
        self._field_names.clear()
        ttk.Label(self.form_frame, text="Carga un CFDI y su XSD para empezar.",
                  font=("Segoe UI", 11, "italic")).pack(pady=20)

    # ---------------- Archivo -----------------------
    def abrir_cfdi(self):
        path = filedialog.askopenfilename(title="Abrir CFDI XML",
                                          filetypes=[("XML CFDI", "*.xml"), ("Todos", "*.*")])
        if not path:
            return
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            if not (root.tag.endswith("Comprobante")):
                messagebox.showwarning("Ojo", "El XML no parece ser un CFDI válido (no se encontró 'Comprobante').")
            self.cfdi_tree = tree
            self.xml_path = path
            self._cfdi_ctx = extract_cfdi_context(root)
            messagebox.showinfo("Listo", os.path.basename(path))
        except Exception as e:
            messagebox.showerror("Error al abrir CFDI", f"Ocurrió un problema al leer el XML:\n{e}")

    def cargar_xsd(self):
        path = filedialog.askopenfilename(title="Cargar XSD de Addenda",
                                          filetypes=[("XSD", "*.xsd"), ("Todos", "*.*")])
        if not path:
            return
        try:
            real_path = cargar_xsd_desde_fuente(path)
            self._post_carga_xsd(real_path)
        except Exception as e:
            messagebox.showerror("Error al cargar XSD", str(e))

    def cargar_xsd_url(self):
        url_win = tk.Toplevel(self.root)
        url_win.title("Cargar XSD desde URL")
        frm = ttk.Frame(url_win, padding=10); frm.pack(fill="both", expand=True)
        var = tk.StringVar()
        ttk.Label(frm, text="URL del XSD (http/https):").pack(anchor="w")
        ttk.Entry(frm, textvariable=var, width=60).pack(fill="x", pady=6)
        def do():
            url = var.get().strip()
            if not url:
                messagebox.showinfo("Falta URL", "Escribe la URL del XSD.")
                return
            try:
                local = cargar_xsd_desde_fuente(url)
                self._post_carga_xsd(local)
                url_win.destroy()
            except Exception as e:
                messagebox.showerror("Error al descargar XSD", str(e))
        ttk.Button(frm, text="Cargar", command=do).pack(anchor="e")

    def cargar_xsd_desde_schemaLocation(self):
        if not self.cfdi_tree:
            messagebox.showinfo("Sin CFDI", "Primero abre un CFDI XML.")
            return
        root = self.cfdi_tree.getroot()
        addenda = root.find(CFDI + "Addenda")
        if addenda is None or len(list(addenda)) == 0:
            messagebox.showinfo("Sin Addenda", "Este CFDI no tiene Addenda todavía.")
            return
        XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
        objetivo = list(addenda)[0]
        scl = objetivo.attrib.get(XSI + "schemaLocation")
        if not scl:
            messagebox.showinfo("Sin schemaLocation", "El elemento de Addenda no declara 'xsi:schemaLocation'.")
            return
        partes = scl.split()
        url = partes[1] if len(partes) >= 2 else None
        if not url or not _es_url(url):
            messagebox.showwarning("No válido", f"No se pudo obtener una URL válida del schemaLocation:\n{scl}")
            return
        try:
            local = cargar_xsd_desde_fuente(url)
            self._post_carga_xsd(local)
        except Exception as e:
            messagebox.showerror("Error al obtener XSD", str(e))

    def _post_carga_xsd(self, xsd_local_path: str):
        self.xsd_path = xsd_local_path
        self.xsd_ns_uri = parse_xsd_target_namespace(self.xsd_path) or ""
        if not self.ns_uri_var.get().strip() and self.xsd_ns_uri:
            self.ns_uri_var.set(self.xsd_ns_uri)
        elif self.xsd_ns_uri and self.ns_uri_var.get().strip() and self.ns_uri_var.get().strip() != self.xsd_ns_uri:
            if messagebox.askyesno(
                "Namespace distinto",
                f"El XSD trae targetNamespace:\n  {self.xsd_ns_uri}\n"
                f"y estás usando:\n  {self.ns_uri_var.get().strip()}\n\n"
                "¿Usar el namespace del XSD?"
            ):
                self.ns_uri_var.set(self.xsd_ns_uri)
        self._parsear_xsd_y_render()

    def _parsear_xsd_y_render(self):
        if not self.xsd_path:
            return
        try:
            root_name = self.root_elem_name.get().strip() or None
            self.shapes = parse_xsd(self.xsd_path, root_element_name=root_name)
            if not self.shapes:
                raise RuntimeError("No se encontraron elementos en el XSD (checa 'Elemento raíz').")
            self._render_form()

            # reglas cache/inferencia
            key = xsd_fingerprint(self.xsd_path)
            cached = self._cache.get(key)
            if isinstance(cached, dict) and cached:
                self._auto_rules = cached
            else:
                self._auto_rules = build_autofill_rules_from_xsd(self.xsd_path, root_element_name=root_name)
                self._cache[key] = self._auto_rules
                save_cache(self._cache)

            if self._cfdi_ctx:
                self.autollenar_desde_cfdi()
        except Exception as e:
            messagebox.showerror("Error XSD", f"Problema al analizar el XSD:\n{e}")

    # ------------- Render dinámico ------------------
    def _add_instance_ui(self, parent, shape):
        inst_frame = ttk.Frame(parent, relief="groove", padding=6)
        inst_frame.pack(fill="x", pady=4)

        def eliminar():
            inst_frame.destroy()

        head = ttk.Frame(inst_frame)
        head.pack(fill="x")
        ttk.Label(head, text=shape["name"], font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(head, text="Eliminar", command=eliminar).pack(side="right")

        # Atributos raíz
        if shape.get("attributes"):
            atf = ttk.LabelFrame(inst_frame, text="Atributos")
            atf.pack(fill="x", padx=4, pady=4)
            for a in shape["attributes"]:
                row = ttk.Frame(atf); row.pack(fill="x", padx=2, pady=2)
                ttk.Label(row, text=f'{a["name"]}{" *" if a.get("use")=="required" else ""}:', width=24).pack(side="left")
                ent = ttk.Entry(row)
                ent.pack(side="left", fill="x", expand=True)
                if a.get("fixed") is not None:
                    ent.insert(0, a["fixed"])
                elif a.get("default") is not None:
                    ent.insert(0, a["default"])
                ent._field_meta = {
                    "kind":"attr", "name": a["name"], "required": a.get("use")=="required",
                    "owner": shape["name"], "owner_path": shape.get("path") or shape["name"]
                }
                self._entry_widgets.append((ent, "attr", shape["name"]))

        # Hijos
        for ch in shape.get("children", []):
            grp = ttk.LabelFrame(inst_frame, text=ch["name"])
            grp.pack(fill="x", padx=4, pady=4)

            # Atributos directos
            if ch.get("attributes"):
                atf = ttk.LabelFrame(grp, text="Atributos")
                atf.pack(fill="x", padx=4, pady=4)
                for a in ch["attributes"]:
                    row = ttk.Frame(atf); row.pack(fill="x", padx=2, pady=2)
                    ttk.Label(row, text=f'{a["name"]}{" *" if a.get("use")=="required" else ""}:', width=24).pack(side="left")
                    ent = ttk.Entry(row)
                    ent.pack(side="left", fill="x", expand=True)
                    if a.get("fixed") is not None:
                        ent.insert(0, a["fixed"])
                    elif a.get("default") is not None:
                        ent.insert(0, a["default"])
                    ent._field_meta = {
                        "kind":"attr", "name": a["name"], "required": a.get("use")=="required",
                        "owner": ch["name"], "owner_path": ch.get("path") or f"{shape.get('path')}/{ch['name']}"
                    }
                    self._entry_widgets.append((ent, "attr", ch["name"]))

            # Elemento simple (texto)
            if ch.get("is_simple") and not ch.get("attributes") and not ch.get("children"):
                row = ttk.Frame(grp); row.pack(fill="x", padx=2, pady=2)
                ttk.Label(row, text="Valor:", width=24).pack(side="left")
                ent = ttk.Entry(row)
                ent.pack(side="left", fill="x", expand=True)
                ent._field_meta = {
                    "kind":"text", "name":"#text", "required": False,
                    "owner": ch["name"], "owner_path": ch.get("path") or f"{shape.get('path')}/{ch['name']}"
                }
                self._entry_widgets.append((ent, "text", ch["name"]))

            # Nietos
            if ch.get("children"):
                rep_wrap = ttk.Frame(grp); rep_wrap.pack(fill="x", padx=4, pady=4)
                self._add_child_instance_ui(rep_wrap, ch)
                if ch.get("maxOccurs","1") != "1":
                    ttk.Button(grp, text="+ Añadir otro",
                               command=lambda w=rep_wrap, s=ch: self._add_child_instance_ui(w, s)
                               ).pack(anchor="w", padx=6, pady=(0,6))

    def _add_child_instance_ui(self, parent, shape):
        inst = ttk.Frame(parent, relief="ridge", padding=6)
        inst.pack(fill="x", pady=4)
        head = ttk.Frame(inst); head.pack(fill="x")
        ttk.Label(head, text=f"Instancia de {shape['name']}", font=("Segoe UI", 9, "italic")).pack(side="left")
        ttk.Button(head, text="Eliminar", command=inst.destroy).pack(side="right")

        for gg in shape.get("children", []):
            sub = ttk.LabelFrame(inst, text=gg["name"])
            sub.pack(fill="x", padx=4, pady=4)
            if gg.get("attributes"):
                atf = ttk.LabelFrame(sub, text="Atributos")
                atf.pack(fill="x", padx=4, pady=4)
                for a in gg["attributes"]:
                    row = ttk.Frame(atf); row.pack(fill="x", padx=2, pady=2)
                    ttk.Label(row, text=f'{a["name"]}{" *" if a.get("use")=="required" else ""}:', width=24).pack(side="left")
                    ent = ttk.Entry(row)
                    ent.pack(side="left", fill="x", expand=True)
                    if a.get("fixed") is not None:
                        ent.insert(0, a["fixed"])
                    elif a.get("default") is not None:
                        ent.insert(0, a["default"])
                    ent._field_meta = {
                        "kind":"attr", "name": a["name"], "required": a.get("use")=="required",
                        "owner": gg["name"], "owner_path": gg.get("path") or gg["name"]
                    }
                    self._entry_widgets.append((ent, "attr", gg["name"]))
            if gg.get("is_simple") and not gg.get("attributes") and not gg.get("children"):
                row = ttk.Frame(sub); row.pack(fill="x", padx=2, pady=2)
                ttk.Label(row, text="Valor:", width=24).pack(side="left")
                ent = ttk.Entry(row)
                ent.pack(side="left", fill="x", expand=True)
                ent._field_meta = {
                    "kind":"text", "name":"#text", "required": False,
                    "owner": gg["name"], "owner_path": gg.get("path") or gg["name"]
                }
                self._entry_widgets.append((ent, "text", gg["name"]))

            for bis in gg.get("children", []):
                bisf = ttk.LabelFrame(sub, text=bis["name"])
                bisf.pack(fill="x", padx=4, pady=4)
                if bis.get("attributes"):
                    atf = ttk.LabelFrame(bisf, text="Atributos")
                    atf.pack(fill="x", padx=4, pady=4)
                    for a in bis.get("attributes", []):
                        row = ttk.Frame(atf); row.pack(fill="x", padx=2, pady=2)
                        ttk.Label(row, text=f'{a["name"]}{" *" if a.get("use")=="required" else ""}:', width=24).pack(side="left")
                        ent = ttk.Entry(row)
                        ent.pack(side="left", fill="x", expand=True)
                        if a.get("fixed") is not None:
                            ent.insert(0, a["fixed"])
                        elif a.get("default") is not None:
                            ent.insert(0, a["default"])
                        ent._field_meta = {
                            "kind":"attr", "name": a["name"], "required": a.get("use")=="required",
                            "owner": bis["name"], "owner_path": bis.get("path") or bis["name"]
                        }
                        self._entry_widgets.append((ent, "attr", bis["name"]))
                if bis.get("is_simple") and not bis.get("attributes") and not bis.get("children"):
                    row = ttk.Frame(bisf); row.pack(fill="x", padx=2, pady=2)
                    ttk.Label(row, text="Valor:", width=24).pack(side="left")
                    ent = ttk.Entry(row)
                    ent.pack(side="left", fill="x", expand=True)
                    ent._field_meta = {
                        "kind":"text", "name":"#text", "required": False,
                        "owner": bis["name"], "owner_path": bis.get("path") or bis["name"]
                    }
                    self._entry_widgets.append((ent, "text", bis["name"]))

    def _render_form(self):
        for w in self.form_frame.winfo_children():
            w.destroy()
        self._entry_widgets.clear()
        self._field_names.clear()

        ttk.Label(self.form_frame, text=f"XSD: {os.path.basename(self.xsd_path) if self.xsd_path else '—'}",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0,8))

        for top_shape in self.shapes:
            section = ttk.LabelFrame(self.form_frame, text=top_shape["name"] or "Elemento")
            section.pack(fill="x", padx=4, pady=6)
            wrap = ttk.Frame(section)
            wrap.pack(fill="x", padx=6, pady=6)
            self._add_instance_ui(wrap, top_shape)
            if top_shape.get("maxOccurs","1") != "1":
                ttk.Button(section, text="+ Añadir otro",
                           command=lambda w=wrap, s=top_shape: self._add_instance_ui(w, s)).pack(anchor="w", padx=6, pady=(0,6))

    # ------------- Autollenado (desde CFDI) -------------
    def autollenar_desde_cfdi(self):
        if not self._cfdi_ctx:
            if not self.cfdi_tree:
                messagebox.showinfo("Sin CFDI", "Primero carga un CFDI.")
                return
            self._cfdi_ctx = extract_cfdi_context(self.cfdi_tree.getroot())

        count = 0
        for ent, kind, owner in self._entry_widgets:
            try:
                if ent.get().strip():
                    continue
                meta = getattr(ent, "_field_meta", {})
                logical_name = meta.get("name") if kind == "attr" else owner

                cfdi_key = self._auto_rules.get(logical_name) or self._auto_rules.get((logical_name or "").lower())
                if cfdi_key:
                    val = self._cfdi_ctx.get(cfdi_key)
                    if val:
                        ent.insert(0, val); count += 1; continue

                val = guess_autofill_value_by_name(logical_name, self._cfdi_ctx)
                if val:
                    ent.insert(0, val); count += 1
            except Exception:
                pass
        messagebox.showinfo("Autollenado", f"Campos autollenados: {count}")

    # ---------- Recolección + validación UI ----------
    def _collect_instances(self):
        roots = []
        for sect in self.form_frame.winfo_children():
            if not isinstance(sect, ttk.LabelFrame):
                continue
            title = sect.cget("text")
            wrap = None
            for ch in sect.winfo_children():
                if isinstance(ch, ttk.Frame):
                    wrap = ch; break
            if not wrap:
                continue
            for inst_frame in [w for w in wrap.winfo_children() if isinstance(w, ttk.Frame)]:
                root_inst = {"name": title, "attributes":{}, "children":[]}
                for sub in inst_frame.winfo_children():
                    if isinstance(sub, ttk.LabelFrame) and sub.cget("text") == "Atributos":
                        for row in sub.winfo_children():
                            for w in row.winfo_children():
                                if hasattr(w, "_field_meta") and getattr(w, "get", None):
                                    meta = w._field_meta; val = w.get().strip()
                                    if meta.get("kind") == "attr":
                                        root_inst["attributes"][meta["name"]] = val
                        continue
                    if isinstance(sub, ttk.LabelFrame) and sub.cget("text") not in ("Atributos",):
                        child_inst = {"name": sub.cget("text"), "attributes":{}, "children":[]}
                        text_value = ""
                        for maybe in sub.winfo_children():
                            if isinstance(maybe, ttk.LabelFrame) and maybe.cget("text") == "Atributos":
                                for row in maybe.winfo_children():
                                    for w in row.winfo_children():
                                        if hasattr(w, "_field_meta") and getattr(w, "get", None):
                                            meta = w._field_meta; val = w.get().strip()
                                            if meta.get("kind") == "attr":
                                                child_inst["attributes"][meta["name"]] = val
                            if isinstance(maybe, ttk.Frame):
                                for w in maybe.winfo_children():
                                    if hasattr(w, "_field_meta") and w._field_meta.get("kind") == "text":
                                        text_value = w.get().strip()
                                for inst in [x for x in maybe.winfo_children() if isinstance(x, ttk.Frame)]:
                                    for bis in inst.winfo_children():
                                        if isinstance(bis, ttk.LabelFrame):
                                            bis_inst = {"name": bis.cget("text"), "attributes":{}, "children":[]}
                                            bis_text = ""
                                            for atsub in bis.winfo_children():
                                                if isinstance(atsub, ttk.LabelFrame) and atsub.cget("text")=="Atributos":
                                                    for row in atsub.winfo_children():
                                                        for w in row.winfo_children():
                                                            if hasattr(w, "_field_meta") and getattr(w, "get", None):
                                                                meta = w._field_meta; val = w.get().strip()
                                                                if meta.get("kind")=="attr":
                                                                    bis_inst["attributes"][meta["name"]] = val
                                                if isinstance(atsub, ttk.Frame):
                                                    for w in atsub.winfo_children():
                                                        if hasattr(w, "_field_meta") and w._field_meta.get("kind")=="text":
                                                            bis_text = w.get().strip()
                                            if bis_text:
                                                bis_inst["text"] = bis_text
                                            if bis_inst.get("attributes") or bis_inst.get("text"):
                                                child_inst["children"].append(bis_inst)
                        if text_value:
                            child_inst["text"] = text_value
                        if child_inst.get("attributes") or child_inst.get("children") or child_inst.get("text"):
                            root_inst["children"].append(child_inst)
                roots.append(root_inst)
        return {"roots": roots}

    def _validate_required_ui(self):
        faltan = []
        for ent_frame in self.form_frame.winfo_children():
            for w in getattr(ent_frame, "winfo_children", lambda:[])():
                self._validate_recurse(w, faltan)
        if faltan:
            messagebox.showwarning("Campos obligatorios", "Faltan: " + ", ".join(sorted(set(faltan))))
            return False
        return True

    def _validate_recurse(self, widget, faltan):
        if hasattr(widget, "_field_meta"):
            meta = widget._field_meta
            if meta.get("required") and not widget.get().strip():
                faltan.append(meta.get("name") if meta.get("kind")=="attr" else meta.get("owner"))
        for ch in getattr(widget, "winfo_children", lambda:[])():
            self._validate_recurse(ch, faltan)

    # ----------------- Acciones ----------------------
    def previsualizar(self):
        if not self.cfdi_tree or not self.xsd_path:
            messagebox.showinfo("Falta info", "Carga CFDI y XSD primero.")
            return
        if not self._validate_required_ui():
            return
        ns_cfg = {"prefix": self.ns_prefix_var.get().strip() or "cli",
                  "uri": (self.ns_uri_var.get().strip() or self.xsd_ns_uri)}
        preview_tree = ET.ElementTree(self.cfdi_tree.getroot())
        try:
            construir_addenda(preview_tree.getroot(), self._collect_instances(), ns_cfg=ns_cfg)
            ok, errs = validate_addenda_subtree_with_xsd(preview_tree.getroot(), self.xsd_path, ns_uri=ns_cfg["uri"])
            if not ok:
                if HAS_LXML:
                    messagebox.showerror("XSD no válido", f"Errores de esquema:\n{errs}")
                    return
                else:
                    messagebox.showwarning("Validación deshabilitada",
                        "Instala lxml para validar contra XSD: pip install lxml")
            xml_text = generate_preview(preview_tree)
        except Exception as e:
            messagebox.showerror("Error", f"Al construir/validar Addenda:\n{e}")
            return

        top = tk.Toplevel(self.root); top.title("Previsualización")
        txt = tk.Text(top, wrap="none", height=30, width=120)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", xml_text); txt.configure(state="disabled")

    def guardar_definitivo(self):
        if not self.cfdi_tree or not self.xsd_path:
            messagebox.showinfo("Falta info", "Carga CFDI y XSD primero.")
            return
        if not self._validate_required_ui():
            return
        ns_cfg = {"prefix": self.ns_prefix_var.get().strip() or "cli",
                  "uri": (self.ns_uri_var.get().strip() or self.xsd_ns_uri)}
        try:
            construir_addenda(self.cfdi_tree.getroot(), self._collect_instances(), ns_cfg=ns_cfg)
            ok, errs = validate_addenda_subtree_with_xsd(self.cfdi_tree.getroot(), self.xsd_path, ns_uri=self.ns_uri_var.get().strip() or self.xsd_ns_uri)
            if not ok:
                if HAS_LXML:
                    messagebox.showerror("XSD no válido", f"Errores de esquema:\n{errs}")
                    return
                else:
                    messagebox.showwarning("Validación deshabilitada",
                        "Instala lxml para validar contra XSD: pip install lxml")
            pretty_xml(self.cfdi_tree)
            out_path = filedialog.asksaveasfilename(
                title="Guardar CFDI con Addenda",
                defaultextension=".xml",
                filetypes=[("XML", "*.xml")]
            )
            if not out_path:
                return
            self.cfdi_tree.write(out_path, encoding="utf-8", xml_declaration=True)
            messagebox.showinfo("Guardado", f"Se guardó el CFDI con Addenda en:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error al guardar", f"Ocurrió un problema al guardar:\n{e}")

    # --------- Addenda desde XML: PREFILL ----------
    def prefill_addenda_desde_xml(self):
        path = filedialog.askopenfilename(title="Seleccionar XML de Addenda (o CFDI con Addenda)",
                                          filetypes=[("XML", "*.xml"), ("Todos", "*.*")])
        if not path:
            return
        try:
            info = parse_addenda_xml_values(path)
            if not info:
                messagebox.showinfo("Sin datos", "No se encontraron valores simples en la Addenda.")
                return
            vals = info.get("values", {})
            if not vals:
                messagebox.showinfo("Sin datos", "No se encontraron valores simples en la Addenda.")
                return

            # Sugerir namespace si no hay XSD cargado
            if not self.xsd_path and info.get("ns_uri"):
                ns_from_xml = info["ns_uri"]
                if not self.ns_uri_var.get().strip():
                    self.ns_uri_var.set(ns_from_xml)
                elif self.ns_uri_var.get().strip() != ns_from_xml:
                    if messagebox.askyesno(
                        "Namespace distinto",
                        f"La Addenda del XML usa:\n  {ns_from_xml}\n"
                        f"y la UI tiene:\n  {self.ns_uri_var.get().strip()}\n\n"
                        "¿Usar el namespace detectado?"
                    ):
                        self.ns_uri_var.set(ns_from_xml)

            # Prefill: por ruta exacta o por nombre, con índice n
            count = 0
            n = max(1, int(self.prefill_index_var.get() or 1))
            for ent, kind, owner in self._entry_widgets:
                if ent.get().strip():
                    continue
                meta = getattr(ent, "_field_meta", {})
                owner_local = owner
                owner_path  = meta.get("owner_path") or owner_local

                if kind == "attr":
                    attr_local = (meta.get("name") or "").lower()
                    key_path = ("attr", owner_local, attr_local, owner_path)
                    key_name = None
                    for k in vals.keys():
                        if len(k)==4 and k[0]=="attr" and k[1]==owner_local and k[2]==attr_local:
                            key_name = k; break
                    picked = None
                    if key_path in vals and vals[key_path]:
                        picked = _pick_n(vals[key_path], n)
                    elif key_name and vals.get(key_name):
                        picked = _pick_n(vals[key_name], n)
                    if picked:
                        ent.insert(0, picked); count += 1
                else:  # text
                    key_path = ("text", owner_local, "#text", owner_path)
                    key_name = None
                    for k in vals.keys():
                        if len(k)==4 and k[0]=="text" and k[1]==owner_local:
                            key_name = k; break
                    picked = None
                    if key_path in vals and vals[key_path]:
                        picked = _pick_n(vals[key_path], n)
                    elif key_name and vals.get(key_name):
                        picked = _pick_n(vals[key_name], n)
                    if picked:
                        ent.insert(0, picked); count += 1

            messagebox.showinfo("Prefill", f"Índice usado: #{self.prefill_index_var.get()} • Campos llenados: {count}")

            # Ofrecer cargar XSD si trae schemaLocation
            scl = info.get("schemaLocation")
            if scl:
                partes = scl.split()
                url = partes[1] if len(partes) >= 2 else None
                if url:
                    if messagebox.askyesno(
                        "XSD detectado",
                        f"Se detectó schemaLocation en la Addenda:\n{url}\n\n¿Cargar ese XSD ahora?"
                    ):
                        try:
                            local = cargar_xsd_desde_fuente(url)
                            self._post_carga_xsd(local)
                        except Exception as e:
                            messagebox.showerror("Error al cargar XSD", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer la Addenda desde el XML:\n{e}")

    # --------- Addenda desde XML: ADJUNTAR DIRECTO ----------
    def adjuntar_addenda_desde_xml(self):
        if not self.cfdi_tree:
            messagebox.showinfo("Sin CFDI", "Primero abre un CFDI XML para adjuntar la Addenda.")
            return
        path = filedialog.askopenfilename(title="Seleccionar XML de Addenda (o CFDI con Addenda)",
                                          filetypes=[("XML", "*.xml"), ("Todos", "*.*")])
        if not path:
            return
        try:
            tree = ET.parse(path)
            r = tree.getroot()
            if _localname(r.tag).lower() == "comprobante":
                base = _elegir_hijo_addenda(r)
                if base is None:
                    messagebox.showinfo("Sin Addenda", "El XML seleccionado no contiene Addenda.")
                    return
                insert_me = base
            else:
                insert_me = r

            ns_uri = insert_me.tag.split('}')[0][1:] if isinstance(insert_me.tag, str) and insert_me.tag.startswith("{") else ""
            root_cfdi = self.cfdi_tree.getroot()
            addenda = root_cfdi.find(CFDI + "Addenda")
            if addenda is None:
                addenda = ET.SubElement(root_cfdi, CFDI + "Addenda")

            # elimina del mismo namespace para no duplicar vendor
            to_remove = []
            for ch in list(addenda):
                if ns_uri and isinstance(ch.tag, str) and ch.tag.startswith("{"+ns_uri+"}"):
                    to_remove.append(ch)
            for ch in to_remove:
                addenda.remove(ch)

            def _deep_copy(elem):
                new = ET.Element(elem.tag, attrib=dict(elem.attrib))
                new.text = elem.text
                new.tail = elem.tail
                for c in list(elem):
                    new.append(_deep_copy(c))
                return new

            addenda.append(_deep_copy(insert_me))

            if ns_uri:
                if not self.ns_uri_var.get().strip():
                    self.ns_uri_var.set(ns_uri)
                elif self.ns_uri_var.get().strip() != ns_uri:
                    if messagebox.askyesno(
                        "Namespace distinto",
                        f"La Addenda adjuntada usa:\n  {ns_uri}\n"
                        f"y la UI tiene:\n  {self.ns_uri_var.get().strip()}\n\n"
                        "¿Usar el namespace de la Addenda?"
                    ):
                        self.ns_uri_var.set(ns_uri)

            if self.xsd_path:
                ok, errs = validate_addenda_subtree_with_xsd(root_cfdi, self.xsd_path, ns_uri=self.ns_uri_var.get().strip())
                if ok:
                    messagebox.showinfo("Addenda", "Se adjuntó y validó contra el XSD. Todo bien.")
                else:
                    messagebox.showerror("Validación XSD", f"Adjuntada, pero NO valida:\n{errs}")
            else:
                messagebox.showinfo("Addenda", "Adjuntada al CFDI. Puedes cargar el XSD para validarla.")

            # Prefill inmediato desde ese XML (usando el índice)
            try:
                info = parse_addenda_xml_values(path)
                vals = info.get("values", {})
                n = max(1, int(self.prefill_index_var.get() or 1))
                count = 0
                for ent, kind, owner in self._entry_widgets:
                    if ent.get().strip(): 
                        continue
                    meta = getattr(ent, "_field_meta", {})
                    owner_local = owner
                    owner_path  = meta.get("owner_path") or owner_local
                    if kind == "attr":
                        attr_local = (meta.get("name") or "").lower()
                        key_path = ("attr", owner_local, attr_local, owner_path)
                        key_name = None
                        for k in vals.keys():
                            if len(k)==4 and k[0]=="attr" and k[1]==owner_local and k[2]==attr_local:
                                key_name = k; break
                        picked = None
                        if key_path in vals and vals[key_path]:
                            picked = _pick_n(vals[key_path], n)
                        elif key_name and vals.get(key_name):
                            picked = _pick_n(vals[key_name], n)
                        if picked:
                            ent.insert(0, picked); count += 1
                    else:
                        key_path = ("text", owner_local, "#text", owner_path)
                        key_name = None
                        for k in vals.keys():
                            if len(k)==4 and k[0]=="text" and k[1]==owner_local:
                                key_name = k; break
                        picked = None
                        if key_path in vals and vals[key_path]:
                            picked = _pick_n(vals[key_path], n)
                        elif key_name and vals.get(key_name):
                            picked = _pick_n(vals[key_name], n)
                        if picked:
                            ent.insert(0, picked); count += 1
                if count:
                    messagebox.showinfo("Prefill", f"Índice usado: #{self.prefill_index_var.get()} • Campos llenados: {count}")
            except Exception:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo adjuntar la Addenda desde el XML:\n{e}")

# ================== Main ===========================
def main():
    root = tk.Tk()
    app = AddendaApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
