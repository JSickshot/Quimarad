import os, ctypes
from ctypes import c_int, c_char_p, c_long, create_string_buffer, byref
from pathlib import Path

DLL_NAME = "MGWServicios.dll"

class ComercialSDK:
    def __init__(self, dll_dir: str, paq_name: bytes):
        self.dll_dir = dll_dir
        self.paq_name = paq_name
        self.dll = None
        self._fns = {}
        self._err = create_string_buffer(512)
        self.loaded = False

    def _bind(self, name, restype=c_int, argtypes=None, optional=False):
        try:
            fn = getattr(self.dll, name)
            if argtypes is not None:
                fn.argtypes = argtypes
            fn.restype = restype
            self._fns[name] = fn
        except AttributeError:
            if not optional: raise
            self._fns[name] = None

    def _call(self, name, *args):
        fn = self._fns.get(name)
        if fn is None:
            raise RuntimeError(f"Función {name} no disponible en DLL")
        return fn(*args)

    def _error_text(self, code: int) -> str:
        self._err = create_string_buffer(512)
        if self._fns.get('fError'):
            self._call('fError', code, self._err, 512)
            return self._err.value.decode('latin-1', 'ignore')
        return ""

    def _check(self, code: int, ctx: str):
        if code != 0:
            raise RuntimeError(f"{ctx} | SDK({code}): {self._error_text(code)}")

    def load(self):
        dll_path = Path(self.dll_dir) / DLL_NAME
        if not dll_path.is_file():
            raise FileNotFoundError(f"No existe {DLL_NAME} en: {self.dll_dir}")

        extra = [
            self.dll_dir,
            r"C:\Program Files (x86)\Common Files\Compac\Nucleo",
            r"C:\Program Files\Common Files\Compac\Nucleo",
        ]
        for d in extra:
            if os.path.isdir(d):
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(d)
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH","")
                except Exception:
                    pass

        self.dll = ctypes.WinDLL(str(dll_path))

        # Base
        self._bind('fSetNombrePAQ', c_int, [c_char_p])
        self._bind('fAbreEmpresa', c_int, [c_char_p])
        self._bind('fCierraEmpresa', None, [])
        self._bind('fTerminaSDK', None, [])
        self._bind('fError', None, [c_int, c_char_p, c_int])
        self._bind('fInicioSesionSDK', c_int, [c_char_p, c_char_p], optional=True)

        # Documento / Movimiento
        self._bind('fAltaDocumento', c_int, [ctypes.POINTER(c_long), ctypes.c_void_p])
        self._bind('fSetDatoDocumento', c_int, [c_char_p, c_char_p])
        self._bind('fGuardaDocumento', c_int, [])

        self._bind('fAltaMovimiento', c_int, [c_long, ctypes.POINTER(c_long), ctypes.c_void_p])
        self._bind('fSetDatoMovimiento', c_int, [c_char_p, c_char_p])

        # Catálogos — nombres más comunes (opcionales)
        # Productos
        self._bind('fPosPrimerProducto', c_int, [], optional=True)
        self._bind('fPosSiguienteProducto', c_int, [], optional=True)
        self._bind('fLeeDatoProducto', c_int, [c_char_p, c_char_p, c_int], optional=True)
        # Clientes/Proveedores
        self._bind('fPosPrimerCteProv', c_int, [], optional=True)
        self._bind('fPosSiguienteCteProv', c_int, [], optional=True)
        self._bind('fLeeDatoCteProv', c_int, [c_char_p, c_char_p, c_int], optional=True)
        # Conceptos 
        self._bind('fPosPrimerConceptoDocto', c_int, [], optional=True)
        self._bind('fPosSiguienteConceptoDocto', c_int, [], optional=True)
        self._bind('fLeeDatoConceptoDocto', c_int, [c_char_p, c_char_p, c_int], optional=True)
        # Agentes
        self._bind('fPosPrimerAgente', c_int, [], optional=True)
        self._bind('fPosSiguienteAgente', c_int, [], optional=True)
        self._bind('fLeeDatoAgente', c_int, [c_char_p, c_char_p, c_int], optional=True)
        # Almacenes
        self._bind('fPosPrimerAlmacen', c_int, [], optional=True)
        self._bind('fPosSiguienteAlmacen', c_int, [], optional=True)
        self._bind('fLeeDatoAlmacen', c_int, [c_char_p, c_char_p, c_int], optional=True)
        # Monedas
        self._bind('fPosPrimerMoneda', c_int, [], optional=True)
        self._bind('fPosSiguienteMoneda', c_int, [], optional=True)
        self._bind('fLeeDatoMoneda', c_int, [c_char_p, c_char_p, c_int], optional=True)
        # Series 
        self._bind('fPosPrimerSerie', c_int, [], optional=True)
        self._bind('fPosSiguienteSerie', c_int, [], optional=True)
        self._bind('fLeeDatoSerie', c_int, [c_char_p, c_char_p, c_int], optional=True)

        self._check(self._call('fSetNombrePAQ', self.paq_name), 'Inicializando SDK (fSetNombrePAQ)')
        self.loaded = True

    def abre_empresa(self, path_empresa: str):
        self._check(self._call('fAbreEmpresa', path_empresa.encode('latin-1')), f"Abrir empresa: {path_empresa}")

    def cierra_empresa(self):
        try:
            if self._fns.get('fCierraEmpresa'): self._call('fCierraEmpresa')
        except Exception: pass

    def terminar(self):
        try:
            if self._fns.get('fTerminaSDK'): self._call('fTerminaSDK')
        except Exception: pass

    def set_doc(self, nombre: str, valor):
        val = '' if valor is None else str(valor)
        self._check(self._call('fSetDatoDocumento', nombre.encode('latin-1'), val.encode('latin-1')), f"Set documento {nombre}")

    def alta_documento(self) -> int:
        doc_id = c_long(0)
        self._check(self._call('fAltaDocumento', byref(doc_id), None), 'Alta documento')
        return doc_id.value

    def guarda_documento(self):
        self._check(self._call('fGuardaDocumento'), 'Guardar documento')

    def set_mov(self, nombre: str, valor):
        val = '' if valor is None else str(valor)
        self._check(self._call('fSetDatoMovimiento', nombre.encode('latin-1'), val.encode('latin-1')), f"Set movimiento {nombre}")

    def alta_mov(self, id_doc: int) -> int:
        mov_id = c_long(0)
        self._check(self._call('fAltaMovimiento', id_doc, byref(mov_id), None), 'Alta movimiento')
        return mov_id.value

    def _listar_generico(self, pos_prim, pos_sig, lee_dato, campos, max_items=100000):
        out = []
        if not self._fns.get(pos_prim) or not self._fns.get(lee_dato):
            return out
        buf = create_string_buffer(512)
        if self._fns[pos_prim]() != 0:
            return out
        n = 0
        while n < max_items:
            rec = {}
            for campo_alias, campo_sdk in campos:
                self._fns[lee_dato](campo_sdk.encode('latin-1'), buf, 512)
                rec[campo_alias] = buf.value.decode('latin-1', 'ignore')
            out.append(rec)
            n += 1
            if self._fns[pos_sig]() != 0:
                break
        return out

    def listar_productos(self): 
        return self._listar_generico('fPosPrimerProducto', 'fPosSiguienteProducto', 'fLeeDatoProducto',
                                     [('codigo','cCodigoProducto'),('nombre','cNombreProducto')])

    def listar_clientes(self): 
        return self._listar_generico('fPosPrimerCteProv', 'fPosSiguienteCteProv', 'fLeeDatoCteProv',
                                     [('codigo','cCodigoCliente'),('nombre','cRazonSocial')])

    def listar_conceptos(self):
        return self._listar_generico('fPosPrimerConceptoDocto','fPosSiguienteConceptoDocto','fLeeDatoConceptoDocto',
                                     [('codigo','cCodigoConcepto'),('nombre','cNombreConcepto')])

    def listar_agentes(self): 
        return self._listar_generico('fPosPrimerAgente','fPosSiguienteAgente','fLeeDatoAgente',
                                     [('codigo','cCodigoAgente'),('nombre','cNombreAgente')])

    def listar_almacenes(self): 
        return self._listar_generico('fPosPrimerAlmacen','fPosSiguienteAlmacen','fLeeDatoAlmacen',
                                     [('codigo','cCodigoAlmacen'),('nombre','cNombreAlmacen')])

    def listar_monedas(self): 
        return self._listar_generico('fPosPrimerMoneda','fPosSiguienteMoneda','fLeeDatoMoneda',
                                     [('codigo','cIdMoneda'),('nombre','cNombreMoneda')])

    def listar_series(self):
        return self._listar_generico('fPosPrimerSerie','fPosSiguienteSerie','fLeeDatoSerie',
                                     [('codigo','cSerie'),('nombre','cNombreSerie')])
