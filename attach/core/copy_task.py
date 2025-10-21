import os
import zipfile
import datetime as _dt

from core.sysops import (
    service_name_from_instance,
    stop_service_safely,
    start_service_safely,
    robocopy,
    SysOpError,
)

def _tstamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

def _zip_dir_with_progress(src_dir: str, zip_path: str, progress_cb=None, base_pct=15.0, span_pct=80.0):

    total = 0
    for root, _, files in os.walk(src_dir):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(root, fname))
            except Exception:
                pass
    done = 0
    if progress_cb:
        progress_cb(base_pct, "Comprimiendo")

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        base_len = len(src_dir.rstrip("\\/")) + 1
        for root, _, files in os.walk(src_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = fpath[base_len:]
                try:
                    zf.write(fpath, arcname)
                    try:
                        done += os.path.getsize(fpath)
                    except Exception:
                        pass
                except Exception:
                    pass

                if progress_cb and total > 0:
                    frac = min(1.0, done / total)
                    pct = base_pct + frac * span_pct
                    progress_cb(pct, f" Comprimiendo Data  {int(frac*100)}%")

    if progress_cb:
        progress_cb(base_pct + span_pct, "Compresión finalizada.")

def run_copy_task(instance: str, data_src: str, emp_src: str, root_dst: str, log_cb=None, progress_cb=None):

    if not instance: raise ValueError("Indica la instancia SQL.")
    if not data_src or not os.path.isdir(data_src): raise ValueError("DATA ORIGEN inválida.")
    if not emp_src or not os.path.isdir(emp_src): raise ValueError("Empresas (origen) inválida.")
    if not root_dst: raise ValueError("Indica carpeta raíz de destino.")

    os.makedirs(root_dst, exist_ok=True)
    zip_path = os.path.join(root_dst, f"DATA_{_tstamp()}.zip")
    emp_dst  = os.path.join(root_dst, f"Empresas_{_tstamp()}")
    os.makedirs(emp_dst, exist_ok=True)

    def log(msg: str):
        if log_cb: log_cb(msg)

    if progress_cb: progress_cb(0.0, "Iniciando")

    svc = service_name_from_instance(instance)
    try:
        log(f" Deteniendo {svc} ...")
        if progress_cb: progress_cb(10.0, f"Deteniendo servicio {svc}...")
        stop_service_safely(svc, log_cb=log)
    except SysOpError:
        raise

    _zip_dir_with_progress(data_src, zip_path, progress_cb=progress_cb, base_pct=15.0, span_pct=80.0)

    try:
        log("Mapeando empresas ")
        if progress_cb: progress_cb(96.0, "Copiando estructura de Empresas")
        out = robocopy(emp_src, emp_dst, [
            "/E","/XF", "*.*","/R:1", "/W:1","/NFL", "/NDL", "/NP"
        ])
        log(out)
    except Exception:
        pass

    try:
        log(f"Iniciando {svc} ...")
        if progress_cb: progress_cb(98.0, f"Iniciando servicio {svc}...")
        start_service_safely(svc, log_cb=log)
    except SysOpError as ex:
        log(f"Advertencia Servicio: {ex}")

    if progress_cb: progress_cb(100.0, "Listo.")
    return zip_path, emp_dst
