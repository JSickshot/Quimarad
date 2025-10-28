# features/factura_loader.py
# -*- coding: utf-8 -*-
import ctypes

DOC_FIELD_ALIASES = {
    "cCodConcepto": ["cCodConcepto","cCodigoConcepto","cConcepto","cIdConcepto"],
    "cSerie":       ["cSerie","cCodigoSerie","cIdSerie"],
    "cFolio":       ["cFolio","cIdFolio"],
    "cCodCteProv":  ["cCodCteProv","cCodigoCliente","cCodigoCteProv","cCliente","cCodCliente"],
    "cFecha": [
        "cFecha","cFechaDoc","cFechaDocumento",
        "cFechaEmision","cFechaExpedicion","cFechaMovto"
    ],
    "cReferencia":  ["cReferencia","cReferenciaDocto"],
    "cIdMoneda":    ["cIdMoneda","cMoneda","cMonedaId","cIdMonedaDocto"],
    "cTipoCambio":  ["cTipoCambio","cTCambio"],
    "cCodAgente":   ["cCodAgente","cCodigoAgente"],
    "cCodProyecto": ["cCodProyecto","cCodigoProyecto","cProyecto"],
}

MOV_FIELD_ALIASES = {
    "cCodigoProducto": ["cCodProducto","cCodigoProducto","cProducto"],
    "cUnidades":       ["cUnidades","cCantidad"],
    "cPrecio":         ["cPrecio","cPrecioUnitario"],
    "cCodigoAlmacen":  ["cCodAlmacen","cCodigoAlmacen","cAlmacen"],
    "cDescripcionExtra":["cDescripcionExtra","cTextoExtra","cDescripcion"],
    "cPorcDesc1":      ["cPorcDesc1","cDesc1"],
    "cPorcDesc2":      ["cPorcDesc2","cDesc2"],
    "cPorcDesc3":      ["cPorcDesc3","cDesc3"],
    "cPorcIVA":        ["cPorcIVA","cIVA"],
}

class FacturaLoader:
    def __init__(self, sdk, tolerant=True, logger=print):
        self.sdk = sdk
        self.tolerant = tolerant
        self.log = logger

        self.sdk.dll.fSetDatoDocumento.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.sdk.dll.fSetDatoDocumento.restype  = ctypes.c_int
        self.sdk.dll.fAltaDocumento.argtypes    = [ctypes.POINTER(ctypes.c_long), ctypes.c_void_p]
        self.sdk.dll.fAltaDocumento.restype     = ctypes.c_int
        self.sdk.dll.fGuardaDocumento.argtypes  = []
        self.sdk.dll.fGuardaDocumento.restype   = ctypes.c_int

        self.sdk.dll.fSetDatoMovimiento.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.sdk.dll.fSetDatoMovimiento.restype  = ctypes.c_int
        self.sdk.dll.fAltaMovimiento.argtypes    = [ctypes.c_long, ctypes.POINTER(ctypes.c_long), ctypes.c_void_p]
        self.sdk.dll.fAltaMovimiento.restype     = ctypes.c_int

    def _try_set_doc(self, canonical: str, value: str):
        for name in DOC_FIELD_ALIASES.get(canonical, [canonical]):
            code = self.sdk.dll.fSetDatoDocumento(name.encode("latin-1"),
                                                  (value or "").encode("latin-1"))
            if code == 0:
                if name != canonical: self.log(f"[DOC] usando alias {name} para {canonical}")
                return
            if code != 73 and not self.tolerant:
                raise RuntimeError(f"SetDoc {name} | SDK({code})")
        raise RuntimeError(f"SetDoc {canonical} | SDK(73): Nombre de campo inválido en esta DLL")

    def _try_set_mov(self, canonical: str, value: str):
        for name in MOV_FIELD_ALIASES.get(canonical, [canonical]):
            code = self.sdk.dll.fSetDatoMovimiento(name.encode("latin-1"),
                                                   (value or "").encode("latin-1"))
            if code == 0:
                if name != canonical: self.log(f"[MOV] usando alias {name} para {canonical}")
                return
            if code != 73 and not self.tolerant:
                raise RuntimeError(f"SetMov {name} | SDK({code})")
        raise RuntimeError(f"SetMov {canonical} | SDK(73): Nombre de campo inválido en esta DLL")

    def crear_desde_tabla(self, headers, rows,
                           usar_primer_renglon_para_encabezado=True,
                           simular=False):
        if not rows: raise RuntimeError("No hay renglones para procesar.")

        head_map = {
            "Concepto Código <F3>": "cCodConcepto",
            "Proyecto Codigo <F3>": "cCodProyecto",
            "Fecha": "cFecha",
            "Serie": "cSerie",
            "Folio": "cFolio",
            "Cliente Código <F3>": "cCodCteProv",
            "Moneda Id <F3>": "cIdMoneda",
            "Tipo de Cambio": "cTipoCambio",
            "Agente Código <F3>": "cCodAgente",
        }
        mov_map = {
            "Producto Código <F3>": "cCodigoProducto",
            "Almacén Código <F3>": "cCodigoAlmacen",
            "Cantidad": "cUnidades",
            "Precio Unitario": "cPrecio",
            "Descuento 1 (%)": "cPorcDesc1",
            "Descuento 2 (%)": "cPorcDesc2",
            "Descuento 3 (%)": "cPorcDesc3",
            "IVA (%)": "cPorcIVA",
        }

        def val(r, colname):
            if isinstance(r, dict): return str(r.get(colname, "")).strip()
            try: return str(r[headers.index(colname)]).strip()
            except Exception: return ""

        # encabezado
        doc_id = ctypes.c_long(0)
        if usar_primer_renglon_para_encabezado:
            r0 = rows[0]
            fecha = val(r0, "Fecha")
            if fecha:
                t = fecha.replace("\\","/").replace("-","/").replace(".","/")
                parts=t.split("/")
                if len(parts)==3:
                    if len(parts[0])==4: y,m,d=parts
                    else: d,m,y=parts
                    fecha=f"{int(y):04d}{int(m):02d}{int(d):02d}"
                elif len(fecha)==8 and fecha.isdigit():
                    pass

            req=["Concepto Código <F3>","Fecha","Cliente Código <F3>"]
            falt=[c for c in req if not val(r0,c)]
            if falt: raise RuntimeError(f"Faltan datos de encabezado: {', '.join(falt)}. (La fecha se convierte a YYYYMMDD)")

            self._try_set_doc("cCodConcepto", val(r0, "Concepto Código <F3>"))
            if val(r0,"Serie"): self._try_set_doc("cSerie", val(r0, "Serie"))
            if val(r0,"Folio"): self._try_set_doc("cFolio", val(r0, "Folio"))
            self._try_set_doc("cCodCteProv", val(r0, "Cliente Código <F3>"))
            self._try_set_doc("cFecha", fecha)
            if val(r0,"Moneda Id <F3>"): self._try_set_doc("cIdMoneda", val(r0, "Moneda Id <F3>"))
            if val(r0,"Tipo de Cambio"): self._try_set_doc("cTipoCambio", val(r0, "Tipo de Cambio"))
            if val(r0,"Agente Código <F3>"): self._try_set_doc("cCodAgente", val(r0, "Agente Código <F3>"))
            if val(r0,"Proyecto Codigo <F3>"): self._try_set_doc("cCodProyecto", val(r0, "Proyecto Codigo <F3>"))

        if not simular:
            code = self.sdk.dll.fAltaDocumento(ctypes.byref(doc_id), None)
            if code != 0: raise RuntimeError(f"Alta documento | SDK({code})")

        # partidas
        reng=0
        for r in rows:
            cprod = val(r, "Producto Código <F3>")
            if not cprod: continue
            reng += 1
            if not simular:
                self._try_set_mov("cCodigoProducto", cprod)
                if val(r,"Almacén Código <F3>"): self._try_set_mov("cCodigoAlmacen", val(r,"Almacén Código <F3>"))
                if val(r,"Cantidad"): self._try_set_mov("cUnidades", val(r,"Cantidad"))
                if val(r,"Precio Unitario"): self._try_set_mov("cPrecio", val(r,"Precio Unitario"))
                if val(r,"Descuento 1 (%)"): self._try_set_mov("cPorcDesc1", val(r,"Descuento 1 (%)"))
                if val(r,"Descuento 2 (%)"): self._try_set_mov("cPorcDesc2", val(r,"Descuento 2 (%)"))
                if val(r,"Descuento 3 (%)"): self._try_set_mov("cPorcDesc3", val(r,"Descuento 3 (%)"))
                if val(r,"IVA (%)"):           self._try_set_mov("cPorcIVA",    val(r,"IVA (%)"))
                mov_id = ctypes.c_long(0)
                code = self.sdk.dll.fAltaMovimiento(doc_id.value, ctypes.byref(mov_id), None)
                if code != 0: raise RuntimeError(f"Alta movimiento {reng} | SDK({code})")

        if not simular:
            code = self.sdk.dll.fGuardaDocumento()
            if code != 0: raise RuntimeError(f"Guardar documento | SDK({code})")
