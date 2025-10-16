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

def _zip_dir(src_dir: str, zip_path: str):

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        base_len = len(src_dir.rstrip("\\/")) + 1
        for root, _, files in os.walk(src_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = fpath[base_len:]
                try:
                    zf.write(fpath, arcname)
                except Exception:
                    pass

def run_copy_task(instance: str, data_src: str, emp_src: str, root_dst: str, log_cb=None):

    if not instance:
        raise ValueError("Indica la instancia SQL.")
    if not data_src or not os.path.isdir(data_src):
        raise ValueError("DATA ORIGEN inválida.")
    if not emp_src or not os.path.isdir(emp_src):
        raise ValueError("Empresas (origen) inválida.")
    if not root_dst:
        raise ValueError("Indica carpeta raíz de destino.")

    os.makedirs(root_dst, exist_ok=True)
    zip_path = os.path.join(root_dst, f"DATA_{_tstamp()}.zip")
    emp_dst  = os.path.join(root_dst, f"Empresas_{_tstamp()}")
    os.makedirs(emp_dst, exist_ok=True)

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    svc = service_name_from_instance(instance)
    log(f" Deteniendo {svc} …")
    try:
        stop_service_safely(svc, log_cb=log)
    except SysOpError as ex:
        raise

    log(f" Comprimiendo DATA  {zip_path}")
    _zip_dir(data_src, zip_path)

    try:
        log(f"Mapeando Empresas  {emp_dst}")
        out = robocopy(emp_src, emp_dst, ["/E", "/XF", "*.*"])
        if out:
            log(out)
    except Exception:
        pass

    log(f"> Iniciando {svc} …")
    try:
        start_service_safely(svc, log_cb=log)
    except SysOpError as ex:
        raise

    return zip_path, emp_dst
