import os
import sys
import argparse
import ctypes
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

APP_NAME = "Optimizador"
DEFAULT_LOGO_FILE = "logo.png" 
DEFAULT_ICO_FILE  = "logo.ico"   

LOG_DIR = Path(tempfile.gettempdir()) / "optimizador_windows_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"optimizador_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def relaunch_as_admin():
    params = " ".join([f'"{a}"' for a in sys.argv])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)

def run(cmd, shell=False, check=False):
    log(f"CMD: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, shell=shell, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.stdout or ""
        if out.strip():
            for ln in out.splitlines():
                log(ln)
        if check and p.returncode != 0:
            raise subprocess.CalledProcessError(p.returncode, cmd, out)
        return p.returncode, out
    except Exception as e:
        log(f"ERROR ejecutando comando: {e}")
        return 1, str(e)

def run_stream(cmd):
    log(f"STREAM: {cmd}")
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True)
        for line in iter(p.stdout.readline, ''):
            if line:
                log(line.rstrip())
        p.stdout.close()
        rc = p.wait()
        return rc
    except Exception as e:
        log(f"ERROR stream: {e}")
        return 1

def powershell(ps_cmd: str):
    return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd])

def delete_path(path: Path, preview: bool):
    try:
        if path.exists():
            if preview:
                log(f"[Preview] Borraría: {path}")
                return
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            else:
                shutil.rmtree(path, ignore_errors=True)
            log(f"Eliminado: {path}")
    except Exception as e:
        log(f"No se pudo eliminar {path}: {e}")

def resource_path(relative: str) -> Path:
    """
    Devuelve la ruta real de un recurso tanto en modo script como congelado (PyInstaller).
    """
    try:
        base_path = Path(sys._MEIPASS) 
    except Exception:
        base_path = Path(__file__).resolve().parent
    return (base_path / relative).resolve()

def detect_logo_path(custom_logo: str | None) -> Path | None:

    if custom_logo:
        p = Path(custom_logo)
        if p.exists():
            return p.resolve()
    candidate = resource_path(DEFAULT_LOGO_FILE)
    if candidate.exists():
        return candidate
    local = Path(__file__).with_name(DEFAULT_LOGO_FILE)
    if local.exists():
        return local.resolve()
    return None

def set_console_title(title: str):
    try:
        os.system(f"title {title}")
    except Exception:
        pass

def print_banner(logo_path: Path | None):
    print("=" * 60)
    print(f"{APP_NAME}".center(60))
    print("Mantenimiento y optimización de Windows".center(60))
    if logo_path:
        print(f"Logo: {logo_path}".center(60))
    else:
        print("(Logo no encontrado)".center(60))
    print("=" * 60)

def open_logo(logo_path: Path | None):

    if not logo_path or not logo_path.exists():
        log("No se encontró el logo para mostrar.")
        return
    log(f"Abrir logo: {logo_path}")
    try:
        os.startfile(str(logo_path))  
    except Exception as e:
        log(f"No se pudo abrir el logo: {e}")

def clean_temp(preview=False):
    log("== Limpieza: temporales usuario/sistema ==")
    for p in [Path(os.getenv("TEMP") or ""), Path(r"C:\Windows\Temp")]:
        if p and p.exists():
            for item in p.glob("*"):
                delete_path(item, preview)

def empty_recycle_bin(preview=False):
    log("== Vaciar Papelera ==")
    if preview:
        log("[Preview] Vaciaría la Papelera")
        return
    powershell("Clear-RecycleBin -Force")

def stop_update_services():
    for s in ["wuauserv", "bits", "dosvc"]:
        run(["sc", "stop", s])

def start_update_services():
    for s in ["wuauserv", "bits", "dosvc"]:
        run(["sc", "start", s])

def clean_windows_update(preview=False):
    log("== Limpieza: caché Windows Update y Delivery Optimization ==")
    stop_update_services()
    delete_path(Path(r"C:\Windows\SoftwareDistribution\Download"), preview)
    do_cache = Path(r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache")
    delete_path(do_cache, preview)
    start_update_services()

def clean_thumbnails(preview=False):
    log("== Limpieza: caché de miniaturas del usuario ==")
    thumb_dir = Path(os.getenv("LOCALAPPDATA") or "") / r"Microsoft\Windows\Explorer"
    if thumb_dir.exists():
        for f in thumb_dir.glob("thumbcache*.db"):
            delete_path(f, preview)

def clean_browsers(preview=False):
    log("== Limpieza: cachés de navegadores (Chrome/Edge/Brave) ==")
    base = Path(os.getenv("LOCALAPPDATA") or "")
    targets = [
        base / r"Google\Chrome\User Data\Default\Cache",
        base / r"Microsoft\Edge\User Data\Default\Cache",
        base / r"BraveSoftware\Brave-Browser\User Data\Default\Cache",
    ]
    for t in targets:
        delete_path(t, preview)

def dism_analyze():
    log("== DISM: AnalyzeComponentStore ==")
    return run_stream(["Dism.exe", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"])

def dism_start_component_cleanup(aggressive=False):
    log("== DISM: StartComponentCleanup ==")
    cmd = ["Dism.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"]
    if aggressive:
        log("** Modo agresivo /ResetBase: no podrás desinstalar updates antiguos **")
        cmd.append("/ResetBase")
    return run_stream(cmd)

def dism_restore_health():
    log("== DISM: RestoreHealth ==")
    return run_stream(["Dism.exe", "/Online", "/Cleanup-Image", "/RestoreHealth"])

def sfc_scannow():
    log("== SFC: /scannow ==")
    return run_stream(["sfc", "/scannow"])

def detect_media_type() -> str:
    rc, out = powershell("(Get-PhysicalDisk | Select -First 1).MediaType")
    if rc == 0 and out:
        mt = out.strip().splitlines()[-1].strip()
        return mt
    return "Unknown"

def optimize_volume(drive_letter="C"):
    media = detect_media_type()
    log(f"Tipo de disco detectado: {media}")
    if media.upper() == "SSD":
        log(f"TRIM en {drive_letter}:")
        powershell(f"Optimize-Volume -DriveLetter {drive_letter} -ReTrim")
    else:
        log(f"Desfragmentación en {drive_letter}:")
        powershell(f"Optimize-Volume -DriveLetter {drive_letter} -Defrag -Verbose")

def top_big_files(root="C:\\", top=20):
    log(f"== Top {top} archivos por tamaño en {root} (informativo) ==")
    ps = (
        f"Get-ChildItem '{root}' -Recurse -Force -ErrorAction SilentlyContinue | "
        f"Where-Object {{ -not $_.PSIsContainer }} | "
        f"Sort-Object Length -Descending | "
        f"Select-Object -First {top} FullName,@{{n='MB';e={{[math]::Round($_.Length/1MB,2)}}}} | "
        f"Format-Table -Auto"
    )
    powershell(ps)

def main():
    ap = argparse.ArgumentParser(
        description=f"{APP_NAME} (limpieza, DISM, SFC, optimización de disco). Requiere administrador."
    )
    ap.add_argument("--preview", action="store_true", help="Modo simulación: no borra, solo registra acciones.")
    ap.add_argument("--browsers", action="store_true", help="Limpiar cachés de navegadores (Chrome/Edge/Brave).")
    ap.add_argument("--aggressive", action="store_true", help="DISM StartComponentCleanup con /ResetBase.")
    ap.add_argument("--skip-dism", action="store_true", help="Saltar DISM.")
    ap.add_argument("--skip-sfc", action="store_true", help="Saltar SFC /scannow.")
    ap.add_argument("--no-optimize", action="store_true", help="No optimizar volumen (TRIM/Defrag).")
    ap.add_argument("--drive", default="C", help="Letra de unidad a optimizar (por defecto C).")
    ap.add_argument("--top", type=int, default=0, help="Mostrar TOP N archivos más grandes (0 = no mostrar).")
    ap.add_argument("--logo-path", default="", help="Ruta manual al PNG del logo (opcional).")
    ap.add_argument("--show-logo", action="store_true", help="Abrir el logo con el visor por defecto.")
    args = ap.parse_args()

    set_console_title(APP_NAME)
    logo_resolved = detect_logo_path(args.logo_path or None)
    print_banner(logo_resolved)

    log(f"Log: {LOG_FILE}")
    if logo_resolved:
        log(f"Logo detectado: {logo_resolved}")
    else:
        log("Logo no encontrado (opcional).")

    if args.show_logo:
        open_logo(logo_resolved)

    if not is_admin():
        log("Elevando privilegios de administrador...")
        relaunch_as_admin()
        sys.exit(0)

    clean_temp(preview=args.preview)
    empty_recycle_bin(preview=args.preview)
    clean_windows_update(preview=args.preview)
    clean_thumbnails(preview=args.preview)
    if args.browsers:
        clean_browsers(preview=args.preview)

    if not args.skip_dism:
        dism_analyze()
        dism_start_component_cleanup(aggressive=args.aggressive)
        dism_restore_health()
    if not args.skip_sfc:
        sfc_scannow()

    if not args.no_optimize:
        optimize_volume(args.drive.upper().rstrip(":"))

    if args.top and args.top > 0:
        try:
            top_big_files("C:\\", args.top)
        except Exception as e:
            log(f"No se pudo listar archivos grandes: {e}")

    log("== Finalizado. ==")
    log(f"Revisa el log: {LOG_FILE}")

if __name__ == "__main__":
    main()
