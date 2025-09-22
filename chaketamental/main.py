import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from lxml import etree
import xml.etree.ElementTree as ET
import os


class AddendaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador Global de Addendas")

        self.fields = {}
        self.xml_tree = None
        self.addenda_name = "CustomAddenda"  # nombre por defecto

        # Botones
        tk.Button(root, text="Cargar XSD", command=self.load_xsd).pack(pady=3)
        tk.Button(root, text="Cargar XML Timbrado", command=self.load_xml).pack(pady=3)
        tk.Button(root, text="Guardar XML con Addenda", command=self.save_xml).pack(pady=3)

        # Frame para formulario dinámico
        self.form_frame = tk.Frame(root)
        self.form_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Previsualización
        tk.Label(root, text="Previsualización XML:").pack()
        self.preview = scrolledtext.ScrolledText(root, height=15, state="normal")
        self.preview.pack(padx=10, pady=10, fill="both", expand=True)

    def load_xsd(self):
        path = filedialog.askopenfilename(filetypes=[("XSD files", "*.xsd")])
        if not path:
            return

        schema_doc = etree.parse(path)
        schema_root = schema_doc.getroot()

        # limpiar formulario anterior
        for w in self.form_frame.winfo_children():
            w.destroy()
        self.fields.clear()

        # Detectar nombre principal de la addenda (primer element name)
        first_elem = schema_root.find(".//{http://www.w3.org/2001/XMLSchema}element")
        if first_elem is not None and first_elem.get("name"):
            self.addenda_name = first_elem.get("name")

        # Crear formulario recursivo
        for element in schema_root.findall(".//{http://www.w3.org/2001/XMLSchema}element"):
            name = element.get("name")
            if name:
                frame = tk.LabelFrame(self.form_frame, text=name, padx=5, pady=5)
                frame.pack(fill="x", pady=2)
                self.parse_element(element, frame, prefix=name)

        messagebox.showinfo("Éxito", f"XSD cargado: {os.path.basename(path)}\nNodo raíz: {self.addenda_name}")

    def parse_element(self, element, parent_frame, prefix=""):
        """Analiza un elemento XSD recursivamente"""
        
        for attr in element.findall(".//{http://www.w3.org/2001/XMLSchema}attribute"):
            attr_name = attr.get("name")
            lbl = tk.Label(parent_frame, text=f"{prefix}.{attr_name}")
            lbl.pack(anchor="w")
            entry = tk.Entry(parent_frame)
            entry.pack(fill="x")
            entry.bind("<KeyRelease>", lambda e: self.update_preview())
            self.fields[f"{prefix}.{attr_name}"] = entry

        seq = element.find(".//{http://www.w3.org/2001/XMLSchema}sequence")
        if seq is not None:
            for child in seq.findall("{http://www.w3.org/2001/XMLSchema}element"):
                child_name = child.get("name")
                if child_name:
                    frame = tk.LabelFrame(parent_frame, text=child_name, padx=5, pady=5)
                    frame.pack(fill="x", pady=1)
                    self.parse_element(child, frame, prefix=f"{prefix}.{child_name}")

        if not list(element):
            lbl = tk.Label(parent_frame, text=prefix)
            lbl.pack(anchor="w")
            entry = tk.Entry(parent_frame)
            entry.pack(fill="x")
            entry.bind("<KeyRelease>", lambda e: self.update_preview())
            self.fields[prefix] = entry

    def load_xml(self):
        path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml")])
        if not path:
            return
        self.xml_tree = ET.parse(path)
        messagebox.showinfo("Éxito", f"XML cargado: {os.path.basename(path)}")

    def update_preview(self):
        if self.xml_tree is None:
            return

        root = self.xml_tree.getroot()

        addenda = root.find("Addenda")
        if addenda is None:
            addenda = ET.SubElement(root, "Addenda")

        for child in list(addenda):
            addenda.remove(child)

        custom = ET.SubElement(addenda, self.addenda_name)

        for name, entry in self.fields.items():
            val = entry.get()
            if val:

                parts = name.split(".")
                node = custom
                for p in parts:
                    child = node.find(p)
                    if child is None:
                        child = ET.SubElement(node, p)
                    node = child
                node.text = val

        xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode()
        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, xml_str)

    def save_xml(self):
        if self.xml_tree is None:
            messagebox.showerror("Error", "Primero carga un XML timbrado.")
            return

        self.update_preview()

        path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML", "*.xml")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.preview.get("1.0", tk.END))

        messagebox.showinfo("Guardado", f"XML con Addenda guardado en:\n{path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AddendaApp(root)
    root.mainloop()
