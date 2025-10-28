# features/catalogs.py
# -*- coding: utf-8 -*-
import ctypes

def _bind_any(sdk, *names):
    for n in names:
        fn = getattr(sdk.dll, n, None)
        if fn: return fn
    raise AttributeError(names[0])

def _read_field(fn_read, name: str, size: int = 512) -> str:
    buf = ctypes.create_string_buffer(size)
    try:
        fn_read(name.encode("latin-1"), buf, size)
        return buf.value.decode("latin-1", "ignore").strip()
    except Exception:
        return ""

def _enum_generic_any(sdk, first_names, next_names, read_names,
                      field_nombre: str, field_codigo: str):
    res = []
    try:
        f_first = _bind_any(sdk, *first_names)
        f_next  = _bind_any(sdk, *next_names)
        f_read  = _bind_any(sdk, *read_names)
    except AttributeError:
        return res
    f_first.restype = f_next.restype = ctypes.c_int
    f_read.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    f_read.restype  = ctypes.c_int
    if f_first() != 0:
        return res
    while True:
        codigo = _read_field(f_read, field_codigo)
        nombre = _read_field(f_read, field_nombre)
        if codigo: res.append({"codigo": codigo, "nombre": nombre})
        if f_next()!=0: break
    return res

def _busca_y_lee(sdk, busca_names, lee_names, codigo_name: str,
                 field_codigo: str, field_nombre: str):
    try:
        f_busca = _bind_any(sdk, *busca_names)
        f_lee   = _bind_any(sdk, *lee_names)
    except AttributeError:
        return None
    f_busca.argtypes = [ctypes.c_char_p]; f_busca.restype  = ctypes.c_int
    f_lee.argtypes   = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    f_lee.restype    = ctypes.c_int

    def ok(code): return code==0
    def busca(code): return ok(f_busca(code.encode("latin-1")))
    def lee():
        return {"codigo": _read_field(f_lee, field_codigo),
                "nombre": _read_field(f_lee, field_nombre)}
    def find(code):
        if not code: return None
        if busca(code):
            out=lee()
            if not out.get("codigo"): out["codigo"]=code
            return out
        return None
    return lambda code: find(code)

class CatalogManager:
    def __init__(self, sdk):
        self.sdk = sdk
        self.conceptos=[]; self.clientes=[]; self.productos=[]
        self.almacenes=[]; self.agentes=[]; self.monedas=[]; self.series=[]; self.proyectos=[]
        self.find_concepto=self.find_cliente=self.find_producto=None
        self.find_almacen=self.find_agente=self.find_moneda=self.find_serie=self.find_proyecto=None

    def load_all(self, logger=print):
        self.conceptos = _enum_generic_any(self.sdk,
            ("fPosPrimerConcepto","fPosPrimerDoctoConcepto","fPosPrimerDocto"),
            ("fPosSiguienteConcepto","fPosSiguienteDoctoConcepto","fPosSiguienteDocto"),
            ("fLeeDatoConcepto","fLeeDatoDoctoConcepto","fLeeDatoDocto"),
            "cNombreConcepto", "cCodConcepto")

        self.clientes  = _enum_generic_any(self.sdk,
            ("fPosPrimerCteProv","fPosPrimerCliente"),
            ("fPosSiguienteCteProv","fPosSiguienteCliente"),
            ("fLeeDatoCteProv","fLeeDatoCliente"),
            "cRazonSocial","cCodigo")

        self.productos = _enum_generic_any(self.sdk,
            ("fPosPrimerProducto",),
            ("fPosSiguienteProducto",),
            ("fLeeDatoProducto",),
            "cNombreProducto","cCodigoProducto")

        self.almacenes = _enum_generic_any(self.sdk,
            ("fPosPrimerAlmacen",),
            ("fPosSiguienteAlmacen",),
            ("fLeeDatoAlmacen",),
            "cNombreAlmacen","cCodigoAlmacen")

        self.agentes   = _enum_generic_any(self.sdk,
            ("fPosPrimerAgente",),
            ("fPosSiguienteAgente",),
            ("fLeeDatoAgente",),
            "cNombreAgente","cCodigoAgente")

        self.monedas   = _enum_generic_any(self.sdk,
            ("fPosPrimerMoneda",),
            ("fPosSiguienteMoneda",),
            ("fLeeDatoMoneda",),
            "cNombreMoneda","cIdMoneda")

        self.series    = _enum_generic_any(self.sdk,
            ("fPosPrimerSerie","fPosPrimerFolio"),
            ("fPosSiguienteSerie","fPosSiguienteFolio"),
            ("fLeeDatoSerie","fLeeDatoFolio"),
            "cNombreSerie","cCodigoSerie")

        self.proyectos = _enum_generic_any(self.sdk,
            ("fPosPrimerProyecto",),
            ("fPosSiguienteProyecto",),
            ("fLeeDatoProyecto",),
            "cNombreProyecto","cCodigoProyecto")

        logger(f"Conceptos: {len(self.conceptos)} | Clientes: {len(self.clientes)} | Productos: {len(self.productos)}")
        logger(f"Almacenes: {len(self.almacenes)} | Agentes: {len(self.agentes)} | Monedas: {len(self.monedas)}")
        logger(f"Series: {len(self.series)} | Proyectos: {len(self.proyectos)}")

        # buscadores directos por código (si no hay lista)
        self.find_concepto = _busca_y_lee(self.sdk,
            ("fBuscaConcepto","fBuscaDoctoConcepto","fBuscaDocto","fBuscaDocumentoConcepto","fBuscaConceptoDocto"),
            ("fLeeDatoConcepto","fLeeDatoDoctoConcepto","fLeeDatoDocto"),
            "cCodConcepto", "cCodConcepto", "cNombreConcepto")

        self.find_cliente = _busca_y_lee(self.sdk,
            ("fBuscaCteProv","fBuscaCliente","fBuscaClientePorCodigo","fBuscaCtePorCodigo"),
            ("fLeeDatoCteProv","fLeeDatoCliente"),
            "cCodigo", "cCodigo", "cRazonSocial")

        self.find_producto = _busca_y_lee(self.sdk, ("fBuscaProducto",), ("fLeeDatoProducto",),
                                          "cCodigoProducto","cCodigoProducto","cNombreProducto")
        self.find_almacen  = _busca_y_lee(self.sdk, ("fBuscaAlmacen",), ("fLeeDatoAlmacen",),
                                          "cCodigoAlmacen","cCodigoAlmacen","cNombreAlmacen")
        self.find_agente   = _busca_y_lee(self.sdk, ("fBuscaAgente",), ("fLeeDatoAgente",),
                                          "cCodigoAgente","cCodigoAgente","cNombreAgente")
        self.find_moneda   = _busca_y_lee(self.sdk, ("fBuscaMoneda",), ("fLeeDatoMoneda",),
                                          "cIdMoneda","cIdMoneda","cNombreMoneda")
        self.find_serie    = _busca_y_lee(self.sdk, ("fBuscaSerie","fBuscaFolio"), ("fLeeDatoSerie","fLeeDatoFolio"),
                                          "cCodigoSerie","cCodigoSerie","cNombreSerie")
        self.find_proyecto = _busca_y_lee(self.sdk, ("fBuscaProyecto",), ("fLeeDatoProyecto",),
                                          "cCodigoProyecto","cCodigoProyecto","cNombreProyecto")

    def get_dict(self):
        return {
            "concepto": self.conceptos,
            "cliente": self.clientes,
            "producto": self.productos,
            "almacen": self.almacenes,
            "agente": self.agentes,
            "moneda": self.monedas,
            "serie": self.series,
            "proyecto": self.proyectos,
        }

def get_next_folio(sdk, cod_concepto: str, serie: str) -> str:
    try:
        fn = getattr(sdk.dll, "fSiguienteFolio")
    except AttributeError:
        return ""
    fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    fn.restype  = ctypes.c_int
    buf = ctypes.create_string_buffer(32)
    try:
        if fn(cod_concepto.encode("latin-1"), (serie or "").encode("latin-1"), buf, 32)==0:
            return buf.value.decode("latin-1","ignore").strip()
    except Exception:
        pass
    return ""
