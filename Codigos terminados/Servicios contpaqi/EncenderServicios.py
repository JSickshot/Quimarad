# -*- coding: utf-8 -*-
import subprocess
import threading
from queue import Queue
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk 

SERVICIOS = [
    "Servidor CONTPAQ i",
    "Servidor de Licencias Compac - Comun",
    "Servidor de Licencias Compac - CONTPAQ i® NÓMINAS",
    "Servidor de Licencias Compac (V4)",
    "Servidor de Licencias CONTPAQ i® XMLenLinea",
    "Servidor de Licencias CONTPAQ i®",
    "Servidor de AuthServer Compac - CONTPAQ i® NÓMINAS",
    "Servidor de AuthServer Compac (V4)",
    "Servidor de AuthServer CONTPAQI",
    "Servidor de AuthServer_XMLenLinea",
    "Servidor de aplicaciones Contpaqi",
]
ui_queue = Queue()


def ejecutar_comando(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


def ui_event(evento: tuple):
    ui_queue.put(evento)


def procesar_ui_queue():
    while not ui_queue.empty():
        evento = ui_queue.get_nowait()
        tipo = evento[0]

        if tipo == "init":
            total, texto = evento[1], evento[2]
            progress_bar["maximum"] = total
            progress_bar["value"] = 0
            lbl_status.config(text=texto)
            btn_iniciar.config(state="disabled")
            btn_detener.config(state="disabled")

        elif tipo == "step":
            progress_bar["value"] = progress_bar["value"] + 1

        elif tipo == "done_iniciar":
            ok_iniciados = evento[1]
            lbl_status.config(text="Inicio completado.")
            btn_iniciar.config(state="normal")
            btn_detener.config(state="normal")

            if ok_iniciados:
                servicios_txt = "\n".join(f"- {s}" for s in ok_iniciados)
                msg = (
                    "Los siguientes servicios se iniciaron correctamente:\n\n"
                    f"{servicios_txt}"
                )
            else:
                msg = "No se pudo confirmar ningún servicio iniciado correctamente."

            messagebox.showinfo("Inicio de servicios CONTPAQi", msg)

        elif tipo == "done_detener":
            ok_detenidos = evento[1]
            lbl_status.config(text="Detención completada.")
            btn_iniciar.config(state="normal")
            btn_detener.config(state="normal")

            if ok_detenidos:
                servicios_txt = "\n".join(f"- {s}" for s in ok_detenidos)
                msg = (
                    "Los siguientes servicios se detuvieron correctamente:\n\n"
                    f"{servicios_txt}"
                )
            else:
                msg = "No se pudo confirmar ningún servicio detenido correctamente."

            messagebox.showinfo("Detención de servicios CONTPAQi", msg)

    root.after(100, procesar_ui_queue)


def _iniciar_worker():
    ok_iniciados = []
    ui_event(("init", len(SERVICIOS), "Iniciando servicios CONTPAQi..."))

    for display_name in SERVICIOS:
        code, out = ejecutar_comando(f'net start "{display_name}"')
        salida = (out or "").lower()

        if code == 0:
            ok_iniciados.append(display_name)
        else:

            pass

        ui_event(("step",))

    ui_event(("done_iniciar", ok_iniciados))


def _detener_worker():
    ok_detenidos = []
    ui_event(("init", len(SERVICIOS), "Deteniendo servicios CONTPAQi..."))

    for display_name in reversed(SERVICIOS):
        code, out = ejecutar_comando(f'net stop "{display_name}" /y')
        salida = (out or "").lower()

        if code == 0:
            ok_detenidos.append(display_name)
        else:
            pass

        ui_event(("step",))

    ui_event(("done_detener", ok_detenidos))


def iniciar_servicio():
    threading.Thread(target=_iniciar_worker, daemon=True).start()


def detener_servicio():
    if not messagebox.askyesno(
        "Confirmar",
        "¿Seguro que quieres DETENER los servicios CONTPAQi?"
    ):
        return
    threading.Thread(target=_detener_worker, daemon=True).start()

root = tk.Tk()
root.title("Servicios CONTPAQi - QCG")
root.geometry("600x200")

try:
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    icon_path = base_path / "logo.ico"
    root.iconbitmap(icon_path)
except Exception:
    pass

frame_botones = tk.Frame(root)
frame_botones.pack(padx=10, pady=10, fill="x")

btn_iniciar = tk.Button(
    frame_botones,
    text="Iniciar servicios",
    width=18,
    command=iniciar_servicio
)
btn_iniciar.pack(side="left", padx=5)

btn_detener = tk.Button(
    frame_botones,
    text="Detener servicios",
    width=18,
    command=detener_servicio
)
btn_detener.pack(side="left", padx=5)

btn_salir = tk.Button(
    frame_botones,
    text="Salir",
    width=10,
    command=root.destroy
)
btn_salir.pack(side="right", padx=5)

frame_status = tk.Frame(root)
frame_status.pack(padx=10, pady=(10, 5), fill="x")

lbl_status = tk.Label(frame_status, text="Listo.", anchor="w")
lbl_status.pack(side="top", fill="x")

progress_bar = ttk.Progressbar(frame_status, orient="horizontal", mode="determinate")
progress_bar.pack(side="top", fill="x", pady=3)

procesar_ui_queue()
root.mainloop()
