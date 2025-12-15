# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Tuple

# Este loader NO usa el wrapper "doc_*".
# Siempre llama a las funciones clásicas del SDK:
#   fAltaDocumento / fSetDatoDocumento / fAltaMovimiento /
#   fSetDatoMovimiento / fGuardaDocumento / fCancelaDocumento

Headers = List[str]
Row = Dict[str, str]
Rows = List[Row]

_DOC_MAP = {
    "Concepto Código <F3>": "cCodConcepto",
    "Fecha (dd/mm/aaaa)":   ("dFechaEmision", "dFechaDoc"),
    "Serie":                "cSerie",
    "Folio":                "cFolio",
    "Cliente Código <F3>":  "cCodCteProv",
    "Moneda Id <F3>":       "cIdMoneda",
    "Tipo de Cambio":       "cTipoCambio",
    "Agente Código <F3>":   "cCodAgente",
    # Campos adicionales del encabezado si los tuvieras,
    # puedes agregarlos aquí sin que sean obligatorios.
}

_MOV_MAP = {
    "Producto Código <F3>": "cCodigoProducto",
    "Almacén Código <F3>":  "cCodAlmacen",
    "Cantidad":             "cUnidades",
    "Precio Unitario":      "cPrecio",
    "Descuento 1 (%)":      ("cPorcentajeDescuento1", "cDescuento1"),
    "Descuento 2 (%)":      ("cPorcentajeDescuento2", "cDescuento2"),
    "Descuento 3 (%)":      ("cPorcentajeDescuento3", "cDescuento3"),
    "IVA (%)":              ("cPorcentajeImpuesto1", "cTasaIVA"),
}

# mínimo indispensable para evitar AccessViolation
_REQUIRED_DOC = ("Concepto Código <F3>", "Fecha (dd/mm/aaaa)", "Serie", "Folio", "Cliente Código <F3>", "Moneda Id <F3>", "Tipo de Cambio")
_REQUIRED_MOV = ("Producto Código <F3>", "Cantidad", "Precio Unitario")


def _yyyymmdd_from_ddmmaa(s: str) -> str:
    s = (s or "").strip().replace(".", "/").replace("-", "/")
    if not s:
        return ""
    try:
        p = [x for x in s.split("/") if x]
        if len(p) == 3:
            # dd/mm/aaaa o aaaa/mm/dd
            if len(p[0]) == 4:
                y, m, d = map(int, p)
            else:
                d, m, y = map(int, p)
            return f"{y:04d}{m:02d}{d:02d}"
    except Exception:
        pass
    if len(s) == 8 and s.isdigit():
        return s
    return ""


class FacturaLoader:
    def __init__(self, sdk, tolerant: bool = True, logger: Callable[[str], None] | None = None):
        self.sdk = sdk
        self.dll = sdk.dll
        self.tolerant = tolerant
        self.log = logger or (lambda s: None)

        # Validamos que existan al menos las funciones clásicas mínimas
        required = ["fAltaDocumento", "fSetDatoDocumento", "fAltaMovimiento",
                    "fSetDatoMovimiento", "fGuardaDocumento", "fCancelaDocumento"]
        faltan = [fn for fn in required if not hasattr(self.dll, fn)]
        if faltan:
            raise RuntimeError(
                "El wrapper del SDK no expone las funciones clásicas necesarias: "
                + ", ".join(faltan)
            )

    # ---------- util ----------
    def _set_doc(self, campo_sdk: str | Tuple[str, ...], valor: str) -> None:
        if not valor:
            return
        if isinstance(campo_sdk, str):
            campo_sdk = (campo_sdk,)
        last_rc = 0
        for c in campo_sdk:
            rc = self.dll.fSetDatoDocumento(c, str(valor))
            last_rc = rc
            if rc == 0:
                return
        # si no lo logró en ningún alias
        if last_rc != 0 and not self.tolerant:
            raise RuntimeError(f"fSetDatoDocumento({campo_sdk}) rc={last_rc} {self.dll.error_text(last_rc)}")

    def _set_mov(self, campo_sdk: str | Tuple[str, ...], valor: str) -> None:
        # valores vacíos no son obligatorios
        if valor is None or valor == "":
            return
        if isinstance(campo_sdk, str):
            campo_sdk = (campo_sdk,)
        last_rc = 0
        for c in campo_sdk:
            rc = self.dll.fSetDatoMovimiento(c, str(valor))
            last_rc = rc
            if rc == 0:
                return
        if last_rc != 0 and not self.tolerant:
            raise RuntimeError(f"fSetDatoMovimiento({campo_sdk}) rc={last_rc} {self.dll.error_text(last_rc)}")

    # ---------- API ----------
    def crear_desde_tabla(
        self,
        headers: Headers,
        rows: Rows,
        usar_primer_renglon_para_encabezado: bool = True,
        simular: bool = False,
    ) -> None:

        if not rows:
            raise RuntimeError("No hay renglones para crear el documento.")

        # Encabezado
        enc: Row = {}
        if usar_primer_renglon_para_encabezado:
            enc = dict(rows[0])

        # Validación mínima para evitar AccessViolation
        faltantes = [h for h in _REQUIRED_DOC if not (enc.get(h, "") or "").strip()]
        if faltantes and not self.tolerant:
            raise RuntimeError(f"Faltan datos del encabezado: {', '.join(faltantes)}")

        # Alta de documento
        rc = self.dll.fAltaDocumento()
        if rc != 0:
            raise RuntimeError(f"fAltaDocumento rc={rc} {self.dll.error_text(rc)}")
        self.log("[Crear] Encabezado -> " + ", ".join([f"{k}={enc.get(k,'')}" for k in _DOC_MAP.keys()]))

        # mapeo encabezado
        for h, sdk_field in _DOC_MAP.items():
            v = (enc.get(h, "") or "").strip()
            if h == "Fecha (dd/mm/aaaa)":
                v = _yyyymmdd_from_ddmmaa(v)
            self._set_doc(sdk_field, v)

        # Movimientos a partir de la segunda fila si usamos encabezado en la primera
        start_idx = 1 if usar_primer_renglon_para_encabezado else 0
        enviados = 0

        for i in range(start_idx, len(rows)):
            mov = rows[i]
            if not any((mov.get(k, "") or "").strip() for k in _MOV_MAP.keys()):
                # fila vacía
                continue

            # validación mínima del movimiento
            miss = [h for h in _REQUIRED_MOV if not (mov.get(h, "") or "").strip()]
            if miss and not self.tolerant:
                raise RuntimeError(f"Renglón {i+1}: faltan datos del movimiento: {', '.join(miss)}")

            rc = self.dll.fAltaMovimiento()
            if rc != 0:
                raise RuntimeError(f"fAltaMovimiento rc={rc} {self.dll.error_text(rc)}")

            # mapeo movimiento
            for h, sdk_field in _MOV_MAP.items():
                v = (mov.get(h, "") or "").strip()
                self._set_mov(sdk_field, v)

            # guarda movimiento
            rc = self.dll.fGuardaMovimiento()
            if rc != 0:
                raise RuntimeError(f"fGuardaMovimiento rc={rc} {self.dll.error_text(rc)}")

            enviados += 1

        self.log(f"[Crear] Movimientos a enviar: {enviados}")

        # Commit / Cancel
        if simular:
            rc = self.dll.fCancelaDocumento()
            if rc != 0:
                raise RuntimeError(f"fCancelaDocumento rc={rc} {self.dll.error_text(rc)}")
            self.log("[Fin] OK=0 Simulado")
        else:
            rc = self.dll.fGuardaDocumento()
            if rc != 0:
                raise RuntimeError(f"fGuardaDocumento rc={rc} {self.dll.error_text(rc)}")
            self.log("[Fin] OK=0 Guardado")
