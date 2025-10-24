# core/sysops.py
import os
import shlex
import subprocess
import time

class SysOpError(Exception):
    pass

def _run(cmd: list[str] | str, use_shell: bool = False) -> tuple[int, str]:

    if isinstance(cmd, str):
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=use_shell)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=use_shell)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()

def _run_sc(cmd: str) -> tuple[int, str]:

    return _run(cmd, use_shell=True)


_KNOWN_STATES = {
    "RUNNING", "STOPPED", "START_PENDING", "STOP_PENDING",
    "PAUSED", "CONTINUE_PENDING", "PAUSE_PENDING"
}

def _parse_state_from_sc_output(text: str) -> str:

    for line in text.splitlines():
        u = line.upper()
        if ("STATE" in u) or ("ESTADO" in u):
            parts = line.split(":", 1)
            tail = parts[1] if len(parts) == 2 else line
            tokens = [t.strip().upper() for t in tail.strip().split()]
            for token in reversed(tokens):
                if token in _KNOWN_STATES:
                    return token
    return "UNKNOWN"

def _service_exists(name: str) -> bool:
    rc, out = _run_sc(f'sc query "{name}"')
    if "1060" in out:
        return False
    if ("STATE" in out.upper()) or ("ESTADO" in out.upper()):
        return True
    return rc == 0

def _service_state(name: str) -> str:
    rc, out = _run_sc(f'sc query "{name}"')
    if rc != 0 and "1060" in out:
        return "NOT_FOUND"
    return _parse_state_from_sc_output(out)

def _wait_for_state(name: str, target: str, timeout_s: int = 180) -> bool:
    t0 = time.time()
    target = target.upper()
    while time.time() - t0 < timeout_s:
        st = _service_state(name)
        if st == target:
            return True
        time.sleep(1.0)
    return False


def service_name_from_instance(instance: str) -> str:

    inst = (instance or "").strip()
    if "\\" in inst:
        _, name = inst.split("\\", 1)
        name = name.strip()
        if not name or name.upper() == "MSSQLSERVER":
            return "MSSQLSERVER"
        return f"MSSQL${name}"
    up = inst.upper()
    if up.startswith("MSSQL$") or up == "MSSQLSERVER":
        return inst
    return "MSSQLSERVER"

def resolve_sql_service_name(instance: str) -> str:

    guess = service_name_from_instance(instance)
    candidates: list[str] = []
    inst = (instance or "").strip()

    if guess.upper().startswith("MSSQL$") or guess.upper() == "MSSQLSERVER":
        candidates.append(guess)

    if "\\" in inst:
        _, name = inst.split("\\", 1)
        name = name.strip()
        if name and name.upper() != "MSSQLSERVER":
            candidates.extend([
                f"MSSQL${name}",
                f"MSSQLS{name}", 
            ])

    if "MSSQLSERVER" not in [c.upper() for c in candidates]:
        candidates.append("MSSQLSERVER")

    seen = set()
    uniq = []
    for c in candidates:
        up = c.upper()
        if up not in seen:
            seen.add(up)
            uniq.append(c)

    for svc in uniq:
        if _service_exists(svc):
            return svc

    return guess

def stop_service(name: str) -> str:
    _, out = _run_sc(f'sc stop "{name}"')
    return out

def start_service(name: str) -> str:
    _, out = _run_sc(f'sc start "{name}"')
    return out

def stop_service_safely(main_service: str, log_cb=None) -> None:

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    svc = resolve_sql_service_name(main_service)
    log(f"> Deteniendo servicio {svc} …")

    rc, out = _run(f'net stop "{svc}" /y', use_shell=True)
    if out:
        log(out)

    st = _service_state(svc)
    if st == "RUNNING" or st == "START_PENDING" or st == "PAUSE_PENDING":
        rc2, out2 = _run_sc(f'sc stop "{svc}"')
        if out2:
            log(out2)

    if not _wait_for_state(svc, "STOPPED", timeout_s=240):
        st2 = _service_state(svc)
        raise SysOpError(f"No se pudo detener {svc} a tiempo (estado: {st2}).")

def start_service_safely(main_service: str, log_cb=None) -> None:

    def log(msg: str):
        if log_cb:
            log_cb(msg)

    svc = resolve_sql_service_name(main_service)
    log(f"> Iniciando servicio {svc} …")

    rc, out = _run(f'net start "{svc}"', use_shell=True)
    if out:
        log(out)

    st = _service_state(svc)
    if st != "RUNNING":
        rc2, out2 = _run_sc(f'sc start "{svc}"')
        if out2:
            log(out2)

    if not _wait_for_state(svc, "RUNNING", timeout_s=240):
        st2 = _service_state(svc)
        raise SysOpError(f"No se pudo iniciar {svc} a tiempo (estado: {st2}).")

def robocopy(src: str, dst: str, options: list[str] | None = None) -> str:

    if options is None:
        options = []
    cmd = ["robocopy", src, dst] + options
    rc, out = _run(" ".join(shlex.quote(x) for x in cmd), use_shell=True)
    return out
