import sys, os, time, tempfile
import customtkinter as ctk
from tkinter import filedialog, messagebox
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from PIL import ImageGrab, Image as PILImage, ImageTk, ImageOps
from datetime import datetime

def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel_path)

ICON_PATH = resource_path("logo.ico") 
LOGO_PATH = resource_path("logo.png")  

COLOR_BG = "#0D0D0D"
COLOR_FG = "#FFFFFF"
COLOR_ACCENT = "#B51D1D"
COLOR_ACCENT_2 = "#262626"
BTN_HEIGHT = 56
ENTRY_WIDTH = 420
THUMB_SIZE = 130
TEMP_DIR = tempfile.gettempdir()

pruebas = []  

def seleccionar_imagenes():
    rutas = filedialog.askopenfilenames(
        title="Seleccionar imágenes",
        filetypes=[("Imágenes", "*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp")],
    )
    return list(rutas) if rutas else []

def pegar_desde_portapapeles():
    img = ImageGrab.grabclipboard()
    if img:
        filename = os.path.join(TEMP_DIR, f"clipboard_{int(time.time())}.png")
        img.save(filename, "PNG")
        return filename
    else:
        messagebox.showwarning("Portapapeles vacío", "No se encontró ninguna imagen en el portapapeles.")
        return None

def _rlimage_fit(path, max_w=450, max_h=650):
    try:
        with PILImage.open(path) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            scale = min(max_w / float(w), max_h / float(h), 1.0)
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            if scale < 1.0:
                tmp = os.path.join(TEMP_DIR, f"fit_{int(time.time()*1000)}.png")
                im.resize((new_w, new_h), PILImage.LANCZOS).save(tmp, "PNG")
                return RLImage(tmp, width=new_w, height=new_h)
            return RLImage(path, width=new_w, height=new_h)
    except Exception:
        return RLImage(path, width=max_w, height=max_h)

def _make_thumb(path, size=THUMB_SIZE):
    with PILImage.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((size, size), PILImage.LANCZOS)
        return ImageTk.PhotoImage(im)

class Gallery(ctk.CTkScrollableFrame):
    def __init__(self, master, title, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.configure(fg_color=COLOR_ACCENT_2)
        self.title = title
        self.paths = []
        self._thumb_refs = []

        head = ctk.CTkLabel(self, text=f"{title}: 0 imagen(es)", text_color=COLOR_FG)
        head.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 6))
        self.counter_label = head

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,8))
        self.grid_columnconfigure(0, weight=1)

    def add_paths(self, new_paths):
        self.paths.extend(new_paths); self._refresh()

    def add_one(self, path):
        self.paths.append(path); self._refresh()

    def _refresh(self):
        for w in self.container.winfo_children(): w.destroy()
        self._thumb_refs.clear()
        self.counter_label.configure(text=f"{self.title}: {len(self.paths)} imagen(es)")

        cols = 2
        for idx, p in enumerate(self.paths):
            r, c = divmod(idx, cols)
            card = ctk.CTkFrame(self.container, fg_color="#1E1E1E", corner_radius=12)
            card.grid(row=r, column=c, padx=10, pady=10, sticky="n")

            try: thumb = _make_thumb(p)
            except Exception: thumb = _make_thumb(p) if os.path.exists(p) else None
            lbl_img = ctk.CTkLabel(card, text="", image=thumb) if thumb else ctk.CTkLabel(card, text="(sin vista)")
            lbl_img.pack(padx=8, pady=(8,4))
            if thumb: self._thumb_refs.append(thumb)

            name = os.path.basename(p)
            ctk.CTkLabel(card, text=name, text_color=COLOR_FG, wraplength=160, justify="center").pack(padx=8, pady=(0,6))

            btns = ctk.CTkFrame(card, fg_color="transparent"); btns.pack(pady=(0,8))
            ctk.CTkButton(btns, width=28, height=28, text="arriba",
                          fg_color=COLOR_ACCENT, hover_color="#8F1616",
                          command=lambda i=idx: self._move_up(i)).pack(side="left", padx=4)
            ctk.CTkButton(btns, width=28, height=28, text="abajo",
                          fg_color=COLOR_ACCENT, hover_color="#8F1616",
                          command=lambda i=idx: self._move_down(i)).pack(side="left", padx=4)
            ctk.CTkButton(btns, width=28, height=28, text="quitar",
                          fg_color="#3C3C3C", hover_color="#2F2F2F",
                          command=lambda i=idx: self._remove(i)).pack(side="left", padx=4)

        total_rows = (len(self.paths)+cols-1)//cols
        for rr in range(total_rows): self.container.grid_rowconfigure(rr, weight=0)
        for cc in range(cols): self.container.grid_columnconfigure(cc, weight=1)

    def _move_up(self, i):
        if i <= 0: return
        self.paths[i-1], self.paths[i] = self.paths[i], self.paths[i-1]; self._refresh()

    def _move_down(self, i):
        if i >= len(self.paths)-1: return
        self.paths[i+1], self.paths[i] = self.paths[i], self.paths[i+1]; self._refresh()

    def _remove(self, i):
        if 0 <= i < len(self.paths):
            del self.paths[i]; self._refresh()

def agregar_prueba(tipo):
    ventana = ctk.CTkToplevel(root)
    ventana.title(f"- {tipo}")
    ventana.geometry("920x820")
    ventana.minsize(920, 820)
    ventana.configure(fg_color=COLOR_BG)
    ventana.grab_set()
    ventana.grid_rowconfigure(1, weight=1)
    ventana.grid_columnconfigure(0, weight=1)

    try:
        ventana.iconbitmap(ICON_PATH)
    except Exception:
        try:
            ventana.iconphoto(False, ImageTk.PhotoImage(file=LOGO_PATH))
        except Exception:
            pass

    top_frame = ctk.CTkFrame(ventana, fg_color="transparent")
    top_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

    ctk.CTkLabel(top_frame, text=f" ({tipo}):", text_color=COLOR_FG)\
        .pack(pady=(0, 4), anchor="w")
    entry_nombre = ctk.CTkEntry(top_frame, width=ENTRY_WIDTH, fg_color=COLOR_ACCENT_2, text_color=COLOR_FG)
    entry_nombre.pack(pady=(0, 8), anchor="w")

    frame_botones = ctk.CTkFrame(top_frame, fg_color="transparent")
    frame_botones.pack(fill="x", pady=(4, 0))

    contenedor_galerias = ctk.CTkFrame(ventana, fg_color="transparent")
    contenedor_galerias.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
    contenedor_galerias.grid_columnconfigure((0,1,2), weight=1)
    contenedor_galerias.grid_rowconfigure(0, weight=1)

    gal_antes   = Gallery(contenedor_galerias, "Antes",   width=280, height=520)
    gal_despues = Gallery(contenedor_galerias, "Después", width=280, height=520)
    gal_ingreso = Gallery(contenedor_galerias, "Ingreso", width=280, height=520)

    gal_antes.grid(row=0, column=0, sticky="nsew", padx=6)
    gal_despues.grid(row=0, column=1, sticky="nsew", padx=6)
    gal_ingreso.grid(row=0, column=2, sticky="nsew", padx=6)

    def seleccionar(gal: Gallery):
        nuevas = seleccionar_imagenes()
        if nuevas:
            gal.add_paths(nuevas)
            messagebox.showinfo("Imágenes agregadas", f"Se agregaron {len(nuevas)} imagen(es) a {gal.title}.")

    def pegar(gal: Gallery):
        pegada = pegar_desde_portapapeles()
        if pegada:
            gal.add_one(pegada)

    def fila_botones(nombre, galeria):
        fila = ctk.CTkFrame(frame_botones, fg_color="transparent")
        fila.pack(side="left", expand=True, padx=8, pady=6, fill="x")
        ctk.CTkLabel(fila, text=nombre, text_color=COLOR_FG).pack()
        inner = ctk.CTkFrame(fila, fg_color="transparent"); inner.pack(pady=4)
        ctk.CTkButton(inner, text="Agregar archivos", height=36,
                      fg_color=COLOR_ACCENT, hover_color="#8F1616",
                      command=lambda g=galeria: seleccionar(g)).pack(side="left", padx=6)
        ctk.CTkButton(inner, text="Pegar", height=36,
                      fg_color="#3C3C3C", hover_color="#2F2F2F",
                      command=lambda g=galeria: pegar(g)).pack(side="left", padx=6)

    fila_botones("Antes",   gal_antes)
    fila_botones("Después", gal_despues)
    fila_botones("Ingreso", gal_ingreso)

    bottom_bar = ctk.CTkFrame(ventana, fg_color=COLOR_BG)
    bottom_bar.grid(row=2, column=0, sticky="ew")
    bottom_bar.grid_columnconfigure(0, weight=1)

    def guardar():
        nombre = entry_nombre.get().strip() or f"{tipo} {len(pruebas)+1}"
        imgs = {"antes": gal_antes.paths, "despues": gal_despues.paths, "ingreso": gal_ingreso.paths}
        if all(len(v) == 0 for v in imgs.values()):
            if not messagebox.askyesno("Sin imágenes", "No agregaste imágenes. ¿Guardar de todas formas?"):
                return
        pruebas.append({"tipo": tipo, "nombre": nombre, "imgs": imgs})
        ventana.destroy()
        messagebox.showinfo("Guardado", f" '{nombre}' agregada con éxito")

    ctk.CTkButton(
        bottom_bar, text="Guardar", height=BTN_HEIGHT,
        fg_color=COLOR_ACCENT, hover_color="#8F1616", command=guardar
    ).grid(row=0, column=0, pady=12, padx=12, sticky="ew")

def generar_pdf():
    if not pruebas:
        messagebox.showwarning("Sin datos", "No has agregado ninguna prueba.")
        return

    archivo = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        initialfile=f"QCG {(titulo_entry.get().strip() or 'Cliente')}_{datetime.now():%Y%m%d}.pdf",
        filetypes=[("PDF", "*.pdf")],
        title="Guardar como"
    )
    if not archivo:
        return

    doc = SimpleDocTemplate(
        archivo,
        pagesize=(595.27, 841.89),  # A4
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )
    elementos, estilos = [], getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("BrandTitle", parent=estilos["Title"], alignment=TA_CENTER, textColor="#111111")
    estilo_seccion = estilos["Normal"]

    cliente = titulo_entry.get().strip() or "Sin cliente"
    elementos.append(Paragraph(f"Servicio - {cliente}", estilo_titulo))
    elementos.append(Spacer(1, 18))

    for i, p in enumerate(pruebas, start=1):
        elementos.append(Paragraph(f"{i}. {p['nombre']} ({p['tipo']})", estilo_seccion))
        elementos.append(Spacer(1, 6))
        for etiqueta, encabezado in [("antes", "Antes"), ("despues", "Después"), ("ingreso", "Prueba de Ingreso")]:
            fotos = p["imgs"].get(etiqueta, [])
            if not fotos: continue
            elementos.append(Paragraph(f"{encabezado} ({len(fotos)}):", estilo_seccion))
            elementos.append(Spacer(1, 4))
            for ruta in fotos:
                try:
                    elementos.append(_rlimage_fit(ruta, max_w=450, max_h=650))
                    elementos.append(Spacer(1, 8))
                except Exception:
                    elementos.append(Paragraph(f"[No se pudo insertar: {os.path.basename(ruta)}]", estilo_seccion))
                    elementos.append(Spacer(1, 6))
        elementos.append(Spacer(1, 18))

    try:
        doc.build(elementos)
        messagebox.showinfo("Éxito", f"PDF generado en:\n{archivo}")
    except Exception as e:
        messagebox.showerror("Error al generar PDF", f"Ocurrió un error:\n{e}")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.title("Evidencia")
root.geometry("900x780")
root.configure(fg_color=COLOR_BG)

try:
    root.iconbitmap(ICON_PATH)
except Exception:
    try:
        root.iconphoto(False, ImageTk.PhotoImage(file=LOGO_PATH))
    except Exception:
        pass

header = ctk.CTkFrame(root, fg_color=COLOR_BG)
header.pack(fill="x", pady=(10, 0))
logo_label = ctk.CTkLabel(header, text="")
try:
    if os.path.exists(LOGO_PATH):
        pil_logo = PILImage.open(LOGO_PATH)
        max_w = 120
        scale = min(1.0, max_w / pil_logo.width)
        logo_img = pil_logo.resize((int(pil_logo.width*scale), int(pil_logo.height*scale)), PILImage.LANCZOS)
        logo_tk = ImageTk.PhotoImage(logo_img)
        logo_label.configure(image=logo_tk)
        logo_label.image = logo_tk
except Exception:
    pass
logo_label.pack(pady=(0, 6))

title = ctk.CTkLabel(root, text="QCG - Evidencias",
                     font=("Segoe UI", 22, "bold"), text_color=COLOR_FG)
title.pack(pady=6)

cliente_frame = ctk.CTkFrame(root, fg_color=COLOR_ACCENT_2, corner_radius=14)
cliente_frame.pack(pady=14, padx=16, fill="x")
ctk.CTkLabel(cliente_frame, text="Cliente:", text_color=COLOR_FG).pack(pady=(10, 2))
titulo_entry = ctk.CTkEntry(cliente_frame, width=ENTRY_WIDTH, fg_color="#1E1E1E", text_color=COLOR_FG)
titulo_entry.pack(pady=(0, 10))

botones = ctk.CTkFrame(root, fg_color="transparent")
botones.pack(pady=6)
ctk.CTkButton(botones, text=" Servidor", width=320, height=BTN_HEIGHT,
              fg_color=COLOR_ACCENT, hover_color="#8F1616",
              command=lambda: agregar_prueba("Servidor")).pack(pady=8, side="left", padx=8)
ctk.CTkButton(botones, text=" Terminal", width=320, height=BTN_HEIGHT,
              fg_color="#3C3C3C", hover_color="#2F2F2F",
              command=lambda: agregar_prueba("Terminal")).pack(pady=8, side="left", padx=8)

ctk.CTkButton(root, text="Generar PDF", width=320, height=BTN_HEIGHT,
              fg_color=COLOR_ACCENT, hover_color="#8F1616",
              command=generar_pdf).pack(pady=20)

footer = ctk.CTkLabel(root, text="By Sick", text_color="#9E9E9E", font=("Segoe UI", 12))
footer.pack(pady=(0, 10))

root.mainloop()
