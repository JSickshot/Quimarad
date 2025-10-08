# core/sysops.py
import subprocess
import time
from typing import Sequence

class SysOpError(Exception):
    pass

def service_name_from_instance(instance: str) -> str:
    """
    MSSQLSERVER para instancia por defecto; MSSQL$NOMBRE para instancias nombradas.
    Ej.: localhost\COMPAC -> MSSQL$COMPAC
    """
    if "\\" in instance:
        inst = instance.split("\\", 1)[1].strip()
        return f"MSSQL${inst}"
    return "MSSQLSERVER"

def _run(cmd: Sequence[str]) -> subprocess.CompletedProcess:
    # Usa shell=False; captura salida para logging
    return subprocess.run(cmd, capture_output=True, text=True, check=False)

def _state_of(service: str) -> str:
    q = _run(["sc", "query", service])
    # Busca líneas tipo: STATE              : 4  RUNNING  / 1 STOPPED / 2 START PENDING
    for line in q.stdout.splitlines():
        if "STATE" in line:
            return line.strip()
    return q.stdout.strip() or q.stderr.strip()

def stop_service(service: str, timeout_s: int = 60) -> str:
    res = _run(["sc", "stop", service])
    out = res.stdout + res.stderr
    # Espera a que realmente esté detenido
    start = time.time()
    while time.time() - start < timeout_s:
        state = _state_of(service)
        if "STOPPED" in state:
            return out + "\n" + state
        time.sleep(1.0)
    raise SysOpError(f"No se pudo detener el servicio {service} en {timeout_s}s.\n{out}")

def start_service(service: str, timeout_s: int = 60) -> str:
    res = _run(["sc", "start", service])
    out = res.stdout + res.stderr
    start = time.time()
    while time.time() - start < timeout_s:
        state = _state_of(service)
        if "RUNNING" in state:
            return out + "\n" + state
        time.sleep(1.0)
    raise SysOpError(f"No se pudo iniciar el servicio {service} en {timeout_s}s.\n{out}")

def robocopy(src: str, dst: str, extra_args: Sequence[str]) -> str:
    """
    Ejecuta robocopy y devuelve stdout+stderr para log.
    OJO: robocopy devuelve códigos de salida no estándar (0,1,2…8…).
    NO usamos check=True.
    """
    cmd = ["robocopy", src, dst, *extra_args]
    res = _run(cmd)
    return f"$ {' '.join(cmd)}\n{res.stdout}\n{res.stderr}"
