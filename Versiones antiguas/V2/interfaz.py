import tkinter as tk
from tkinter import filedialog, messagebox
from observacion import generar_observacion
from xml_generador import generar_xml
from guardar import guardartxt
from PIL import Image, ImageTk
import os, sys, errno

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

archivos_excel = []
tickets = []

def agregar_excel():
    rutas = filedialog.askopenfilenames(
        title="Selecciona uno o más archivos Excel",
        filetypes=[("Archivos Excel", "*.xlsx *.xls")]
    )
    for ruta in rutas:
        if ruta not in archivos_excel:
            archivos_excel.append(ruta)
            lista_excel.insert(tk.END, ruta)

def nuevo_ticket():
    folio = entry_folio.get()
    referencia = entry_referencia.get()

    if not folio or not referencia:
        messagebox.showerror("Error", "Ingresa Folio y Referencia")
        return
    if not archivos_excel:
        messagebox.showerror("Error", "Carga al menos un archivo Excel")
        return

    observaciones = ""
    for ruta in archivos_excel:
        try:
            observaciones += generar_observacion(ruta)
        except PermissionError:
            messagebox.showwarning(
                "Archivo en uso",
                f"El archivo está abierto en otra aplicación:\n\n{ruta}\n\n"
                "Por favor CIÉRRELO e inténtelo de nuevo."
            )
            return
        except Exception as e:
            messagebox.showerror("Error", f"Problema con {ruta}:\n{e}")
            return
        
    tickets.append({
        "folio": folio,
        "referencia": referencia,
        "observacion": observaciones,
        "excels": archivos_excel.copy()
    })

    resumen_text.insert(tk.END, f"Ticket Folio={folio}, Referencia={referencia}\n")
    for ex in archivos_excel:
        resumen_text.insert(tk.END, f"   - {ex}\n")
    resumen_text.insert(tk.END, "\n")

    entry_folio.delete(0, tk.END)
    entry_referencia.delete(0, tk.END)
    archivos_excel.clear()
    lista_excel.delete(0, tk.END)

def generar_xml_gui():
    if not tickets:
        messagebox.showerror("Error", "No hay tickets almacenados")
        return

    salida_txt = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Archivo TXT", "*.txt")],
        title="Guardar archivo como"
    )
    if not salida_txt:
        return

    try:
        contenido = ""
        for t in tickets:
            contenido += (
                f'<Ticket Folio="{t["folio"]}" '
                f'Referencia="{t["referencia"]}" '
                f'Observacion="{t["observacion"]}"/>\n'
            )

        xml = f"<cfdi:Addenda>\n    <Tickets>\n{contenido}    </Tickets>\n</cfdi:Addenda>"

        guardartxt(xml, salida_txt)

        messagebox.showinfo("Éxito", f"Archivo generado en:\n{salida_txt}")
        lbl_salida.config(text=f"Se guardó en:\n{salida_txt}")

        tickets.clear()
        archivos_excel.clear()
        resumen_text.delete(1.0, tk.END)
        lista_excel.delete(0, tk.END)
        entry_folio.delete(0, tk.END)
        entry_referencia.delete(0, tk.END)
        lbl_salida.config(text="No se ha generado el archivo")

    except OSError as e:
        if e.errno == errno.EACCES:
            messagebox.showwarning(
                "Archivo en uso",
                f"No se pudo guardar porque el archivo está abierto:\n\n"
                f"{salida_txt}\n\n"
                "Por favor CIÉRRELO (Excel, Bloc de notas u otra aplicación) y vuelve a intentarlo."
            )
        else:
            messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{e}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{e}")

def crear_interfaz():
    global entry_folio, entry_referencia, lista_excel, lbl_salida, resumen_text

    root = tk.Tk()
    root.title("Quimarad Consulting Group - Addendas")
    root.state("zoomed")
    root.configure(bg="#fcfcfc")

    try:
        root.iconbitmap(resource_path("logo.ico"))
    except Exception as e:
        print(f"No se pudo cargar el icono: {e}")

    header_frame = tk.Frame(root, bg="#000000")
    header_frame.pack(fill="x")

    titulo = tk.Label(
        header_frame,
        text="Quimarad Consulting Group",
        font=("Arial", 16, "bold"),
        bg="#000000",
        fg="white",
        pady=10
    )
    titulo.pack(side="left", padx=15)

    try:
        logo_img = Image.open(resource_path("logo.jpg"))
        logo_img = logo_img.resize((40, 40), Image.LANCZOS)
        logo_tk = ImageTk.PhotoImage(logo_img)

        logo_label = tk.Label(header_frame, image=logo_tk, bg="#000000")
        logo_label.image = logo_tk
        logo_label.pack(side="right", padx=15)
    except Exception as e:
        print(f"No se pudo cargar el logo: {e}")

    frame_datos = tk.LabelFrame(root, text="Addenda", padx=10, pady=10, bg="#f4f6f9")
    frame_datos.pack(fill="x", padx=15, pady=10)

    tk.Label(frame_datos, text="Folio:", bg="#f4f6f9").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    entry_folio = tk.Entry(frame_datos, width=50)
    entry_folio.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(frame_datos, text="Referencia:", bg="#f4f6f9").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    entry_referencia = tk.Entry(frame_datos, width=50)
    entry_referencia.grid(row=1, column=1, padx=5, pady=5)

    frame_central = tk.Frame(root, bg="#fcfcfc")
    frame_central.pack(fill="both", expand=True, padx=15, pady=10)

    frame_excel = tk.LabelFrame(frame_central, text="Carga de archivos Excel", padx=10, pady=10, bg="#f4f6f9")
    frame_excel.pack(side="left", fill="both", expand=True, padx=10, pady=5)

    btns_frame = tk.Frame(frame_excel, bg="#f4f6f9")
    btns_frame.pack(fill="x", pady=5)

    tk.Button(btns_frame, text="Nuevo Ticket", command=nuevo_ticket,
              bg="#001E72", fg="white").pack(side="left", padx=5)
    tk.Button(btns_frame, text="Agregar Excel", command=agregar_excel,
              bg="#001E72", fg="white").pack(side="left", padx=5)

    lista_excel = tk.Listbox(frame_excel, height=10, selectmode=tk.SINGLE)
    lista_excel.pack(fill="both", expand=True, padx=5, pady=5)

    frame_resumen = tk.LabelFrame(frame_central, text="Tickets", padx=10, pady=10, bg="#f4f6f9")
    frame_resumen.pack(side="right", fill="both", expand=True, padx=10, pady=5)

    resumen_text = tk.Text(frame_resumen, height=20, wrap="word", bg="white")
    resumen_text.pack(fill="both", expand=True)

    frame_salida = tk.LabelFrame(root, text="Archivo Generado", padx=10, pady=10, bg="#f4f6f9")
    frame_salida.pack(fill="x", padx=15, pady=10)

    lbl_salida = tk.Label(frame_salida, text="Aún no se ha generado el archivo", fg="gray", bg="#f4f6f9")
    lbl_salida.pack()

    frame_botones = tk.Frame(root, bg="#fcfcfc")
    frame_botones.pack(pady=15)

    tk.Button(frame_botones, text="Generar TXT", command=generar_xml_gui,
              bg="#001E72", fg="white", font=("Arial", 12, "bold"), width=15).pack(side="left", padx=10)

    root.mainloop()

if __name__ == "__main__":
    crear_interfaz()
