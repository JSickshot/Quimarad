# -*- coding: utf-8 -*-
from __future__ import annotations
import ctypes

def _bind0(dll, names):
    last=None
    for n in names:
        try:
            fn=getattr(dll,n); fn.restype=ctypes.c_int
            return fn
        except Exception as e: last=e
    raise AttributeError(f"No existe ninguna de: {names} ({last})")

def _bind_reader(dll, bases):
    for nm in [b+"W" for b in bases]:
        try: fn=getattr(dll,nm); fn.restype=ctypes.c_int; return fn,"wide"
        except Exception: pass
    for nm in bases:
        try: fn=getattr(dll,nm); fn.restype=ctypes.c_int; return fn,"ansi"
        except Exception: pass
    raise AttributeError(f"Sin variantes ANSI/Wide para {bases}")

def _arg(mode, s:str):
    return ctypes.c_wchar_p(s) if mode=="wide" else ctypes.c_char_p(s.encode("latin-1","ignore"))

def _read_field(fn, mode, field:str, buflen=1024):
    if mode=="wide":
        buf=ctypes.create_unicode_buffer(buflen)
    else:
        buf=ctypes.create_string_buffer(buflen)
    n = ctypes.c_int(buflen)
    try:
        rc = fn(_arg(mode,field), buf, ctypes.byref(n))
    except (TypeError, ctypes.ArgumentError):
        rc = fn(_arg(mode,field), buf, n.value)
    if rc!=0: return rc,""
    if mode=="wide": return 0, buf.value
    return 0, buf.value.decode("latin-1","ignore")

def _collect(dll, pos_names, next_names, read_names, code_fields, name_fields):
    try:
        f_pos1=_bind0(dll,pos_names); f_next=_bind0(dll,next_names); f_read,mode=_bind_reader(dll,read_names)
    except Exception:
        return []
    items=[]; rc=f_pos1()
    while rc==0:
        code=""; name=""
        for fld in code_fields:
            rc1,val=_read_field(f_read,mode,fld)
            if rc1==0 and val: code=val.strip(); break
        for fld in name_fields:
            rc2,val=_read_field(f_read,mode,fld)
            if rc2==0 and val: name=val.strip(); break
        if code: items.append((code, name))
        rc=f_next()
    return items

# --- Catálogos principales ---
def conceptos(sdk):
    dll=sdk.dll.dll
    return _collect(dll,
        ["fPosPrimerConceptoDocto","fPosPrimerConceptoDocumento"],
        ["fPosSiguienteConceptoDocto","fPosSiguienteConceptoDocumento"],
        ["fLeeDatoConceptoDocto","fLeeDatoConceptoDocumento","fLeeDatoConceptoDoctoW","fLeeDatoConceptoDocumentoW"],
        ["cCodigoConcepto","cCodConcepto","cIdConcepto","cCodigo"],
        ["cNombreConcepto","cNombre"]
    )

def clientes(sdk):
    dll=sdk.dll.dll
    return _collect(dll,
        ["fPosPrimerCteProv","fPosPrimerCliente"],
        ["fPosSiguienteCteProv","fPosSiguienteCliente"],
        ["fLeeDatoCteProv","fLeeDatoCliente"],
        ["cCodigoCliente","cCodigoCteProv","cCodigo"],
        ["cRazonSocial","cNombreCliente","cNombre"]
    )

def productos(sdk):
    dll=sdk.dll.dll
    return _collect(dll,
        ["fPosPrimerProducto"],["fPosSiguienteProducto"],["fLeeDatoProducto"],
        ["cCodigoProducto","cCodigo"],["cNombreProducto","cNombre"]
    )

def almacenes(sdk):
    dll=sdk.dll.dll
    return _collect(dll,
        ["fPosPrimerAlmacen"],["fPosSiguienteAlmacen"],["fLeeDatoAlmacen"],
        ["cCodigoAlmacen","cCodigo"],["cNombreAlmacen","cNombre"]
    )

def agentes(sdk):
    dll=sdk.dll.dll
    return _collect(dll,
        ["fPosPrimerAgente"],["fPosSiguienteAgente"],["fLeeDatoAgente"],
        ["cCodigoAgente","cCodigo"],["cNombreAgente","cNombre"]
    )

def monedas(sdk):
    dll=sdk.dll.dll
    items=_collect(dll,
        ["fPosPrimerMoneda"],["fPosSiguienteMoneda"],["fLeeDatoMoneda"],
        ["cIdMoneda","cNumero","cCodigo"],["cNombreMoneda","cDescripcion","cNombre"]
    )
    return [(c, n or (c=="1" and "Peso Mexicano") or (c=="2" and "Dólar Americano") or f"Moneda {c}") for c,n in items]

def proyectos(sdk):
    dll=sdk.dll.dll
    return _collect(dll,
        ["fPosPrimerProyecto"],["fPosSiguienteProyecto"],["fLeeDatoProyecto"],
        ["cCodigoProyecto","cCodigo"],["cNombreProyecto","cNombre"]
    )

def series(sdk):
    dll=sdk.dll.dll
    items=_collect(dll,
        ["fPosPrimerSerie","fPosPrimerSerieDoc"],["fPosSiguienteSerie","fPosSiguienteSerieDoc"],
        ["fLeeDatoSerie","fLeeDatoSerieDoc"],
        ["cIdSerie","cCodigoSerie","cSerie","cCodigo"],
        ["cNombreSerie","cNombre","cDescripcion"]
    )
    if items: return items
    return _collect(dll,
        ["fPosPrimerFolio"],["fPosSiguienteFolio"],["fLeeDatoFolio"],
        ["cIdSerie","cSerie","cCodigo"],["cNombreSerie","cNombre","cDescripcion"]
    )

# --- Información dependiente del concepto ---
def concepto_moneda_default(sdk, cod_concepto: str) -> str | None:
    """
    Intenta leer la 'moneda default' del concepto. Si no hay campo legible,
    regresa None y la UI caerá en Peso Mexicano (1).
    """
    dll = sdk.dll.dll
    try:
        f_pos1=_bind0(dll,["fPosPrimerConceptoDocto","fPosPrimerConceptoDocumento"])
        f_next=_bind0(dll,["fPosSiguienteConceptoDocto","fPosSiguienteConceptoDocumento"])
        f_read,mode=_bind_reader(dll,["fLeeDatoConceptoDocto","fLeeDatoConceptoDocumento"])
    except Exception:
        return None

    rc=f_pos1()
    while rc==0:
        rc1,val=_read_field(f_read,mode,"cCodConcepto")
        if rc1==0 and val.strip()==cod_concepto.strip():
            # probar varios posibles alias de campo
            for fld in ("cIdMoneda","cNumeroMoneda","cMoneda","cMonedaId","cIdMonedaDefault"):
                r,v=_read_field(f_read,mode,fld)
                if r==0 and v.strip().isdigit():
                    return v.strip()
            return None
        rc=f_next()
    return None
