# -*- coding: utf-8 -*-
import os
import ctypes as C

# Constantes CONTPAQ i COMERCIAL
PAQ_NAME = "CONTPAQ I COMERCIAL"  # fSetNombrePAQ

# Tipos básicos
c_long  = C.c_long
c_int   = C.c_int
c_charp = C.c_char_p

def _ansi(s: str) -> bytes:
    # La DLL espera ANSI/Latin-1 en la mayoría de builds
    return (s or "").encode("latin-1", errors="ignore")

class ComercialDLL:
    """
    Wrapper mínimo y seguro de MGWSERVICIOS.DLL para lo que usa la app:
      - fSetNombrePAQ
      - fInicioSesionSDK / fTerminaSesionSDK
      - fAbreEmpresa / fCierraEmpresa
      - fError (texto)
      - fBuscaIdConcepto (por código)
      - fSiguienteFolio (por Id + serie)
    """

    def __init__(self, dll_path: str):
        if not os.path.isfile(dll_path):
            raise FileNotFoundError(f"No existe MGWSERVICIOS.DLL en: {dll_path}")
        self._dll = C.WinDLL(dll_path)

        # ---- Prototipos críticos ----
        # long fSetNombrePAQ(char* aNombrePaq);
        self._dll.fSetNombrePAQ.argtypes = [c_charp]
        self._dll.fSetNombrePAQ.restype  = c_long

        # long fInicioSesionSDK();
        self._dll.fInicioSesionSDK.argtypes = []
        self._dll.fInicioSesionSDK.restype  = c_long

        # long fTerminaSesionSDK();
        self._dll.fTerminaSesionSDK.argtypes = []
        self._dll.fTerminaSesionSDK.restype  = c_long

        # long fAbreEmpresa(char* aRutaEmpresa);
        self._dll.fAbreEmpresa.argtypes = [c_charp]
        self._dll.fAbreEmpresa.restype  = c_long

        # long fCierraEmpresa();
        self._dll.fCierraEmpresa.argtypes = []
        self._dll.fCierraEmpresa.restype  = c_long

        # long fError(long aCodigo, char* aMensaje, int aLen);
        self._dll.fError.argtypes = [c_long, c_charp, c_int]
        self._dll.fError.restype  = c_long

        # long fBuscaIdConcepto(char* cCodigoConcepto, int* pIdConcepto);
        self._dll.fBuscaIdConcepto.argtypes = [c_charp, C.POINTER(c_int)]
        self._dll.fBuscaIdConcepto.restype  = c_long

        # long fSiguienteFolio(int aIdConceptoDocumento, char* aSerie, long* aFolio);
        self._dll.fSiguienteFolio.argtypes  = [c_int, c_charp, C.POINTER(c_long)]
        self._dll.fSiguienteFolio.restype   = c_long

        # ---- Sesión estándar ----
        rc = self._dll.fSetNombrePAQ(_ansi(PAQ_NAME))
        if rc != 0:
            raise RuntimeError(f"fSetNombrePAQ rc={rc}")
        rc = self._dll.fInicioSesionSDK()
        if rc != 0:
            raise RuntimeError(f"fInicioSesionSDK rc={rc}")

    # --------- API de alto nivel usada por app.py ----------
    def open_company(self, empresa_path: str) -> int:
        """Abre empresa (ruta AD*). Devuelve rc."""
        return int(self._dll.fAbreEmpresa(_ansi(empresa_path)))

    def close_company(self) -> int:
        try:
            return int(self._dll.fCierraEmpresa())
        except Exception:
            return 0

    def error_text(self, rc: int) -> str:
        buf = C.create_string_buffer(512)
        try:
            self._dll.fError(int(rc), buf, C.sizeof(buf))
            return buf.value.decode("latin-1", errors="ignore")
        except Exception:
            return f"rc={rc}"

    def next_folio(self, cod_concepto: str, serie: str):
        """
        SDK puro y seguro:
          1) fBuscaIdConcepto(cod) -> IdConcepto
          2) fSiguienteFolio(IdConcepto, serie, &folio)
        """
        # 1) IdConcepto
        pid = c_int(0)
        rc  = int(self._dll.fBuscaIdConcepto(_ansi(cod_concepto), C.byref(pid)))
        if rc != 0:
            return rc, 0

        # 2) SiguienteFolio
        out = c_long(0)
        rc  = int(self._dll.fSiguienteFolio(pid.value, _ansi(serie), C.byref(out)))
        if rc != 0:
            return rc, 0
        return 0, int(out.value)

    # --------- Limpieza ---------
    def __del__(self):
        try:
            self._dll.fCierraEmpresa()
        except Exception:
            pass
        try:
            self._dll.fTerminaSesionSDK()
        except Exception:
            pass
