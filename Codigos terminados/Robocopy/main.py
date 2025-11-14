import os
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

salida_queue = queue.Queue()
current_proc = None

is_running = False
is_paused = False
stop_requested = False
stop_mode = None
last_origenes = []
last_destino = ""
current_index = 0
copy_mode = "full"

def agregar_origen():
    ruta = filedialog.askdirectory(title="robocopy")
    if ruta:
        lista_origenes.insert(tk.END, ruta)

def quitar_origen():
    seleccion = lista_origenes.curselection()
    if not seleccion:
        return
    for idx in reversed(seleccion):
        lista_origenes.delete(idx)

def seleccionar_destino():
    ruta = filedialog.askdirectory(title="destino")
    if ruta:
        destino_var.set(ruta)

def start_copy(origenes, destino_base, start_idx):

    def hilo_copia():
        global current_proc, is_running, is_paused, stop_requested, stop_mode, current_index

        peor_rc = 0
        errores = []

        for idx in range(start_idx, len(origenes)):
            if stop_requested:
                tag = "__PAUSED__" if stop_mode == "pause" else "__STOP__"
                salida_queue.put((tag, (peor_rc, errores)))
                is_running = False
                return

            origen = origenes[idx]
            current_index = idx

            nombre = os.path.basename(origen.rstrip("\\/")) or f"origen_{idx+1}"
            destino_final = os.path.join(destino_base, nombre)

            try:
                os.makedirs(destino_final, exist_ok=True)
            except Exception as e:
                salida_queue.put(f"\n[ERROR] No se pudo crear destino {destino_final}: {e}\n")
                peor_rc = max(peor_rc, 8)
                errores.append((origen, "No se pudo crear destino"))
                continue

            salida_queue.put(f"\n=== Carpeta {idx+1}/{len(origenes)} ===\n")
            salida_queue.put(f"Origen : {origen}\n")
            salida_queue.put(f"Destino: {destino_final}\n\n")

            origen_norm = os.path.normpath(origen)
            destino_norm = os.path.normpath(destino_final)

            cmd = [
                "robocopy",
                origen_norm,
                destino_norm,
                "/E",
                "/COPY:DAT",
                "/DCOPY:T",
                "/R:3",
                "/W:5",
                "/Z",
                "/FFT",
                "/MT:16",
                "/XA:SH",
                "/XJ",
                "/V",
                "/NP",
            ]
            if copy_mode == "no_overwrite":
                cmd += ["/XC", "/XN", "/XO"]

            salida_queue.put(" ".join(cmd) + "\n\n")

            creation_flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creation_flags = subprocess.CREATE_NO_WINDOW

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="cp1252",
                    errors="ignore",
                    shell=False,
                    creationflags=creation_flags
                )
                current_proc = proc

                for linea in proc.stdout:
                    if stop_requested:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        break
                    salida_queue.put(linea)

                rc = proc.wait()
                current_proc = None

                if stop_requested:
                    tag = "__PAUSED__" if stop_mode == "pause" else "__STOP__"
                    salida_queue.put(f"\n proceso detenido. \n")
                    salida_queue.put((tag, (peor_rc, errores)))
                    is_running = False
                    return

                current_index = idx + 1

                salida_queue.put(f"\n carpeta terminada, código: {rc}\n")
                peor_rc = max(peor_rc, rc)
                if rc >= 8:
                    errores.append((origen, rc))

            except FileNotFoundError:
                msg = "robocopy faltante"
                salida_queue.put(msg + "\n")
                peor_rc = max(peor_rc, 16)
                errores.append((origen, msg))
                is_running = False
                salida_queue.put(("__DONE__", (peor_rc, errores)))
                return
            except Exception as e:
                msg = f"Error inesperado al copiar {origen}: {e}"
                salida_queue.put(msg + "\n")
                peor_rc = max(peor_rc, 16)
                errores.append((origen, msg))
                is_running = False
                salida_queue.put(("__DONE__", (peor_rc, errores)))
                return

        is_running = False
        salida_queue.put(("__DONE__", (peor_rc, errores)))

    t = threading.Thread(target=hilo_copia, daemon=True)
    t.start()


def ejecutar_robocopy(modo="full"):
    global last_origenes, last_destino, is_running, is_paused, stop_requested, stop_mode, current_index, copy_mode

    if is_running:
        messagebox.showinfo("Copia en curso", "Ya hay una copia ejecutándose.")
        return

    if is_paused:
        messagebox.showinfo("Copia pausada", "La copia está pausada. Usa 'Reanudar'.")
        return

    origenes = list(lista_origenes.get(0, tk.END))
    destino_base = destino_var.get().strip()

    if not origenes:
        messagebox.showerror("Faltan datos", "Agrega al menos una carpeta de origen.")
        return

    if not destino_base:
        messagebox.showerror("Faltan datos", "Selecciona una carpeta de destino.")
        return

    try:
        os.makedirs(destino_base, exist_ok=True)
    except Exception as e:
        messagebox.showerror("Error creando destino", str(e))
        return

    salida_text.delete("1.0", tk.END)
    salida_text.insert(tk.END, "Iniciando copia \n\n")
    root.update_idletasks()

    last_origenes = origenes
    last_destino = destino_base
    current_index = 0
    stop_requested = False
    stop_mode = None
    is_running = True
    is_paused = False
    copy_mode = modo 

    boton_ejecutar_todo.config(state="disabled")
    boton_ejecutar_solo_nuevos.config(state="disabled")
    boton_pausa.config(state="normal", text="Pausar")
    boton_detener.config(state="normal")

    start_copy(last_origenes, last_destino, current_index)
    root.after(50, actualizar_salida)


def on_pausa_reanudar():
    global stop_requested, stop_mode, is_paused, is_running

    if not is_running and not is_paused:
        return

    if is_running and not is_paused:
        stop_mode = "pause"
        stop_requested = True
        is_paused = True
        boton_pausa.config(text="Reanudando...")
        boton_pausa.config(state="disabled")
        return

    if is_paused and not is_running:
        if not last_origenes or not last_destino:
            messagebox.showerror("No hay copia previa", "No se encontró información para reanudar.")
            return

        stop_requested = False
        stop_mode = None
        is_paused = False
        is_running = True
        boton_pausa.config(text="Pausar", state="normal")
        boton_ejecutar_todo.config(state="disabled")
        boton_ejecutar_solo_nuevos.config(state="disabled")
        boton_detener.config(state="normal")

        salida_text.insert(tk.END, f"\n\n Reanudando copia \n")
        salida_text.see(tk.END)

        start_copy(last_origenes, last_destino, current_index)
        root.after(50, actualizar_salida)


def on_detener():
    global stop_requested, stop_mode, is_running, is_paused

    if not is_running and not is_paused:
        return

    if messagebox.askyesno("Detener copia", "¿Seguro?"):
        stop_mode = "stop"
        stop_requested = True
        boton_pausa.config(state="disabled")
        boton_detener.config(state="disabled")


def actualizar_salida():
    global is_running, is_paused, stop_requested, stop_mode

    max_items = 300  
    processed = 0

    try:
        while processed < max_items:
            item = salida_queue.get_nowait()
            processed += 1

            if isinstance(item, tuple):
                tag, data = item
                if tag == "__DONE__":
                    rc, errores = data
                    salida_text.insert(tk.END, f"\n Proceso terminado")
                    if errores:
                        salida_text.insert(tk.END, "\n Carpetas con error:\n")
                        for origen, info in errores:
                            salida_text.insert(tk.END, f"- {origen} - {info}\n")
                    salida_text.see(tk.END)

                    if rc < 8:
                        messagebox.showinfo("Completado", "Copias finalizadas")
                    else:
                        messagebox.showwarning(
                            "Advertencia",
                            "Hubo errores en alguna carpeta. Revisa la salida."
                        )

                    boton_ejecutar_todo.config(state="normal")
                    boton_ejecutar_solo_nuevos.config(state="normal")
                    boton_pausa.config(state="disabled", text="Pausar")
                    boton_detener.config(state="disabled")
                    is_running = False
                    is_paused = False
                    stop_requested = False
                    stop_mode = None

                elif tag == "__PAUSED__":
                    rc, errores = data
                    salida_text.insert(tk.END, "\n Copia pausada\n")
                    if errores:
                        salida_text.insert(tk.END, "\n Warnings antes de pausar:\n")
                        for origen, info in errores:
                            salida_text.insert(tk.END, f"- {origen} - {info}\n")
                    salida_text.see(tk.END)

                    is_running = False
                    is_paused = True
                    stop_requested = False
                    stop_mode = None

                    boton_pausa.config(text="Reanudar", state="normal")
                    boton_detener.config(state="normal")

                elif tag == "__STOP__":
                    rc, errores = data
                    salida_text.insert(tk.END, "\n  Copia CANCELADA \n")
                    if errores:
                        salida_text.insert(tk.END, "\n Warnings antes de cancelar:\n")
                        for origen, info in errores:
                            salida_text.insert(tk.END, f"- {origen} - {info}\n")
                    salida_text.see(tk.END)

                    is_running = False
                    is_paused = False
                    stop_requested = False
                    stop_mode = None

                    boton_ejecutar_todo.config(state="normal")
                    boton_ejecutar_solo_nuevos.config(state="normal")
                    boton_pausa.config(state="disabled", text="Pausar")
                    boton_detener.config(state="disabled")

            else:
                salida_text.insert(tk.END, item)
                salida_text.see(tk.END)

    except queue.Empty:
        pass

    if is_running or not salida_queue.empty() or is_paused:
        root.after(50, actualizar_salida)


def on_cerrar():
    global stop_requested, stop_mode, current_proc, is_running, is_paused

    if is_running or is_paused:
        salir = messagebox.askyesno(
            "Salir",
            "Hay una copia en curso o pausada."
        )
        if not salir:
            return

        stop_mode = "stop"
        stop_requested = True
        if current_proc is not None:
            try:
                current_proc.terminate()
            except Exception:
                pass

    root.destroy()

root = tk.Tk()
root.title("Robocopy")

main_frame = ttk.Frame(root, padding=10)
main_frame.grid(row=0, column=0, sticky="nsew")

root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=1)
main_frame.columnconfigure(2, weight=1)

ttk.Label(main_frame, text="Origen").grid(
    row=0, column=0, columnspan=3, sticky="w"
)

lista_origenes = tk.Listbox(main_frame, height=8, selectmode=tk.EXTENDED)
lista_origenes.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=5)

scroll_origen = ttk.Scrollbar(main_frame, orient="vertical", command=lista_origenes.yview)
scroll_origen.grid(row=1, column=3, sticky="ns")
lista_origenes.configure(yscrollcommand=scroll_origen.set)

ttk.Button(main_frame, text="Agregar carpeta", command=agregar_origen).grid(
    row=2, column=0, sticky="w", pady=5
)
ttk.Button(main_frame, text="Quitar", command=quitar_origen).grid(
    row=2, column=1, sticky="e", pady=5
)

destino_var = tk.StringVar(value=r"")

ttk.Label(main_frame, text="Destino").grid(
    row=3, column=0, sticky="w", pady=5
)
entrada_destino = ttk.Entry(main_frame, textvariable=destino_var)
entrada_destino.grid(row=3, column=1, sticky="ew", pady=5)
ttk.Button(main_frame, text="Destino", command=seleccionar_destino).grid(
    row=3, column=2, padx=5, pady=5
)

boton_ejecutar_todo = ttk.Button(
    main_frame,
    text="Copiar",
    command=lambda: ejecutar_robocopy("full")
)
boton_ejecutar_todo.grid(row=4, column=0, pady=10)

boton_ejecutar_solo_nuevos = ttk.Button(
    main_frame,
    text="Copia incremental",
    command=lambda: ejecutar_robocopy("no_overwrite")
)
boton_ejecutar_solo_nuevos.grid(row=4, column=1, pady=10)

boton_pausa = ttk.Button(
    main_frame,
    text="Pausar",
    command=on_pausa_reanudar,
    state="disabled"
)
boton_pausa.grid(row=4, column=2, pady=10, padx=5)

boton_detener = ttk.Button(
    main_frame,
    text="Detener",
    command=on_detener,
    state="disabled"
)
boton_detener.grid(row=4, column=3, pady=10, padx=5)

ttk.Label(main_frame, text="Robocopy:").grid(
    row=5, column=0, columnspan=4, sticky="w"
)

salida_text = tk.Text(main_frame, height=15, wrap="none")
salida_text.grid(row=6, column=0, columnspan=4, sticky="nsew", pady=5)

scroll_y = ttk.Scrollbar(main_frame, orient="vertical", command=salida_text.yview)
scroll_y.grid(row=6, column=4, sticky="ns")
salida_text.configure(yscrollcommand=scroll_y.set)

main_frame.rowconfigure(1, weight=1)
main_frame.rowconfigure(6, weight=1)

root.geometry("1000x600")
root.protocol("WM_DELETE_WINDOW", on_cerrar)

if __name__ == "__main__":
    root.mainloop()
