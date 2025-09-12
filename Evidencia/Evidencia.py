import customtkinter as ctk
from tkinter import filedialog, messagebox
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from PIL import ImageGrab
import os, time

pruebas = []

def seleccionar_imagen():
    archivo = filedialog.askopenfilename(filetypes=[("Imágenes", "*.png;*.jpg;*.jpeg")])
    return archivo if archivo else None

def pegar_desde_portapapeles():
    
    img = ImageGrab.grabclipboard()
    if img:
        filename = f"clipboard_{int(time.time())}.png"
        img.save(filename, "PNG")
        return filename
    else:
        messagebox.showwarning("Portapapeles vacío", "No se encontró ninguna imagen en el portapapeles.")
        return None

def agregar_prueba(tipo):
    ventana = ctk.CTkToplevel(root)
    ventana.title(f"Nueva prueba - {tipo}")
    ventana.geometry("500x400")

    ctk.CTkLabel(ventana, text=f"Nombre de la prueba ({tipo}):").pack(pady=5)
    entry_nombre = ctk.CTkEntry(ventana, width=300)
    entry_nombre.pack(pady=5)

    img_paths = {"antes": None, "despues": None, "ingreso": None}

    def cargar_img(campo):
        img_paths[campo] = seleccionar_imagen()
        if img_paths[campo]:
            messagebox.showinfo("Imagen cargada", f"{campo.capitalize()}: {img_paths[campo]}")

    def pegar_img(campo):
        img_paths[campo] = pegar_desde_portapapeles()
        if img_paths[campo]:
            messagebox.showinfo("Imagen pegada", f"{campo.capitalize()} desde portapapeles.")

    for campo, color in [("antes","orange"),("despues","green"),("ingreso","blue")]:
        frame = ctk.CTkFrame(ventana)
        frame.pack(pady=10)
        ctk.CTkLabel(frame, text=f"Imagen {campo.capitalize()}").grid(row=0, column=0, padx=5)
        ctk.CTkButton(frame, text="img", fg_color=color, command=lambda c=campo: cargar_img(c)).grid(row=0, column=1, padx=5)
        ctk.CTkButton(frame, text="pegar", fg_color="gray", command=lambda c=campo: pegar_img(c)).grid(row=0, column=2, padx=5)

    def guardar():
        nombre = entry_nombre.get().strip()
        if not nombre:
            nombre = f"{tipo} {len(pruebas) + 1}"
        prueba = {
            "tipo": tipo,
            "nombre": nombre,
            "img_antes": img_paths["antes"],
            "img_despues": img_paths["despues"],
            "img_ingreso": img_paths["ingreso"]
        }
        pruebas.append(prueba)
        ventana.destroy()
        messagebox.showinfo("Guardado", f"Prueba '{nombre}' agregada con éxito")

    ctk.CTkButton(ventana, text="Guardar", fg_color="blue", command=guardar).pack(pady=20)

def generar_pdf():
    if not pruebas:
        messagebox.showwarning("Sin datos", "No has agregado ninguna prueba.")
        return

    archivo = filedialog.asksaveasfilename(defaultextension=".pdf",
                                           filetypes=[("PDF files", "*.pdf")],
                                           title="Guardar evidencia como...")
    if not archivo:
        return

    doc = SimpleDocTemplate(archivo, pagesize=A4)
    elementos = []
    estilos = getSampleStyleSheet()
    estilo_titulo = estilos["Title"]
    estilo_normal = estilos["Normal"]

    elementos.append(Paragraph(f"Servicio - {titulo_entry.get()}", estilo_titulo))
    elementos.append(Spacer(1, 20))

    for i, p in enumerate(pruebas, start=1):
        elementos.append(Paragraph(f"{p['nombre']} ({p['tipo']})", estilo_normal))
        elementos.append(Spacer(1, 10))

        if p["img_antes"]:
            elementos.append(Paragraph("Antes:", estilo_normal))
            elementos.append(Image(p["img_antes"], width=450, height=300))
        if p["img_despues"]:
            elementos.append(Paragraph("Después:", estilo_normal))
            elementos.append(Image(p["img_despues"], width=450, height=300))
        if p["img_ingreso"]:
            elementos.append(Paragraph("Prueba de Ingreso:", estilo_normal))
            elementos.append(Image(p["img_ingreso"], width=450, height=300))

        elementos.append(Spacer(1, 30))

    doc.build(elementos)
    messagebox.showinfo("Éxito", f"PDF en:\n{archivo}")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Servicio")
root.geometry("550x450")

title = ctk.CTkLabel(root, text="Servicio", font=("Arial", 22))
title.pack(pady=20)

ctk.CTkLabel(root, text="Cliente:").pack(pady=5)
titulo_entry = ctk.CTkEntry(root, width=300)
titulo_entry.pack(pady=5)

btn_servidor = ctk.CTkButton(root, text=" Servidor", width=250, height=50, fg_color="green", command=lambda: agregar_prueba("Servidor"))
btn_servidor.pack(pady=10)

btn_terminal = ctk.CTkButton(root, text=" Terminal (es)", width=250, height=50, fg_color="orange", command=lambda: agregar_prueba("Terminal"))
btn_terminal.pack(pady=10)

btn_pdf = ctk.CTkButton(root, text="Guardar", width=250, height=50, fg_color="blue", command=generar_pdf)
btn_pdf.pack(pady=30)

root.mainloop()
