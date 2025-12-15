# features/catalogs.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Tuple, Any

def _first_callable(obj, names: Iterable[str]):
    """
    Devuelve la primera función disponible en obj, obj.dll o obj.catalogs
    con alguno de los nombres candidatos.
    """
    for name in names:
        fn = getattr(obj, name, None)
        if callable(fn):
            return fn
        dll = getattr(obj, "dll", None)
        if dll:
            fn = getattr(dll, name, None)
            if callable(fn):
                return fn
        cats = getattr(obj, "catalogs", None)
        if cats:
            fn = getattr(cats, name, None)
            if callable(fn):
                return fn
    return None

def _coerce_to_pairs(
    items: Any,
    code_keys=(
        "codigo","code","id","clave","cCodigo","cCodigoProducto",
        "cCodAlmacen","cCodAgente","cCodConcepto","cCodCteProv",
        "cIdMoneda","cSerie","cCodigoCliente"
    ),
    name_keys=(
        "nombre","name","descripcion","desc","cNombre",
        "cDescripcion","cDenominacion","denominacion"
    ),
) -> List[Tuple[str,str]]:
    """Normaliza tuplas/dicts/strings a lista de pares [(codigo, nombre)]."""
    out: List[Tuple[str,str]] = []
    if items is None:
        return out
    try:
        iterator = list(items)
    except Exception:
        return out

    for it in iterator:
        if it is None:
            continue
        # (codigo, nombre)
        if isinstance(it, (tuple, list)):
            if len(it) >= 2:
                c = str(it[0]).strip()
                n = str(it[1]).strip()
                if c:
                    out.append((c, n or c))
                continue
            elif len(it) == 1:
                s = str(it[0]).strip()
                if s:
                    out.append((s, s))
                continue
        # dict estilo {"codigo": "...", "nombre": "..."}
        if isinstance(it, dict):
            c = n = None
            for k in code_keys:
                if k in it and it[k] is not None:
                    c = str(it[k]).strip(); break
            for k in name_keys:
                if k in it and it[k] is not None:
                    n = str(it[k]).strip(); break
            if c:
                out.append((c, n or c))
            continue
        # string suelto -> (s, s)
        s = str(it).strip()
        if s:
            out.append((s, s))

    # deduplicar por código
    seen = set(); uniq: List[Tuple[str,str]] = []
    for c, n in out:
        if c not in seen:
            uniq.append((c, n)); seen.add(c)
    return uniq

def _enum_generic(sdk, fn_candidates: Iterable[str]) -> List[Tuple[str,str]]:
    """
    Llama a la primera función disponible (con varios alias) en el wrapper,
    en sdk.dll o en sdk.catalogs; normaliza a pares.
    """
    fn = _first_callable(sdk, fn_candidates)
    if not fn:
        return []
    try:
        return _coerce_to_pairs(fn())
    except Exception:
        try:
            # algunos wrappers piden sdk explícito
            return _coerce_to_pairs(fn(sdk))
        except Exception:
            return []

def conceptos(sdk) -> List[Tuple[str, str]]:
    return _enum_generic(sdk, (
        "conceptos","list_conceptos","enum_conceptos",
        "cat_conceptos","get_conceptos","obtener_conceptos"
    ))

def clientes(sdk) -> List[Tuple[str, str]]:
    return _enum_generic(sdk, (
        "clientes","list_clientes","enum_clientes",
        "cat_clientes","get_clientes","obtener_clientes"
    ))

def productos(sdk) -> List[Tuple[str, str]]:
    return _enum_generic(sdk, (
        "productos","list_productos","enum_productos",
        "cat_productos","get_productos","obtener_productos"
    ))

def almacenes(sdk) -> List[Tuple[str, str]]:
    return _enum_generic(sdk, (
        "almacenes","list_almacenes","enum_almacenes",
        "cat_almacenes","get_almacenes","obtener_almacenes"
    ))

def agentes(sdk) -> List[Tuple[str, str]]:
    return _enum_generic(sdk, (
        "agentes","list_agentes","enum_agentes",
        "cat_agentes","get_agentes","obtener_agentes"
    ))

def monedas(sdk) -> List[Tuple[str, str]]:
    pairs = _enum_generic(sdk, (
        "monedas","list_monedas","enum_monedas",
        "cat_monedas","get_monedas","obtener_monedas"
    ))
    # fallback seguro: PMX y USD
    if not pairs:
        pairs = [("1","Peso Mexicano"), ("2","Dólar Americano")]
    return pairs

def series(sdk) -> List[Tuple[str, str]]:
    pairs = _enum_generic(sdk, (
        "series","list_series","enum_series",
        "cat_series","get_series","obtener_series"
    ))
    # fallback seguro: "1"
    if not pairs:
        pairs = [("1","1")]
    return pairs

__all__ = [
    "conceptos","clientes","productos","almacenes",
    "agentes","monedas","series"
]
