import os
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import dbf 

log_queue = queue.Queue()

root = None
text_log = None


def enqueue_log(message: str):
    log_queue.put(message)


def procesar_tabla(path: str, old: str, new: str, log_fn):
    log_fn(f"viendo: {path}")
    table = dbf.Table(path)
    table.open(dbf.READ_WRITE)
    try:
        field_names = list(table.field_names)

        for record in table:
            with record as rec:
                for name in field_names:
                    value = rec[name]

                    if isinstance(value, str) and old in value:
                        rec[name] = value.replace(old, new)
    finally:
        table.close()


def recorrer_compacw(root_path: str, old: str, new: str, log_fn):
    total_dbf = 0
    log_fn(f"Buscando en: {root_path}")
    log_fn(f"Cambiando '{old}' por '{new}'")

    for dirpath, dirnames, filenames in os.walk(root_path):
        for filename in filenames:
            if filename.lower().endswith(".dbf"):
                full_path = os.path.join(dirpath, filename)
                try:
                    procesar_tabla(full_path, old, new, log_fn)
                    total_dbf += 1
                except Exception as e:
                    log_fn(f"Error en {full_path}: {e}")

    log_fn(f"Terminado ")
    return total_dbf


def seleccionar_carpeta(entry_widget: tk.Entry):
    carpeta = filedialog.askdirectory(title="Selecciona carpeta COMPACW")
    if carpeta:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, carpeta)


def iniciar_proceso(entry_root, entry_old, entry_new, btn_iniciar):
    root_path = entry_root.get().strip()
    old = entry_old.get().strip()
    new = entry_new.get().strip()

    if not root_path:
        messagebox.showwarning("Falta", "Selecciona la carpeta Compacw.")
        return
    if not os.path.isdir(root_path):
        messagebox.showerror("Ruta invalida", f"La carpeta no existe:\n{root_path}")
        return
    if not old:
        messagebox.showwarning("Falta ruta vieja", "Escribe la ruta actual.")
        return
    if not new:
        messagebox.showwarning("Falta ruta nueva", "Escribe la ruta nueva.")
        return

    msg = (
        f"ruta:\n{root_path}\n\n"
        f"Ruta actual:\n{old}\n\n"
        f"Ruta nueva:\n{new}\n\n"
        "Respalda COMPACW antes de continuar.\n\n"
   
    )
    if not messagebox.askyesno("Respalda primero", msg):
        return

    text_log.delete("1.0", tk.END)
    btn_iniciar.config(state=tk.DISABLED)
    root.update_idletasks()

    def worker():
        try:
            total = recorrer_compacw(root_path, old, new, enqueue_log)
            enqueue_log(f"Revisa")
            root.after(
                0,
                lambda: messagebox.showinfo(
                    "Proceso terminado"
                ),
            )
        finally:
            root.after(0, lambda: btn_iniciar.config(state=tk.NORMAL))

    hilo = threading.Thread(target=worker, daemon=True)
    hilo.start()


def process_log_queue():
    try:
        while True:
            msg = log_queue.get_nowait()
            text_log.insert(tk.END, msg + "\n")
            text_log.see(tk.END)
    except queue.Empty:
        pass
    root.after(100, process_log_queue)


def crear_interfaz():
    global root, text_log
    root = tk.Tk()
    root.title("Ruta masivo")

    main_frame = ttk.Frame(root, padding=10)
    main_frame.grid(row=0, column=0, sticky="nsew")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    ttk.Label(main_frame, text="Carpeta COMPACW").grid(
        row=0, column=0, sticky="w"
    )
    entry_root = ttk.Entry(main_frame, width=60)
    entry_root.grid(row=1, column=0, sticky="we", pady=2)
    btn_browse = ttk.Button(
        main_frame,
        text="Buscar...",
        command=lambda: seleccionar_carpeta(entry_root),
    )
    btn_browse.grid(row=1, column=1, padx=5)

    ttk.Label(main_frame, text="Ruta actual:").grid(
        row=2, column=0, sticky="w", pady=(10, 0)
    )
    entry_old = ttk.Entry(main_frame, width=60)
    entry_old.grid(row=3, column=0, columnspan=2, sticky="we", pady=2)

    ttk.Label(main_frame, text="Ruta nueva:").grid(
        row=4, column=0, sticky="w", pady=(10, 0)
    )
    entry_new = ttk.Entry(main_frame, width=60)
    entry_new.grid(row=5, column=0, columnspan=2, sticky="we", pady=2)

    btn_iniciar = ttk.Button(
        main_frame,
        text="Reemplazar",
        command=lambda: iniciar_proceso(
            entry_root, entry_old, entry_new, btn_iniciar
        ),
    )
    btn_iniciar.grid(row=6, column=0, columnspan=2, pady=(10, 5))

    ttk.Label(main_frame, text="Log del proceso:").grid(
        row=7, column=0, sticky="w", pady=(10, 0)
    )
    text_log = tk.Text(main_frame, width=80, height=20)
    text_log.grid(row=8, column=0, columnspan=2, sticky="nsew")

    scroll = ttk.Scrollbar(main_frame, orient="vertical", command=text_log.yview)
    scroll.grid(row=8, column=2, sticky="ns")
    text_log.configure(yscrollcommand=scroll.set)

    main_frame.rowconfigure(8, weight=1)
    main_frame.columnconfigure(0, weight=1)

    root.minsize(700, 500)

    # Arranca el ciclo que va leyendo la cola de log
    root.after(100, process_log_queue)

    return root


if __name__ == "__main__":
    app = crear_interfaz()
    app.mainloop()
