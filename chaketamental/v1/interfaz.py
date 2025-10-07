import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import xml.etree.ElementTree as ET

from mapeo import (
    cargar_xsd, guardar_xsd, cargar_xsd_guardado,
    extraer_datos_factura, sugerir_autovalores
)
from xml_manager import construir_addenda

class InterfazApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Addendas global")
        self.root.geometry("1100x720")

        self.xml_path = None
        self.shapes = None
        self.factura_header = {}
        self.factura_conceptos = []
        self.campos = {}
        self.autofilled = set()

        wrap = tk.Frame(root)
        wrap.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(wrap, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.frame = tk.Frame(self.canvas)

        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")

        # scroll con la rueda del mouse
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # --- Barra de botones ---
        bar = tk.Frame(root)
        bar.pack(fill="x", pady=8)

        tk.Button(bar, text="Cargar XML timbrado", command=self.cargar_xml).pack(side="left", padx=6)
        tk.Button(bar, text="Cargar XSD", command=self.cargar_xsd_file).pack(side="left", padx=6)
        tk.Button(bar, text="Guardar esquema XSD…", command=self.guardar_xsd_local).pack(side="left", padx=6)
        tk.Button(bar, text="Cargar esquema guardado…", command=self.cargar_xsd_local).pack(side="left", padx=6)
        tk.Button(bar, text="Insertar Addenda y Guardar XML", command=self.guardar_addenda).pack(side="right", padx=6)

        self.info = tk.Label(root, text="Carga un XML timbrado y un XSD para comenzar.", fg="#444")
        self.info.pack(fill="x", padx=10)



    def cargar_xml(self):
        ruta = filedialog.askopenfilename(title="Selecciona CFDI XML", filetypes=[("XML", "*.xml")])
        if not ruta:
            return
        self.xml_path = ruta
        self.factura_header, self.factura_conceptos = extraer_datos_factura(ruta)
        msg = f"CFDI cargado | Folio: {self.factura_header.get('Folio','')} | Fecha: {self.factura_header.get('Fecha','')} | Total: {self.factura_header.get('Total','')}"
        self.info.config(text=msg)
        messagebox.showinfo("OK", "Factura timbrada cargada correctamente.")

        if self.shapes:
            self._construir_formulario()

    def cargar_xsd_file(self):
        ruta = filedialog.askopenfilename(title="Selecciona XSD de Addenda", filetypes=[("XSD", "*.xsd")])
        if not ruta:
            return
        try:
            self.shapes = cargar_xsd(ruta)
            self._construir_formulario()
            messagebox.showinfo("OK", "XSD cargado y analizado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo analizar el XSD:\n{e}")

    def guardar_xsd_local(self):
        if not self.shapes:
            messagebox.showerror("Error", "Primero carga un XSD.")
            return
        ruta = filedialog.asksaveasfilename(title="Guardar esquema parseado", defaultextension=".xml",
                                            filetypes=[("XML", "*.xml")])
        if not ruta:
            return
        guardar_xsd(self.shapes, ruta)
        messagebox.showinfo("OK", f"Esquema guardado en:\n{ruta}")

    def cargar_xsd_local(self):
        ruta = filedialog.askopenfilename(title="Cargar esquema parseado", filetypes=[("XML", "*.xml")])
        if not ruta:
            return
        try:
            from mapeo import cargar_xsd_guardado
            self.shapes = cargar_xsd_guardado(ruta)
            self._construir_formulario()
            messagebox.showinfo("OK", "Esquema cargado desde archivo guardado.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el esquema guardado:\n{e}")

    def _clear_form(self):
        for w in self.frame.winfo_children():
            w.destroy()
        self.campos.clear()
        self.autofilled.clear()

    def _construir_formulario(self):
        self._clear_form()
        if not self.shapes:
            tk.Label(self.frame, text="Carga un XSD para continuar.").pack(anchor="w", padx=8, pady=6)
            return

        autovals = {}
        if self.factura_header:
            autovals = sugerir_autovalores(self.shapes, self.factura_header, self.factura_conceptos)

        tk.Label(self.frame, text="Campos de Addenda", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=6)

        def draw_shape(sh, level, path):
            name = sh.get("name") or "Elemento"
            cur_path = f"{path}/{name}" if path and name else (name or path)

            hdr = tk.Label(self.frame, text=("    " * level) + f"<{name}>", fg="#0A5")
            hdr.pack(anchor="w", padx=10, pady=2)

            entry = tk.Entry(self.frame, width=60)
            entry.pack(anchor="w", padx=36, pady=2)
            self.campos[cur_path] = entry

            v_elem = autovals.get(cur_path, "")
            if v_elem:
                entry.insert(0, v_elem)
                entry.config(state="disabled")
                self.autofilled.add(cur_path)

            for a in sh.get("attrs", []):
                ruta_attr = f"{cur_path}@{a['name']}"
                lab = tk.Label(self.frame, text=("    " * (level+1)) + f"@{a['name']} ({a.get('use','optional')})", fg="#555")
                lab.pack(anchor="w", padx=10, pady=1)
                e_attr = tk.Entry(self.frame, width=60)
                e_attr.pack(anchor="w", padx=36, pady=2)
                self.campos[ruta_attr] = e_attr

                v_attr = autovals.get(ruta_attr, "")
                if v_attr:
                    e_attr.insert(0, v_attr)
                    e_attr.config(state="disabled")
                    self.autofilled.add(ruta_attr)

            for c in sh.get("children", []):
                draw_shape(c, level+1, cur_path)

        for s in self.shapes:
            draw_shape(s, 0, "")

        tk.Label(self.frame, text="Los campos autorrellenos desde CFDI están bloqueados.", fg="#666").pack(anchor="w", padx=10, pady=8)

    def guardar_addenda(self):
        if not self.xml_path:
            messagebox.showerror("Error", "Primero carga un XML timbrado.")
            return
        if not self.shapes:
            messagebox.showerror("Error", "Carga un XSD antes de guardar la Addenda.")
            return

        valores = {}
        for ruta, entry in self.campos.items():
            try:
                v = entry.get()
            except tk.TclError:
                v = ""
            if v is None:
                v = ""
            valores[ruta] = v

        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()

            construir_addenda(root, self.shapes, valores)

            nuevo = os.path.splitext(self.xml_path)[0] + "_con_addenda.xml"
            tree.write(nuevo, encoding="utf-8", xml_declaration=True)
            messagebox.showinfo("Éxito", f"Addenda insertada y guardada en:\n{nuevo}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo insertar la Addenda:\n{e}")
