from __future__ import annotations
import re
from datetime import datetime
from typing import List, Dict, Callable
from sdk.comercial import ComercialSDK

def _norm(h: str) -> str:
    return " ".join(h.replace("\t"," ").replace("\r"," ").replace("\n"," ").replace('"',"").split())

def _acc(headers: List[str]) -> Dict[str, str]:
    return {_norm(h): h for h in headers}

def _to_sdk_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{8}", s):
        yyyy = int(s[:4])
        mm   = int(s[4:6])
        dd   = int(s[6:8])
        if 1900 <= yyyy <= 2100:
            try: datetime(yyyy, mm, dd); return s
            except Exception: pass
        dd2, mm2, yyyy2 = int(s[:2]), int(s[2:4]), int(s[4:])
        try: datetime(yyyy2, mm2, dd2); return f"{yyyy2:04d}{mm2:02d}{dd2:02d}"
        except Exception: pass
        mm3, dd3, yyyy3 = int(s[:2]), int(s[2:4]), int(s[4:])
        try: datetime(yyyy3, mm3, dd3); return f"{yyyy3:04d}{mm3:02d}{dd3:02d}"
        except Exception: pass
        return ""
    s2 = re.sub(r"[^\d]", "", s)
    for fmt in ("%Y%m%d", "%d%m%Y", "%m%d%Y"):
        try: return datetime.strptime(s2, fmt).strftime("%Y%m%d")
        except Exception: pass
    for fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y","%m-%d-%Y"):
        try: return datetime.strptime(s, fmt).strftime("%Y%m%d")
        except Exception: pass
    return ""

def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _is_number(s: str) -> bool:
    try:
        float(str(s).replace(",", "")); return True
    except Exception:
        return False

COLUMNS_ALL = [
    "Concepto Código <F3>", "Proyecto Codigo <F3>", "Fecha", "Serie", "Folio",
    "Cliente Código <F3>", "Moneda Id <F3>", "Tipo de Cambio", "Agente Código <F3>",
    "Producto Código <F3>", "Almacén Código <F3>", "Cantidad", "Precio Unitario",
    "Descuento 1 (%)", "Descuento 2 (%)", "Descuento 3 (%)", "IVA (%)",
    "Segmento Contable", "Serie Número", "Pedimento Número", "Lote Numero",
    "Folio Fiscal (UUID)",
    "Documento Referencia", "Documento Observaciones",
    "Documento Texto Extra 01", "Documento Texto Extra 01",
    "Documento Texto Extra 01", "Documento Texto Extra 01",
    "Documento Importe 01", "Documento Importe 02", "Documento Importe 03",
    "Docto Extras",
    "Movimiento Referencia", "Movimiento Observaciones",
    "Movimiento Texto Extra 01", "Movimiento Texto Extra 01",
    "Movimiento Texto Extra 01", "Movimiento Texto Extra 01",
    "Movimiento Importe 01", "Movimiento Importe 02", "Movimiento Importe 03",
    "Movto Extras",
    "Concepto Descripción (No capturar)", "Proveedor Nombre (No capturar)",
    "Agente Nombre (No capturar)", "Producto Descripción (No capturar)",
    "Almacén Descripción (No capturar)",
]

DOCUMENTO_MAP = {
    "Concepto Código <F3>": ["cCodConcepto"],
    "Proyecto Codigo <F3>": ["cProyecto", "cIdProyecto"],
    "Fecha": ["cFecha"],
    "Serie": ["cSerie"],
    "Folio": ["cFolio"],
    "Cliente Código <F3>": ["cCodCteProv"],
    "Moneda Id <F3>": ["cIdMoneda"],
    "Tipo de Cambio": ["cTipoCambio"],
    "Agente Código <F3>": ["cCodAgente"],
    "Documento Referencia": ["cReferencia"],
    "Documento Observaciones": ["cObservacion","cObservaciones"],
    "Documento Texto Extra 01": ["cTextoExtra1"],
    "Documento Importe 01": ["cImporte01"],
    "Documento Importe 02": ["cImporte02"],
    "Documento Importe 03": ["cImporte03"],
    "Docto Extras": ["cExtras"],
    "Folio Fiscal (UUID)": ["cFolioFiscalUUID","cUUID"],
}

MOVIMIENTO_MAP = {
    "Producto Código <F3>": ["cCodigoProducto"],
    "Almacén Código <F3>": ["cCodigoAlmacen"],
    "Cantidad": ["cUnidades"],
    "Precio Unitario": ["cPrecio"],
    "Descuento 1 (%)": ["cPorcentajeDescuento1"],
    "Descuento 2 (%)": ["cPorcentajeDescuento2"],
    "Descuento 3 (%)": ["cPorcentajeDescuento3"],
    "IVA (%)": ["cPorcentajeImpuesto1","cImpuesto1"],
    "Segmento Contable": ["cSegmentoContable"],
    "Serie Número": ["cSerieNumero"],
    "Pedimento Número": ["cPedimento"],
    "Lote Numero": ["cLote"],
    "Movimiento Referencia": ["cReferencia"],
    "Movimiento Observaciones": ["cObservacion","cObservaciones"],
    "Movimiento Texto Extra 01": ["cTextoExtra1"],
    "Movimiento Importe 01": ["cImporte01"],
    "Movimiento Importe 02": ["cImporte02"],
    "Movimiento Importe 03": ["cImporte03"],
    "Movto Extras": ["cExtras"],
}

NO_CAPTURAR = {
    _norm("Concepto Descripción (No capturar)"),
    _norm("Proveedor Nombre (No capturar)"),
    _norm("Agente Nombre (No capturar)"),
    _norm("Producto Descripción (No capturar)"),
    _norm("Almacén Descripción (No capturar)"),
}

class FacturaLoader:
    def __init__(self, sdk: ComercialSDK, tolerant: bool = True, logger: Callable[[str], None] = print):
        self.sdk = sdk
        self.tolerant = tolerant
        self.log = logger

    def _try_set_doc(self, campos_sdk: List[str], valor) -> bool:
        for campo in campos_sdk:
            try:
                self.sdk.set_doc(campo, valor); return True
            except Exception:
                if not self.tolerant: raise
        self.log(f"[DOC] (omitido) {campos_sdk} = {valor}"); return False

    def _try_set_mov(self, campos_sdk: List[str], valor) -> bool:
        for campo in campos_sdk:
            try:
                self.sdk.set_mov(campo, valor); return True
            except Exception:
                if not self.tolerant: raise
        self.log(f"[MOV] (omitido) {campos_sdk} = {valor}"); return False

    def crear_desde_tabla(self, headers: List[str], rows: List[Dict[str,str]],
                          usar_primer_renglon_para_encabezado=True, simular=False):
        if not rows: raise ValueError("No hay renglones.")
        acc = _acc(headers)
        header = rows[0] if usar_primer_renglon_para_encabezado else {}

        fecha_key = acc.get(_norm("Fecha"))
        fecha_val = _to_sdk_date(header.get(fecha_key, "")) if fecha_key else ""
        if fecha_key: header[fecha_key] = fecha_val

        required = {
            "Concepto Código <F3>": header.get(acc.get(_norm("Concepto Código <F3>")), "").strip(),
            "Fecha": fecha_val,
            "Cliente Código <F3>": header.get(acc.get(_norm("Cliente Código <F3>")), "").strip(),
        }
        folio_capturado = header.get(acc.get(_norm("Folio")), "")
        if not folio_capturado:
            required["Serie"] = header.get(acc.get(_norm("Serie")), "").strip()

        faltan = [k for k,v in required.items() if not v]
        if faltan:
            raise ValueError("Faltan datos de encabezado: " + ", ".join(faltan) +
                             ". (La fecha se convierte a YYYYMMDD automáticamente)")

        if header.get(acc.get(_norm("Moneda Id <F3>")), "").strip():
            tc = (header.get(acc.get(_norm("Tipo de Cambio")), "") or "").replace(",", "")
            if not _is_number(tc) or float(tc) <= 0:
                raise ValueError("Tipo de Cambio inválido para la Moneda indicada.")

        self.log("== Encabezado ==")
        for csv_name, sdk_fields in DOCUMENTO_MAP.items():
            key = acc.get(_norm(csv_name))
            if not key or _norm(csv_name) in NO_CAPTURAR: continue
            val = header.get(key, "")
            if csv_name == "Fecha":
                val = _to_sdk_date(val)
                if not val: raise ValueError("Fecha inválida.")
            if csv_name == "Folio":
                val = _only_digits(val)
                if not val: continue
            if val == "": continue
            self.log(f"[DOC] {sdk_fields} = {val}")
            if not simular: self._try_set_doc(sdk_fields, val)

        doc_id = -1
        if not simular: doc_id = self.sdk.alta_documento()
        self.log(f"Documento creado id={doc_id}")

        self.log("== Movimientos ==")
        for i, row in enumerate(rows, start=1):
            try:
                prod = row.get(acc.get(_norm("Producto Código <F3>")), "").strip()
                cant = (row.get(acc.get(_norm("Cantidad")), "") or "").replace(",", ".").strip()
                prec = (row.get(acc.get(_norm("Precio Unitario")), "") or "").replace(",", ".").strip()
                alm  = row.get(acc.get(_norm("Almacén Código <F3>")), "").strip() or "1"
                if not (prod and cant and prec and _is_number(cant) and _is_number(prec)):
                    raise ValueError("Faltan Producto/Cantidad/Precio o no son numéricos.")

                if not simular:
                    self._try_set_mov(["cCodigoProducto"], prod)
                    self._try_set_mov(["cUnidades"], cant)
                    self._try_set_mov(["cPrecio"], prec)
                    self._try_set_mov(["cCodigoAlmacen"], alm)
                    for csv_name, sdk_fields in MOVIMIENTO_MAP.items():
                        key = acc.get(_norm(csv_name))
                        if not key or _norm(csv_name) in NO_CAPTURAR: continue
                        v = row.get(key, "")
                        if v == "": continue
                        self._try_set_mov(sdk_fields, v)

                    mov_id = self.sdk.alta_mov(doc_id)
                    self.log(f"  + R{i}: {prod} x {cant} @ {prec} (alm {alm}) -> id={mov_id}")
                else:
                    self.log(f"  ~ R{i} (SIM): {prod} x {cant} @ {prec} (alm {alm})")
            except Exception as ex:
                self.log(f"  ! R{i} ERROR: {ex}")

        if not simular:
            self.sdk.guarda_documento(); self.log("Documento guardado.")
        else:
            self.log("SIMULACIÓN.")
