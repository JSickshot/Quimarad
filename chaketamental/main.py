import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from lxml import etree
import xmlschema
from collections import OrderedDict

SCHEMAS_DIR = "schemas"
TEMPLATES_DIR = "plantillas"
os.makedirs(SCHEMAS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

CFDI_NS = "http://www.sat.gob.mx/cfd/4"  # ajustar si usas otra versión
CFDI_PREFIX = "cfdi"
NSMAP_CFDI = {CFDI_PREFIX: CFDI_NS}

# helper para QNames
def qn(ns, tag):
    return etree.QName(ns, tag)

# ---------- Parsing XSD para formulario dinámico ----------
class XsdFormBuilder:
    def __init__(self, schema: xmlschema.XMLSchema):
        self.schema = schema
        self.tns = getattr(schema, 'target_namespace', None)

    def get_root_elements(self):
        return list(self.schema.elements.values())

    def build_structure(self, elem):
        def _build(e):
            info = OrderedDict()
            info['name'] = e.name
            info['min_occurs'] = getattr(e, 'min_occurs', 1)
            info['max_occurs'] = getattr(e, 'max_occurs', 1)
            try:
                is_simple = e.type.is_simple()
            except Exception:
                is_simple = False
            info['is_simple'] = is_simple
            info['type'] = getattr(e.type, 'name', None)
            info['children'] = []
            if not is_simple:
                try:
                    for c in e.type.content.iter_elements():
                        info['children'].append(_build(c))
                except Exception:
                    # fallback: intentar obtener particles
                    pass
            return info
        return _build(elem)

# ---------- UI helpers ----------
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.canvas = canvas
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

# ---------- FieldInstance - controla campos simples, complejos y listas ----------
class FieldInstance:
    def __init__(self, parent, descriptor, nsmap=None):
        self.descriptor = descriptor
        self.parent = parent
        self.nsmap = nsmap or {}
        self.frame = ttk.Frame(parent)
        # widgets:
        # - si simple: {'entry': Entry}
        # - si complex: {'children': {name: FieldInstance or [FieldInstance,...]}}
        self.widgets = {}
        self.build()

    def build(self):
        name = self.descriptor['name']
        is_simple = self.descriptor['is_simple']
        if is_simple:
            lbl = ttk.Label(self.frame, text=name, width=25)
            ent = ttk.Entry(self.frame, width=50)
            lbl.pack(side='left', padx=(2,8))
            ent.pack(side='left', pady=2)
            self.widgets['entry'] = ent
        else:
            lbl = ttk.Label(self.frame, text=f"{name}:", font=('Arial', 10, 'bold'))
            lbl.pack(anchor='w', pady=(4,2))
            subf = ttk.Frame(self.frame, relief='flat', padding=4)
            subf.pack(fill='x')
            self.widgets['children'] = OrderedDict()
            for child in self.descriptor['children']:
                cname = child['name']
                if child['max_occurs'] is None or child['max_occurs'] > 1:
                    # lista repetible
                    panel = ttk.Frame(subf)
                    panel.pack(fill='x', pady=2)
                    lblc = ttk.Label(panel, text=cname)
                    lblc.pack(side='left')
                    btn_add = ttk.Button(panel, text='Agregar', command=lambda c=child, p=panel: self._add_list_item(c, p))
                    btn_add.pack(side='left', padx=6)
                    container = ttk.Frame(subf)
                    container.pack(fill='x', padx=12, pady=4)
                    # store as list container
                    self.widgets['children'][cname] = []  # list of FieldInstance
                    # also keep container for packing
                    self.widgets['children'][f"_{cname}_container"] = container
                else:
                    inst = FieldInstance(subf, child, nsmap=self.nsmap)
                    inst.frame.pack(fill='x', pady=2)
                    self.widgets['children'][cname] = inst

    def _add_list_item(self, child_descriptor, panel):
        container = self.widgets['children'].get(f"_{child_descriptor['name']}_container")
        if container is None:
            return
        item_frame = ttk.Frame(container, relief='solid', borderwidth=1, padding=6)
        item_frame.pack(fill='x', pady=4)
        inst = FieldInstance(item_frame, child_descriptor, nsmap=self.nsmap)
        inst.frame.pack(fill='x')
        btn_del = ttk.Button(item_frame, text='Eliminar', command=lambda f=item_frame, i=inst: self._remove_list_item(f, i, child_descriptor['name']))
        btn_del.pack(anchor='e', pady=2)
        # append to list
        self.widgets['children'][child_descriptor['name']].append(inst)

    def _remove_list_item(self, frame, inst, name):
        frame.destroy()
        lst = self.widgets['children'].get(name, [])
        if inst in lst:
            lst.remove(inst)

    def get_value(self):
        if self.descriptor['is_simple']:
            ent = self.widgets.get('entry')
            return ent.get() if ent else ''
        else:
            data = OrderedDict()
            for key, widget in self.widgets['children'].items():
                if isinstance(widget, FieldInstance):
                    data[key] = widget.get_value()
                elif isinstance(widget, list):
                    # list of FieldInstance
                    items = []
                    for inst in widget:
                        items.append(inst.get_value())
                    data[key] = items
                else:
                    # unexpected
                    data[key] = None
            return data

# ---------- Aplicación principal mejorada ----------
class AddendadorApp:
    def __init__(self, master):
        self.master = master
        master.title('Addendador dinámico - Mejorado')
        master.geometry('1200x800')

        self.schema = None
        self.schema_path = None
        self.builder = None
        self.root_descriptor = None
        self.form_root_inst = None
        self.cfdi_tree = None
        self.cfdi_path = None
        self.nsmap_addenda = {}

        # UI
        top = ttk.Frame(master)
        top.pack(fill='x', pady=6)
        ttk.Button(top, text='Cargar XSD', command=self.load_xsd).pack(side='left', padx=4)
        ttk.Button(top, text='Guardar XSD en schemas/', command=self.save_schema_copy).pack(side='left', padx=4)
        ttk.Button(top, text='Cargar CFDI (XML)', command=self.load_cfdi).pack(side='left', padx=4)
        ttk.Button(top, text='Insertar Addenda', command=self.insert_addenda).pack(side='left', padx=4)
        ttk.Button(top, text='Validar Addenda', command=self.validate_addenda).pack(side='left', padx=4)
        ttk.Button(top, text='Guardar XML final', command=self.save_cfdi).pack(side='left', padx=4)
        ttk.Button(top, text='Guardar plantilla', command=self.save_template).pack(side='right', padx=4)
        ttk.Button(top, text='Cargar plantilla', command=self.load_template).pack(side='right', padx=4)

        pan = ttk.PanedWindow(master, orient='horizontal')
        pan.pack(fill='both', expand=True)

        left = ttk.Frame(pan)
        right = ttk.Frame(pan)
        pan.add(left, weight=3)
        pan.add(right, weight=2)

        ttk.Label(left, text='Formulario addenda', font=('Arial', 12, 'bold')).pack(anchor='w')
        self.scrollframe = ScrollableFrame(left)
        self.scrollframe.pack(fill='both', expand=True, padx=6, pady=6)

        # Right side: TreeView for Addenda + XML raw view
        ttk.Label(right, text='Previsualización / Edición Addenda', font=('Arial', 12, 'bold')).pack(anchor='w')
        sub_top = ttk.Frame(right)
        sub_top.pack(fill='both', expand=True)

        # Treeview
        tree_frame = ttk.Frame(sub_top)
        tree_frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tree_frame)
        self.tree.pack(fill='both', expand=True, side='left')
        tree_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Editor for selected node
        edit_panel = ttk.Frame(right)
        edit_panel.pack(fill='x', pady=4)
        ttk.Label(edit_panel, text='Tag:').grid(row=0, column=0, sticky='w')
        self.edit_tag = ttk.Entry(edit_panel, width=30)
        self.edit_tag.grid(row=0, column=1, sticky='w')
        ttk.Label(edit_panel, text='Texto/Valor:').grid(row=1, column=0, sticky='w')
        self.edit_text = ttk.Entry(edit_panel, width=60)
        self.edit_text.grid(row=1, column=1, sticky='w')
        ttk.Button(edit_panel, text='Actualizar nodo', command=self.update_selected_node).grid(row=2, column=1, sticky='e', pady=4)

        # Raw XML view
        ttk.Label(right, text='CFDI XML (raw)', font=('Arial', 10, 'bold')).pack(anchor='w')
        self.txt_xml = tk.Text(right, wrap='none', height=20)
        self.txt_xml.pack(fill='both', expand=True, padx=6, pady=6)

    # ---------- XSD ----------
    def load_xsd(self):
        path = filedialog.askopenfilename(title='Selecciona XSD', filetypes=[('XSD files', '*.xsd')])
        if not path:
            return
        try:
            schema = xmlschema.XMLSchema(path)
            self.schema = schema
            self.schema_path = path
            self.builder = XsdFormBuilder(schema)
            roots = self.builder.get_root_elements()
            if len(roots) > 1:
                names = [r.name for r in roots]
                choice = self._ask_choice('Seleccione elemento raíz de la addenda', names)
                if choice is None:
                    return
                root_elem = roots[choice]
            else:
                root_elem = roots[0]
            self.root_descriptor = self.builder.build_structure(root_elem)
            tns = getattr(self.schema, 'target_namespace', None)
            if tns:
                # asignar prefijo 'a' por defecto
                self.nsmap_addenda = { 'a': tns }
            else:
                self.nsmap_addenda = {}
            self.render_form()
            messagebox.showinfo('XSD cargado', f'Se cargó XSD: {os.path.basename(path)}')
        except Exception as e:
            messagebox.showerror('Error al cargar XSD', str(e))

    def save_schema_copy(self):
        if not self.schema_path:
            messagebox.showwarning('No hay XSD', 'Primero carga un XSD.')
            return
        dest = os.path.join(SCHEMAS_DIR, os.path.basename(self.schema_path))
        try:
            with open(self.schema_path, 'rb') as fr, open(dest, 'wb') as fw:
                fw.write(fr.read())
            messagebox.showinfo('Guardado', f'XSD copiado a {dest}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    # ---------- Form rendering ----------
    def render_form(self):
        for w in self.scrollframe.scrollable_frame.winfo_children():
            w.destroy()
        self.form_root_inst = FieldInstance(self.scrollframe.scrollable_frame, self.root_descriptor, nsmap=self.nsmap_addenda)
        self.form_root_inst.frame.pack(fill='x', pady=8)

    # ---------- CFDI ----------
    def load_cfdi(self):
        path = filedialog.askopenfilename(title='Selecciona CFDI XML', filetypes=[('XML files', '*.xml')])
        if not path:
            return
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(path, parser)
            self.cfdi_tree = tree
            self.cfdi_path = path
            s = etree.tostring(tree, pretty_print=True, encoding='utf-8').decode('utf-8')
            self.txt_xml.delete('1.0', tk.END)
            self.txt_xml.insert('1.0', s)
            messagebox.showinfo('CFDI cargado', os.path.basename(path))
        except Exception as e:
            messagebox.showerror('Error al cargar CFDI', str(e))

    # ---------- Construir addenda XML desde formulario (preservando nombres) ----------
    def build_addenda_element(self):
        if not self.form_root_inst:
            raise ValueError('Formulario no generado')

        def _build_elem(descriptor, inst):
            name = descriptor['name']
            ns_uri = None
            if self.nsmap_addenda:
                ns_uri = list(self.nsmap_addenda.values())[0]
                el = etree.Element(qn(ns_uri, name))
            else:
                el = etree.Element(name)
            if descriptor['is_simple']:
                val = inst.get_value()
                if val:
                    el.text = val
                return el
            else:
                for child_desc in descriptor['children']:
                    child_widget = inst.widgets['children'].get(child_desc['name'])
                    if isinstance(child_widget, FieldInstance):
                        child_el = _build_elem(child_desc, child_widget)
                        el.append(child_el)
                    elif isinstance(child_widget, list):
                        # lista de FieldInstance
                        for item_inst in child_widget:
                            child_el = _build_elem(child_desc, item_inst)
                            el.append(child_el)
                    else:
                        # no es instanciado (posiblemente minOccurs=0)
                        pass
                return el

        root_descriptor = self.root_descriptor
        addenda_el = _build_elem(root_descriptor, self.form_root_inst)
        return addenda_el

    # ---------- Insertar addenda en CFDI ----------
    def insert_addenda(self):
        if self.cfdi_tree is None:
            messagebox.showwarning('Falta CFDI', 'Carga primero el CFDI timbrado (XML).')
            return
        if self.schema is None:
            messagebox.showwarning('Falta XSD', 'Carga primero el XSD de la addenda.')
            return
        try:
            add_el = self.build_addenda_element()
            root = self.cfdi_tree.getroot()
            # buscar o crear cfdi:Addenda
            cfdi_addenda = root.find('{%s}Addenda' % CFDI_NS)
            if cfdi_addenda is None:
                cfdi_addenda = etree.SubElement(root, '{%s}Addenda' % CFDI_NS)
            # limpiar
            for c in list(cfdi_addenda):
                cfdi_addenda.remove(c)
            # declarar namespace(s) de la addenda en el nodo Addenda
            for p, uri in self.nsmap_addenda.items():
                cfdi_addenda.set('xmlns:%s' % p, uri)
            cfdi_addenda.append(add_el)
            # actualizar treeview para edición
            self.populate_tree_from_addenda(add_el)
            # actualizar raw xml
            s = etree.tostring(self.cfdi_tree, pretty_print=True, xml_declaration=True, encoding='utf-8').decode('utf-8')
            self.txt_xml.delete('1.0', tk.END)
            self.txt_xml.insert('1.0', s)
            messagebox.showinfo('Addenda insertada', 'Se insertó la addenda correctamente en el CFDI.')
        except Exception as e:
            messagebox.showerror('Error insertando addenda', str(e))

    # ---------- Validación estricta ----------
    def validate_addenda(self):
        if self.schema is None:
            messagebox.showwarning('Falta XSD', 'Carga primero el XSD.')
            return
        try:
            add_el = self.build_addenda_element()
            # xmlschema acepta ElementTree/Element; usar iter_errors para mensajes detallados
            errors = list(self.schema.iter_errors(add_el))
            if errors:
                msgs = []
                for e in errors:
                    # xmlschema.Error objects suelen tener .path y .reason o str(e)
                    try:
                        loc = getattr(e, 'path', None)
                        reason = str(e)
                        if loc:
                            msgs.append(f"En {loc}: {reason}")
                        else:
                            msgs.append(reason)
                    except Exception:
                        msgs.append(str(e))
                messagebox.showerror('Errores de validación', ' '.join(msgs))
            else:
                messagebox.showinfo('Validación OK', 'La addenda es válida según el XSD.')
        except Exception as e:
            messagebox.showerror('Error validando', str(e))

    # ---------- Plantillas ----------
    def save_template(self):
        if not self.schema_path or not self.form_root_inst:
            messagebox.showwarning('Faltan datos', 'Carga XSD y completa el formulario antes de guardar la plantilla.')
            return
        try:
            data = self.form_root_inst.get_value()
            template = {
                'schema': os.path.basename(self.schema_path),
                'tns': self.nsmap_addenda,
                'data': data
            }
            filename = filedialog.asksaveasfilename(initialdir=TEMPLATES_DIR, defaultextension='.json', filetypes=[('JSON', '*.json')])
            if not filename:
                return
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=2)
            messagebox.showinfo('Plantilla guardada', filename)
        except Exception as e:
            messagebox.showerror('Error guardando plantilla', str(e))

    def load_template(self):
        path = filedialog.askopenfilename(initialdir=TEMPLATES_DIR, title='Selecciona plantilla JSON', filetypes=[('JSON', '*.json')])
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                template = json.load(f)
            schema_name = template.get('schema')
            if schema_name and self.schema_path and os.path.basename(self.schema_path) != schema_name:
                if not messagebox.askyesno('Schema distinto', f"La plantilla fue creada para {schema_name}. ¿Deseas cargarla de todos modos?"):
                    return
            data = template.get('data', {})
            self._populate_form_from_data(self.form_root_inst, data)
            messagebox.showinfo('Plantilla cargada', os.path.basename(path))
        except Exception as e:
            messagebox.showerror('Error cargando plantilla', str(e))

    def _populate_form_from_data(self, form_inst: FieldInstance, data: dict):
        if form_inst.descriptor['is_simple']:
            ent = form_inst.widgets.get('entry')
            nm = form_inst.descriptor['name']
            if ent and nm in data:
                ent.delete(0, tk.END)
                ent.insert(0, data[nm])
            return
        else:
            for key, widget in form_inst.widgets['children'].items():
                if isinstance(widget, FieldInstance):
                    if key in data:
                        self._populate_form_from_data(widget, data[key])
                elif isinstance(widget, list):
                    # limpiar contenedor visual
                    container = form_inst.widgets.get(f"_{key}_container")
                    if container:
                        for child in container.winfo_children():
                            child.destroy()
                    lst_data = data.get(key, [])
                    for item in lst_data:
                        item_frame = ttk.Frame(container, relief='solid', borderwidth=1, padding=6)
                        item_frame.pack(fill='x', pady=4)
                        # localizar descriptor para child
                        child_desc = None
                        for ch in form_inst.descriptor['children']:
                            if ch['name'] == key:
                                child_desc = ch
                                break
                        if child_desc:
                            inst = FieldInstance(item_frame, child_desc, nsmap=self.nsmap_addenda)
                            inst.frame.pack(fill='x')
                            # popular subcampos
                            for subk, subv in item.items():
                                # intentar encontrar entry by subk name recursively
                                self._populate_by_name(inst, subk, subv)
                            btn_del = ttk.Button(item_frame, text='Eliminar', command=lambda f=item_frame: f.destroy())
                            btn_del.pack(anchor='e', pady=2)
                            form_inst.widgets['children'][key].append(inst)

    def _populate_by_name(self, inst: FieldInstance, name, value):
        # busca recursivamente un child simple con el tag 'name' y lo rellena
        if inst.descriptor['is_simple']:
            if inst.descriptor['name'] == name:
                ent = inst.widgets.get('entry')
                if ent:
                    ent.delete(0, tk.END)
                    ent.insert(0, value)
                return True
            return False
        else:
            for k, w in inst.widgets['children'].items():
                if isinstance(w, FieldInstance):
                    if self._populate_by_name(w, name, value):
                        return True
                elif isinstance(w, list):
                    for subinst in w:
                        if self._populate_by_name(subinst, name, value):
                            return True
            return False

    # ---------- TreeView: mostrar y editar el nodo Addenda ----------
    def populate_tree_from_addenda(self, add_el):
        # limpiar tree
        for i in self.tree.get_children():
            self.tree.delete(i)
        def _walk(elem, parent=''):
            # display tag without namespace prefix
            tag = etree.QName(elem).localname
            text = (elem.text or '').strip()
            node_id = self.tree.insert(parent, 'end', text=f"{tag}: {text}", values=(elem.tag, text))
            for ch in elem:
                _walk(ch, node_id)
        _walk(add_el)
        # store current addenda element for editing
        self.current_addenda_element = add_el

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        node = sel[0]
        values = self.tree.item(node, 'values')
        if not values:
            return
        tag_qname, text = values
        # show tag localname and text in editors
        local = etree.QName(tag_qname).localname if isinstance(tag_qname, str) else etree.QName(tag_qname).localname
        self.edit_tag.delete(0, tk.END)
        self.edit_tag.insert(0, local)
        self.edit_text.delete(0, tk.END)
        self.edit_text.insert(0, text)
        # attach selected node id
        self.selected_tree_node = node

    def update_selected_node(self):
        if not hasattr(self, 'selected_tree_node'):
            messagebox.showwarning('Nada seleccionado', 'Selecciona un nodo en el árbol.')
            return
        node = self.selected_tree_node
        values = self.tree.item(node, 'values')
        if not values:
            return
        tag_qname = values[0]
        # localizar el elemento correspondiente en el XML: navegaremos desde current_addenda_element
        # método: utilizar el texto mostrado como camino - simplificación: buscaremos primer elemento con mismo localname y texto
        localname = self.edit_tag.get().strip()
        newtext = self.edit_text.get().strip()
        # buscar en XML
        found = None
        for el in self.current_addenda_element.iter():
            if etree.QName(el).localname == localname:
                # update first found
                found = el
                break
        if found is None:
            messagebox.showerror('No encontrado', 'No se encontró el elemento en el XML para actualizar (búsqueda por nombre).')
            return
        found.text = newtext
        # actualizar raw xml y tree node display
        self.refresh_raw_xml_and_tree()

    def refresh_raw_xml_and_tree(self):
        # actualizar raw xml
        s = etree.tostring(self.cfdi_tree, pretty_print=True, xml_declaration=True, encoding='utf-8').decode('utf-8')
        self.txt_xml.delete('1.0', tk.END)
        self.txt_xml.insert('1.0', s)
        # repoblar tree desde current_addenda
        self.populate_tree_from_addenda(self.current_addenda_element)

    # ---------- Guardar CFDI ----------
    def save_cfdi(self):
        if self.cfdi_tree is None:
            messagebox.showwarning('No hay CFDI', 'Carga y/o inserta la addenda primero')
            return
        path = filedialog.asksaveasfilename(defaultextension='.xml', filetypes=[('XML', '*.xml')])
        if not path:
            return
        try:
            self.cfdi_tree.write(path, pretty_print=True, xml_declaration=True, encoding='utf-8')
            messagebox.showinfo('Guardado', f'CFDI guardado en {path}')
        except Exception as e:
            messagebox.showerror('Error guardando CFDI', str(e))

    # ---------- Util ----------
    def _ask_choice(self, title, options):
        dlg = tk.Toplevel(self.master)
        dlg.title(title)
        var = tk.IntVar(value=-1)
        for i, opt in enumerate(options):
            rb = ttk.Radiobutton(dlg, text=opt, variable=var, value=i)
            rb.pack(anchor='w')
        ok = ttk.Button(dlg, text='OK', command=dlg.destroy)
        ok.pack()
        dlg.grab_set()
        dlg.wait_window()
        val = var.get()
        if val == -1:
            return None
        return val

# ---------- Ejecutar ----------
if __name__ == '__main__':
    root = tk.Tk()
    from tkinter import font
    font.nametofont('TkDefaultFont').configure(size=10)
    app = AddendadorApp(root)
    root.mainloop()
