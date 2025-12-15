# -*- coding: utf-8 -*-
from __future__ import annotations
import os, ctypes
from dataclasses import dataclass
from typing import Optional, List

class SDKError(RuntimeError): ...
class SDKNotFound(SDKError): ...
class SDKArchMismatch(SDKError): ...

def _is_32bit_python() -> bool: return ctypes.sizeof(ctypes.c_void_p) == 4
def _norm(p: str) -> str: return os.path.normpath(p.rstrip("\\/"))
def _exists_file(p: str) -> bool:
    try: return os.path.isfile(p)
    except Exception: return False

def _candidate_paths_for_sdk(drives: List[str]) -> List[str]:
    folders = [
        r"{drv}:\Program Files (x86)\Compac\COMERCIAL\SDK",
        r"{drv}:\Program Files (x86)\Compac\Comercial\SDK",
        r"{drv}:\Program Files (x86)\CONTPAQI\Comercial\SDK",
        r"{drv}:\Archivos de programa (x86)\Compac\COMERCIAL\SDK",
        r"{drv}:\Archivos de programa (x86)\CONTPAQI\Comercial\SDK",
        r"{drv}:\CONTPAQI\Comercial\SDK",
        r"{drv}:\Compac\Comercial\SDK",
        r"{drv}:\Program Files (x86)\Compac\COMERCIAL\bin",
        r"{drv}:\Archivos de programa (x86)\Compac\COMERCIAL\bin",
        r"{drv}:\CONTPAQI\Comercial\bin",
    ]
    return [_norm(f.format(drv=d)) for d in drives for f in folders]

def _candidate_paths_for_cac(drives: List[str]) -> List[str]:
    folders = [
        r"{drv}:\Program Files (x86)\Compac\COMERCIAL",
        r"{drv}:\Program Files (x86)\CONTPAQI\Comercial",
        r"{drv}:\Archivos de programa (x86)\Compac\COMERCIAL",
        r"{drv}:\Archivos de programa (x86)\CONTPAQI\Comercial",
        r"{drv}:\CONTPAQI\Comercial",
        r"{drv}:\Compac\Comercial",
    ]
    return [_norm(f.format(drv=d)) for d in drives for f in folders]

def _find_first_existing(paths: List[str], filename: str) -> Optional[str]:
    for p in paths:
        if os.path.basename(p).lower()==filename.lower() and _exists_file(p): return _norm(p)
    for base in paths:
        cand=_norm(os.path.join(base, filename))
        if _exists_file(cand): return cand
    return None

def _list_drives(include_remote: bool = True) -> List[str]:
    drives=[]
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1<<i):
                drv=f"{chr(ord('A')+i)}:"
                if not include_remote:
                    if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drv+"\\"))==4: continue
                drives.append(drv)
    except Exception:
        for d in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.isdir(f"{d}:\\"): drives.append(f"{d}:")
    return drives


class _DllAPI:
    def __init__(self, dll_path: str):
        self.dll = ctypes.WinDLL(dll_path, use_last_error=True)

        self._fn_abre_empresa=None
        self._fn_alta_doc=None; self._fn_alta_mov=None; self._fn_guarda=None
        self._fn_set_doc=None; self._set_doc_mode=None
        self._fn_set_mov=None; self._set_mov_mode=None
        self._fn_errorA=getattr(self.dll,"fError",None); self._fn_errorW=getattr(self.dll,"fErrorW",None)

        # Tabla de Folios
        self._fn_pos1_folio=None; self._fn_next_folio_row=None
        self._fn_read_folio=None; self._folio_mode=None

    def _bind0(self, names: List[str]):
        last=None
        for n in names:
            try:
                f=getattr(self.dll,n); f.restype=ctypes.c_int
                return f
            except Exception as e: last=e
        raise SDKError(f"No se encontró ninguna de: {names} ({last})")

    def _bind_text_setter(self, base_names: List[str]):
        for nm in [b+"W" for b in base_names]:
            try:
                f=getattr(self.dll,nm); f.restype=ctypes.c_int
                f.argtypes=[ctypes.c_wchar_p, ctypes.c_wchar_p]
                return f,"wide",None
            except Exception: pass
        for nm in base_names:
            try:
                f=getattr(self.dll,nm); f.restype=ctypes.c_int
                f.argtypes=[ctypes.c_char_p, ctypes.c_char_p]
                return f,"ansi",None
            except Exception: pass
        raise SDKError(f"No se encontró variante para {base_names}")

    @staticmethod
    def _arg(mode: str, s: str):
        return ctypes.c_wchar_p(s) if mode=="wide" else ctypes.c_char_p(s.encode("latin-1","ignore"))

    def set_nombre_paq(self, nombre: str) -> int:
        fn = getattr(self.dll,"fSetNombrePAQW",None)
        if fn:
            fn.restype=ctypes.c_int; fn.argtypes=[ctypes.c_wchar_p]
            return fn(ctypes.c_wchar_p(nombre))
        fn = getattr(self.dll,"fSetNombrePAQ",None)
        if fn:
            fn.restype=ctypes.c_int; fn.argtypes=[ctypes.c_char_p]
            return fn(ctypes.c_char_p(nombre.encode("latin-1","ignore")))
        raise SDKError("La DLL no expone fSetNombrePAQ / fSetNombrePAQW")

    def open_company(self, path: str) -> int:
        if self._fn_abre_empresa is None:
            self._fn_abre_empresa = getattr(self.dll,"fAbreEmpresaW",None) or getattr(self.dll,"fAbreEmpresa",None)
            if self._fn_abre_empresa is None: raise SDKError("No se encontró fAbreEmpresa(W)")
            self._fn_abre_empresa.restype=ctypes.c_int
            if self._fn_abre_empresa.__name__.endswith("W"):
                self._fn_abre_empresa.argtypes=[ctypes.c_wchar_p]
            else:
                self._fn_abre_empresa.argtypes=[ctypes.c_char_p]
        if self._fn_abre_empresa.__name__.endswith("W"):
            return self._fn_abre_empresa(ctypes.c_wchar_p(path))
        return self._fn_abre_empresa(ctypes.c_char_p(path.encode("latin-1","ignore")))

    def fAltaDocumento(self) -> int:
        if self._fn_alta_doc is None: self._fn_alta_doc=self._bind0(["fAltaDocumento"])
        return self._fn_alta_doc()

    def fAltaMovimiento(self) -> int:
        if self._fn_alta_mov is None: self._fn_alta_mov=self._bind0(["fAltaMovimiento"])
        return self._fn_alta_mov()

    def fGuardaDocumento(self) -> int:
        if self._fn_guarda is None: self._fn_guarda=self._bind0(["fGuardaDocumento"])
        return self._fn_guarda()

    def _ensure_setters(self):
        if self._fn_set_doc is None:
            self._fn_set_doc, self._set_doc_mode,_ = self._bind_text_setter(["fSetDatoDocumento","fSetDatoDocto"])
        if self._fn_set_mov is None:
            self._fn_set_mov, self._set_mov_mode,_ = self._bind_text_setter(["fSetDatoMovimiento","fSetDatoMovto"])

    def set_doc(self, field: str, value: str) -> int:
        self._ensure_setters()
        f=self._fn_set_doc; mode=self._set_doc_mode
        try:
            return f(self._arg(mode,field), self._arg(mode,value))
        except (TypeError, ctypes.ArgumentError):
            return f(self._arg(mode,field), self._arg(mode,value), ctypes.c_int(len(value)))

    def set_mov(self, field: str, value: str) -> int:
        self._ensure_setters()
        f=self._fn_set_mov; mode=self._set_mov_mode
        try:
            return f(self._arg(mode,field), self._arg(mode,value))
        except (TypeError, ctypes.ArgumentError):
            return f(self._arg(mode,field), self._arg(mode,value), ctypes.c_int(len(value)))

    # --------- Folios (robusto) ----------
    def _bind_folio_table(self):
        if self._fn_pos1_folio and self._fn_next_folio_row and self._fn_read_folio:
            return
        self._fn_pos1_folio = self._bind0(["fPosPrimerFolio"])
        self._fn_next_folio_row = self._bind0(["fPosSiguienteFolio"])
        for nm in ["fLeeDatoFolioW","fLeeDatoFolio"]:
            fn=getattr(self.dll,nm,None)
            if fn:
                fn.restype=ctypes.c_int
                self._fn_read_folio = fn
                self._folio_mode = "wide" if nm.endswith("W") else "ansi"
                return
        raise SDKError("La DLL no expone fLeeDatoFolio(W).")

    def _read_folio_field(self, field: str, buflen=1024) -> tuple[int,str]:
        fn=self._fn_read_folio; mode=self._folio_mode
        n = ctypes.c_int(buflen)
        if mode=="wide":
            buf=ctypes.create_unicode_buffer(buflen)
        else:
            buf=ctypes.create_string_buffer(buflen)
        try:
            rc = fn(self._arg(mode,field), buf, ctypes.byref(n))
        except (TypeError, ctypes.ArgumentError):
            rc = fn(self._arg(mode,field), buf, n.value)
        if rc!=0: return rc, ""
        if mode=="wide": return 0, buf.value
        return 0, buf.value.decode("latin-1","ignore")

    def next_folio(self, concepto: str, serie: str) -> tuple[int,int]:
        try:
            self._bind_folio_table()
        except Exception:
            return 1, 0

        rc = self._fn_pos1_folio()
        last = 0
        while rc == 0:
            ok_serie = False
            for fld in ("cSerie","cCodigoSerie","cIdSerie","cCodigo"):
                r,v = self._read_folio_field(fld)
                if r==0 and v.strip()==serie.strip():
                    ok_serie = True; break

            ok_conc = True
            for fld in ("cCodConcepto","cCodigoConcepto","cIdConcepto","cConcepto"):
                r,v = self._read_folio_field(fld)
                if r==0 and v.strip():
                    ok_conc = (v.strip()==concepto.strip()); break

            if ok_serie and ok_conc:
                for ff in ("cUltimoFolio","cFolio","cUltimo","cFolioUsado","cConsecutivo"):
                    r,v = self._read_folio_field(ff)
                    if r==0 and v.strip().isdigit():
                        try:
                            last = max(last, int(v.strip()))
                            break
                        except Exception:
                            pass
            rc = self._fn_next_folio_row()

        if last>0: return 0, last+1
        return 1, 0

    def series_for_concept(self, concepto: str) -> list[str]:
        """Lista de series que existen en la tabla de folios para ese concepto (seguro)."""
        try:
            self._bind_folio_table()
        except Exception:
            return []
        rc = self._fn_pos1_folio()
        series=set()
        while rc == 0:
            conc_match=False
            for fld in ("cCodConcepto","cCodigoConcepto","cIdConcepto","cConcepto"):
                r,v = self._read_folio_field(fld)
                if r==0 and v.strip()==concepto.strip():
                    conc_match=True; break
            if conc_match:
                for fld in ("cSerie","cCodigoSerie","cIdSerie","cCodigo"):
                    r,v = self._read_folio_field(fld)
                    if r==0 and v.strip():
                        series.add(v.strip()); break
            rc = self._fn_next_folio_row()
        return sorted(series)

    def error_text(self, rc: int) -> str:
        try:
            if self._fn_errorW:
                self._fn_errorW.restype=ctypes.c_wchar_p; self._fn_errorW.argtypes=[ctypes.c_int]
                msg=self._fn_errorW(ctypes.c_int(rc))
                if msg: return msg
            if self._fn_errorA:
                self._fn_errorA.restype=ctypes.c_char_p; self._fn_errorA.argtypes=[ctypes.c_int]
                msg=self._fn_errorA(ctypes.c_int(rc))
                if msg: return msg.decode("latin-1","ignore")
        except Exception: pass
        COMMON={0:"OK",73:"Campo inválido en esta DLL.",100:"Nombre de campo desconocido.",
                601:"Campo no visible o no disponible.",602:"Campo de sólo lectura.",
                99980:"No se encontró CAC.ini.",42101:"La fecha no es válida."}
        return COMMON.get(rc, f"rc={rc}")


@dataclass
class ComercialSDK:
    sdk_dir: str
    dll_file: str
    cac_dir: str
    dll: _DllAPI

def _discover_sdk(sdk_dir_hint: Optional[str] = None) -> tuple[str,str]:
    env_file=os.environ.get("COMPAC_SDK_FILE")
    env_dir =os.environ.get("COMPAC_SDK_DIR") or os.environ.get("COMPAC_SDK_PATH")
    hints=[]
    if sdk_dir_hint: hints.append(_norm(sdk_dir_hint))
    if env_dir:      hints.append(_norm(env_dir))
    if env_file:     hints.append(_norm(env_file))
    dll=_find_first_existing(hints,"MGWSERVICIOS.DLL")
    if not dll:
        drives=_list_drives(include_remote=True)
        dll=_find_first_existing(_candidate_paths_for_sdk(drives),"MGWSERVICIOS.DLL")
    if not dll: raise SDKNotFound("No se encontró MGWSERVICIOS.DLL del SDK de CONTPAQi Comercial.")
    return dll, _norm(os.path.dirname(dll))

def _discover_cac_dir() -> Optional[str]:
    env=os.environ.get("COMPAC_CAC_DIR")
    paths=[]
    if env: paths.append(_norm(env))
    paths.append(_norm(os.getcwd()))
    drives=_list_drives(include_remote=True)
    paths.extend(_candidate_paths_for_cac(drives))
    cac=_find_first_existing(paths,"CAC.ini")
    return _norm(os.path.dirname(cac)) if cac else None

def get_sdk(sdk_dir_hint: Optional[str] = None) -> ComercialSDK:
    if not _is_32bit_python():
        raise SDKArchMismatch("El SDK de Comercial es de 32 bits. Ejecuta Python x86 (py -3.11-32).")

    dll_file, sdk_dir = _discover_sdk(sdk_dir_hint)
    os.environ["PATH"] = sdk_dir + os.pathsep + os.environ.get("PATH","")
    api = _DllAPI(dll_file)

    cac_dir = _discover_cac_dir() or _norm(os.path.join(sdk_dir, os.pardir)) or sdk_dir
    if not _exists_file(os.path.join(cac_dir,"CAC.ini")):
        cac_dir = sdk_dir

    prev = os.getcwd()
    try:
        os.chdir(cac_dir)
        rc = api.set_nombre_paq("CONTPAQ I Comercial")
        if rc != 0:
            raise SDKError(f"fSetNombrePAQ rc={rc}: {api.error_text(rc)}. Verifica CAC.ini en {cac_dir}")
    finally:
        os.chdir(prev)

    return ComercialSDK(sdk_dir=sdk_dir, dll_file=dll_file, cac_dir=cac_dir, dll=api)

__all__ = ["ComercialSDK","get_sdk","SDKError","SDKNotFound","SDKArchMismatch","_list_drives"]
