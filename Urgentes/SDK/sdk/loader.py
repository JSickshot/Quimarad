# sdk/loader.py
# -*- coding: utf-8 -*-
import os, sys, ctypes
from ctypes import c_int, c_char_p, c_long, create_string_buffer

class SDKError(RuntimeError):
    pass

DEFAULT_DIRS = [
    r"C:\Program Files (x86)\Compac\COMERCIAL",
    r"C:\Program Files\Compac\COMERCIAL",
]

def _add_dll_dir(path: str):
    if not path or not os.path.isdir(path):
        return None
    # Py3.8+: asegura que Windows busque dependencias en esta carpeta
    try:
        return os.add_dll_directory(path)  # devuelve un handle que hay que retener
    except Exception:
        # fallback Win7/py<3.8
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(path)
            return path  # “handle” sintético
        except Exception:
            return None

class ComercialSDK:
    def __init__(self, dll_dir: str = None, paq_name: bytes = b"CONTPAQ I Comercial"):
        self.dll_dir = dll_dir
        self.paq_name = paq_name
        self.dll = None
        self._errbuf = create_string_buffer(512)
        self._dll_dir_handle = None

    def _pick_dir(self) -> str:
        # 1) argumento o variable de entorno
        cands = []
        if self.dll_dir: cands.append(self.dll_dir)
        env = os.environ.get("COMPAC_SDK_DIR")
        if env: cands.append(env)

        # 2) carpeta junto al EXE: .\compac_sdk
        try:
            base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
        except Exception:
            base = os.getcwd()
        cands.append(os.path.join(base, "compac_sdk"))

        # 3) rutas típicas
        cands += DEFAULT_DIRS

        # 4) cualquiera que contenga MGWSERVICIOS.DLL
        for p in cands:
            dll = os.path.join(p, "MGWSERVICIOS.DLL")
            if os.path.isfile(dll):
                return p
        return ""

    def load(self):
        dll_dir = self._pick_dir()
        if not dll_dir:
            raise SDKError(
                "No se encontró MGWSERVICIOS.DLL.\n\nOpciones:\n"
                " • Copia toda la carpeta del SDK (COMERCIAL) junto al EXE en .\\compac_sdk\n"
                " • O define la variable de entorno COMPAC_SDK_DIR apuntando a la carpeta del SDK\n"
                " • O instala CONTPAQi Comercial en su ruta por defecto."
            )

        # MUY IMPORTANTE para ejecutables 'frozen' (PyInstaller one-file)
        self._dll_dir_handle = _add_dll_dir(dll_dir)

        # Cambiamos el CWD para DLL con rutas relativas internas
        try: os.chdir(dll_dir)
        except Exception: pass

        try:
            self.dll = ctypes.WinDLL(os.path.join(dll_dir, "MGWSERVICIOS.DLL"))
        except Exception as e:
            raise SDKError(
                f"No se pudo cargar MGWSERVICIOS.DLL ({dll_dir}).\n"
                f"Detalle original: {e}\n\n"
                "Si estás usando un EXE one-file, asegúrate de:\n"
                " 1) Ejecutar en 32 bits (SDK es x86)\n"
                " 2) Tener todas las dependencias en la MISMA carpeta (MGW000.DLL, etc.)\n"
                " 3) Haber agregado la carpeta con os.add_dll_directory (este loader ya lo hace)")

        # binding
        self._bind("fSetNombrePAQ", c_int, [c_char_p])
        self._bind("fAbreEmpresa",  c_int, [c_char_p])
        self._bind("fCierraEmpresa", c_int, [])
        self._bind("fTerminaSDK", c_int, [])
        self._bind("fError", c_int, [c_int, c_char_p, c_int])
        self._bind("fInicioSesionSDK", c_int, [c_char_p, c_char_p], optional=True)

        self._bind("fSetDatoDocumento", c_int, [c_char_p, c_char_p])
        self._bind("fAltaDocumento", c_int, [ctypes.POINTER(c_long), ctypes.c_void_p])
        self._bind("fGuardaDocumento", c_int, [])
        self._bind("fCancelaDocumento", c_int, [], optional=True)

        self._bind("fSetDatoMovimiento", c_int, [c_char_p, c_char_p])
        self._bind("fAltaMovimiento", c_int, [c_long, ctypes.POINTER(c_long), ctypes.c_void_p])

        self._chk(self.dll.fSetNombrePAQ(self.paq_name), "fSetNombrePAQ")

    def _bind(self, name, restype, args=None, optional=False):
        try:
            fn = getattr(self.dll, name)
        except AttributeError:
            if optional: return
            raise SDKError(f"La función {name} no existe en esta DLL")
        fn.restype = restype
        if args is not None:
            fn.argtypes = args

    def _errmsg(self, code: int) -> str:
        self._errbuf = create_string_buffer(512)
        try:
            self.dll.fError(code, self._errbuf, 512)
            return self._errbuf.value.decode("latin-1", "ignore")
        except Exception:
            return f"Error {code}"

    def _chk(self, code: int, ctx: str):
        if code != 0:
            raise SDKError(f"{ctx} | SDK({code}): {self._errmsg(code)}")

    def login(self, user: str, pwd: str):
        fn = getattr(self.dll, "fInicioSesionSDK", None)
        if fn:
            self._chk(fn(user.encode("latin-1"), pwd.encode("latin-1")), "fInicioSesionSDK")

    def abre_empresa(self, ruta: str):
        self._chk(self.dll.fAbreEmpresa(ruta.encode("latin-1")), f"Abrir empresa: {ruta}")

    def cierra_empresa(self):
        try: self.dll.fCierraEmpresa()
        except Exception: pass

    def terminar(self):
        try: self.dll.fTerminaSDK()
        except Exception: pass


def get_sdk(dll_dir: str = None, paq_name: bytes = b"CONTPAQ I Comercial"):
    sdk = ComercialSDK(dll_dir, paq_name)
    sdk.load()
    return sdk
