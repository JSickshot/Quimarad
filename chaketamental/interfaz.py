import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

from xsd_manager import parse_xsd, flatten_structure
from xml_manager import load_xml, save_xml, build_addenda
from mapeo import build_cfdi_index, guess_value_for_field


class InterfazApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Addendas CFDI – Genérico (PPR/PHR/PUA/…)")
        self.root.geometry("1200x800")

        # Estado
        self.xml_tree = None
        self.xml_root = None
        self.cfdi_idx = {}
        self.xsd_root_name = None
        self.xsd_struct = {}
        self.field_paths = []
        self.entries = {}  # {path: Entry}

        # Top bar
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=8, pady=6)

        ttk.Button(bar, text="Cargar XML timbrado", command=self.cargar_xml).pack(side="left", padx=5)
        ttk.Button(bar, text="Cargar XSD (addenda)", command=self.cargar_xsd).pack(side="left", padx=5)
        ttk.Button(bar, text="Generar vista previa", command=self.generar_preview).pack(side="left", padx=5)
        ttk.Button(bar, text="Guardar XML con Addenda", command=self.guardar_xml).pack(side="left", padx=5)

        # Canvas con scroll para el formulario
        wrap = ttk.Frame(self.root)
        wrap.pack(fill="both", expand=True, padx=10, pady=8)

        self.canvas = tk.Canvas(wrap)
        self.vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.form_frame = ttk.Frame(self.canvas)

        self.form_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")

        # Vista previa
        ttk.Label(self.root, text="Vista previa del XML con Addenda:").pack(anchor="w", padx=10)
        self.preview = tk.Text(self.root, height=16, wrap="none")
        self.preview.pack(fill="both", expand=False, padx=10, pady=6)

        # scroll rueda mouse
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ---------- Acciones ----------
    def cargar_xml(self):
        ruta = filedialog.askopenfilename(filetypes=[("XML", "*.xml")])
        if not ruta:
            return
        self.xml_tree, self.xml_root = load_xml(ruta)
        self.cfdi_idx = build_cfdi_index(self.xml_root)
        messagebox.showinfo("OK", "XML timbrado cargado y analizado.")

    def cargar_xsd(self):
        ruta = filedialog.askopenfilename(filetypes=[("XSD", "*.xsd")])
        if not ruta:
            return
        self.xsd_root_name, self.xsd_struct = parse_xsd(ruta)
        self.field_paths = flatten_structure(self.xsd_struct, parent_path=self.xsd_root_name)
        self._render_form()

    def _render_form(self):
        # limpiar
        for w in self.form_frame.winfo_children():
            w.destroy()
        self.entries.clear()

        # Agrupar por primer nivel bajo la raíz del XSD para visual limpio
        groups = {}
        for p in self.field_paths:
            # p.ej: 'DSCargaRemisionProv/Remision/@Id' o 'DSCargaRemisionProv/Remision/Proveedor'
            parts = [x for x in p.split("/") if x]
            if len(parts) < 2:
                group = self.xsd_root_name
            else:
                group = parts[1]  # Remision, Pedidos, Articulos, etc.
            groups.setdefault(group, []).append(p)

        # Construir formulario por grupos
        for gname, paths in groups.items():
            lf = ttk.LabelFrame(self.form_frame, text=gname)
            lf.pack(fill="x", padx=6, pady=6)

            for path in sorted(paths):
                # Texto de etiqueta amigable
                label_txt = path.split("/")[-1]
                if "@" in label_txt:
                    label_txt = "@" + label_txt.split("@", 1)[1]

                ttk.Label(lf, text=label_txt, width=28, anchor="w").pack(anchor="w")

                entry = ttk.Entry(lf, width=80)

                # Prefill + lock si viene del CFDI
                val, editable = guess_value_for_field(path, self.cfdi_idx)
                if val:
                    entry.insert(0, val)
                    if not editable:
                        entry.state(["readonly"])  # bloquear
                entry.pack(fill="x", padx=6, pady=2)

                self.entries[path.replace(f"{self.xsd_root_name}/", "", 1)] = entry  # guardamos sin la raíz al inicio

    def generar_preview(self):
        if self.xml_root is None or not self.entries:
            messagebox.showwarning("Atención", "Carga primero XML y XSD.")
            return

        # Construir dict path->valor
        datos = {}
        for path, entry in self.entries.items():
            v = entry.get().strip()
            if v:
                datos[path] = v

        # Construir addenda en memoria (sin guardar aún)
        temp_root = ET.fromstring(ET.tostring(self.xml_root, encoding="utf-8"))
        build_addenda(temp_root, self.xsd_root_name, datos)
        pretty = ET.tostring(temp_root, encoding="utf-8").decode("utf-8")

        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", pretty)

    def guardar_xml(self):
        if self.xml_root is None or not self.entries:
            messagebox.showwarning("Atención", "Carga primero XML y XSD.")
            return

        datos = {}
        for path, entry in self.entries.items():
            v = entry.get().strip()
            if v:
                datos[path] = v

        # Inserta (o reemplaza) Addenda en el árbol actual
        build_addenda(self.xml_root, self.xsd_root_name, datos)

        ruta = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML", "*.xml")])
        if not ruta:
            return
        save_xml(self.xml_tree, ruta)
        messagebox.showinfo("OK", f"XML guardado con Addenda en:\n{ruta}")
