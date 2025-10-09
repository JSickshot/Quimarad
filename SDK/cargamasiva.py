import os
import csv
import ctypes
from ctypes import c_int, c_double, c_char_p, c_long, create_string_buffer, byref
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk

"""
QCG Facturador SDK (Python) – Plantilla GUI para carga masiva de facturas (CONTPAQi Comercial Premium)
----------------------------------------------------------------------------------------------

Flujo:
1) Login (opcional, si tu instalación usa seguridad en Comercial) y selección de Empresa.
2) Pega desde Excel (TAB-delimited) o carga CSV/Excel.
3) Mapeo mínimo de columnas -> Documento y Movimientos.
4) Validar y Crear facturas con el SDK (fSetDatoDocumento / fAltaDocumento / fSetDatoMovimiento / fAltaMovimiento / fGuardaDocumento).

Notas:
- La autenticación con usuario/contraseña se intenta mediante fInicioSesionSDK si existe en tu DLL; si no, se omite.
- La lista de empresas puede llenarse buscando carpetas dentro de RUTA_EMPRESAS_BASE o manual (Seleccionar carpeta).
- Ajusta RUTA_BINARIOS y RUTA_EMPRESAS_BASE a tu ambiente.
- Estilo visual: fondo blanco, texto negro, logo QCG arriba-derecha.
"""

# ==== CONFIGURACIÓN ADAPTABLE ====
RUTA_BINARIOS = r"C:\Compac\Comercial"                # Carpeta donde está MGWSERVICIOS.DLL
RUTA_EMPRESAS_BASE = r"C:\Compac\Empresas"            # Carpeta que contiene las empresas (subcarpetas)
QCG_LOGO_PATH = r"C:\Users\julio\Documents\Quimarad\Logo.jpg"  # Logo QCG (opcional)
NOMBRE_PAQ = b"CONTPAQ I Comercial"                      # fSetNombrePAQ

# Concepto/Serie por defecto (ajustables en UI)
DEFAULT_CONCEPTO = "4"     # Concepto de factura
DEFAULT_SERIE = "B1"

# Campos mínimos documento que pediremos (puedes ampliar)
DOC_CAMPOS_MIN = {
    'cCodConcepto': DEFAULT_CONCEPTO,
    'cSerie': DEFAULT_SERIE,
    # 'cFolio': None,      # Si folio es automático, dejar None
    'cCodCteProv': None,   # Código cliente
    'cFecha': None,        # YYYYMMDD
    'cReferencia': None,   # Referencia libre
}

# Campos mínimos movimiento
MOV_CAMPOS_MIN = [
    'cCodigoProducto',   # Código de producto
    'cUnidades',         # Cantidad
    'cPrecio',           # Precio unitario
    'cCodigoAlmacen',    # Almacén
    # 'cDescripcionExtra'  # Opcional
]

# ==== SDK WRAPPER DINÁMICO ====
class ComercialSDK:
    def __init__(self, ruta_binarios: str, nombre_paq: bytes):
        self.skd = None
        self._error_buf = create_string_buffer(512)
        self._fns = {}
        self.ruta_binarios = ruta_binarios
        self.nombre_paq = nombre_paq

    def load(self):
        os.chdir(self.ruta_binarios)
        self.skd = ctypes.WinDLL("MGWSERVICIOS.DLL")
        self._bind()
        self._check(self._call('fSetNombrePAQ', self.nombre_paq), 'Inicializando SDK (fSetNombrePAQ)')

    def _bind(self):
        def bind(name, restype=c_int, argtypes=None, optional=False):
            try:
                fn = getattr(self.skd, name)
                if argtypes is not None:
                    fn.argtypes = argtypes
                fn.restype = restype
                self._fns[name] = fn
            except AttributeError:
                if not optional:
                    raise
                self._fns[name] = None

        # Básicos
        bind('fSetNombrePAQ', c_int, [c_char_p])
        bind('fAbreEmpresa', c_int, [c_char_p])
        bind('fCierraEmpresa', None, [])
        bind('fTerminaSDK', None, [])
        bind('fError', None, [c_int, c_char_p, c_int])
        bind('fInicioSesionSDK', c_int, [c_char_p, c_char_p], optional=True)  # Puede no existir
        
        # Documento
        bind('fAltaDocumento', c_int, [ctypes.POINTER(c_long), ctypes.c_void_p])
        bind('fSetDatoDocumento', c_int, [c_char_p, c_char_p])
        bind('fGuardaDocumento', c_int, [])
        bind('fCancelaDocumento', c_int, [], optional=True)

        # Movimiento
        bind('fAltaMovimiento', c_int, [c_long, ctypes.POINTER(c_long), ctypes.c_void_p])
        bind('fSetDatoMovimiento', c_int, [c_char_p, c_char_p])

    def _call(self, name, *args):
        fn = self._fns.get(name)
        if fn is None:
            raise RuntimeError(f"Función {name} no disponible en DLL")
        return fn(*args)

    def _error_text(self, code: int) -> str:
        self._error_buf = create_string_buffer(512)
        self._call('fError', code, self._error_buf, 512)
        return self._error_buf.value.decode('latin-1', 'ignore')

    def _check(self, code: int, ctx: str):
        if code != 0:
            raise RuntimeError(f"{ctx} | SDK({code}): {self._error_text(code)}")

    def login(self, usuario: str, contrasena: str):
        # Intentar login si la función existe
        fn = self._fns.get('fInicioSesionSDK')
        if fn is not None:
            self._check(fn(usuario.encode('latin-1'), contrasena.encode('latin-1')), 'Iniciando sesión (fInicioSesionSDK)')
        # Si no existe, se asume modo sin seguridad

    def abre_empresa(self, ruta_empresa: str):
        self._check(self._call('fAbreEmpresa', ruta_empresa.encode('latin-1')), f'Abrir empresa: {ruta_empresa}')

    def cierra_empresa(self):
        try:
            self._call('fCierraEmpresa')
        except Exception:
            pass

    def terminar(self):
        try:
            self._call('fTerminaSDK')
        except Exception:
            pass

    # Documento helper
    def set_doc(self, nombre: str, valor: str):
        self._check(self._call('fSetDatoDocumento', nombre.encode('latin-1'), ('' if valor is None else str(valor)).encode('latin-1')),
                    f"Set documento {nombre}")

    def alta_documento(self) -> int:
        doc_id = c_long(0)
        self._check(self._call('fAltaDocumento', byref(doc_id), None), 'Alta de documento')
        return doc_id.value

    def guarda_documento(self):
        self._check(self._call('fGuardaDocumento'), 'Guardar documento')

    # Movimiento helper
    def set_mov(self, nombre: str, valor: str):
        self._check(self._call('fSetDatoMovimiento', nombre.encode('latin-1'), ('' if valor is None else str(valor)).encode('latin-1')),
                    f"Set movimiento {nombre}")

    def alta_movimiento(self, id_documento: int) -> int:
        mov_id = c_long(0)
        self._check(self._call('fAltaMovimiento', id_documento, byref(mov_id), None), 'Alta de movimiento')
        return mov_id.value

# ==== GUI ====
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("QCG – Carga masiva de facturas (SDK Comercial)")
        self.configure(bg='white')
        self.geometry('1000x680')
        self.minsize(900, 600)

        # SDK
        self.sdk = ComercialSDK(RUTA_BINARIOS, NOMBRE_PAQ)
        try:
            self.sdk.load()
        except Exception as e:
            messagebox.showerror("SDK", f"No se pudo cargar el SDK.\n\n{e}")

        # Top bar con logo
        top = tk.Frame(self, bg='white')
        top.pack(side=tk.TOP, fill=tk.X)
        self._add_logo(top)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        style = ttk.Style()
        style.theme_use('default')
        style.configure('TLabel', background='white', foreground='black')
        style.configure('TButton', background='white', foreground='black')
        style.configure('TEntry', fieldbackground='white', foreground='black')
        style.configure('TNotebook', background='white')
        style.configure('TNotebook.Tab', background='#f3f3f3', padding=8)

        self._build_login_tab()
        self._build_pegar_tab()
        self._build_mapeo_tab()
        self._build_resumen_tab()

        self.doc_defaults = DOC_CAMPOS_MIN.copy()
        self.mov_campos = MOV_CAMPOS_MIN[:]

        # Estado
        self.ruta_empresa_sel = tk.StringVar()
        self.usuario_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.concepto_var = tk.StringVar(value=DEFAULT_CONCEPTO)
        self.serie_var = tk.StringVar(value=DEFAULT_SERIE)
        self.fecha_var = tk.StringVar()  # YYYYMMDD
        self.cliente_var = tk.StringVar()
        self.referencia_var = tk.StringVar()

        self.paste_data = []  # lista de dicts por fila

    def _add_logo(self, parent):
        try:
            if os.path.exists(QCG_LOGO_PATH):
                img = Image.open(QCG_LOGO_PATH)
                img.thumbnail((120, 120))
                self.logo_img = ImageTk.PhotoImage(img)
                lbl = tk.Label(parent, image=self.logo_img, bg='white')
                lbl.pack(side=tk.RIGHT, padx=10, pady=10)
        except Exception:
            pass

    # --- Tabs ---
    def _build_login_tab(self):
        tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(tab, text='1) Sesión y Empresa')

        frm = tk.Frame(tab, bg='white')
        frm.pack(padx=20, pady=20, fill=tk.X)

        ttk.Label(frm, text='Usuario (Comercial):').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.usuario_var, width=30).grid(row=0, column=1, sticky='w')
        ttk.Label(frm, text='Contraseña:').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.pass_var, width=30, show='*').grid(row=1, column=1, sticky='w')

        ttk.Label(frm, text='Empresa:').grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.cbo_emp = ttk.Combobox(frm, width=60, textvariable=self.ruta_empresa_sel)
        self.cbo_emp.grid(row=2, column=1, sticky='w')

        btn_scan = ttk.Button(frm, text='Buscar empresas', command=self._scan_empresas)
        btn_scan.grid(row=2, column=2, padx=5)
        btn_browse = ttk.Button(frm, text='Elegir carpeta...', command=self._browse_empresa)
        btn_browse.grid(row=2, column=3, padx=5)

        ttk.Label(frm, text='Concepto:').grid(row=3, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.concepto_var, width=10).grid(row=3, column=1, sticky='w')
        ttk.Label(frm, text='Serie:').grid(row=3, column=2, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.serie_var, width=10).grid(row=3, column=3, sticky='w')

        ttk.Label(frm, text='Fecha (YYYYMMDD):').grid(row=4, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.fecha_var, width=16).grid(row=4, column=1, sticky='w')
        ttk.Label(frm, text='Cliente (cCodCteProv):').grid(row=5, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.cliente_var, width=16).grid(row=5, column=1, sticky='w')
        ttk.Label(frm, text='Referencia:').grid(row=6, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.referencia_var, width=30).grid(row=6, column=1, sticky='w')

        btn_login = ttk.Button(frm, text='Conectar y abrir empresa', command=self._do_login_open)
        btn_login.grid(row=7, column=0, columnspan=2, pady=12, sticky='w')

    def _build_pegar_tab(self):
        tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(tab, text='2) Pegar desde Excel / CSV')

        top = tk.Frame(tab, bg='white')
        top.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(top, text='Cargar CSV...', command=self._load_csv).pack(side=tk.LEFT)
        ttk.Button(top, text='Limpiar', command=self._clear_paste).pack(side=tk.LEFT, padx=8)
        ttk.Label(top, text='Pega aquí los renglones (Excel -> Ctrl+C, luego Ctrl+V):').pack(side=tk.LEFT, padx=12)

        self.txt = ScrolledText(tab, height=20, bg='white', fg='black')
        self.txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        bottom = tk.Frame(tab, bg='white')
        bottom.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom, text='Previsualizar', command=self._preview_paste).pack(side=tk.LEFT)

        self.preview = ttk.Treeview(tab, columns=("codigo","cantidad","precio","almacen","descripcion"), show='headings', height=6)
        for col, w in [("codigo",160),("cantidad",100),("precio",100),("almacen",90),("descripcion",300)]:
            self.preview.heading(col, text=col)
            self.preview.column(col, width=w)
        self.preview.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

    def _build_mapeo_tab(self):
        tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(tab, text='3) Mapeo de columnas')

        info = tk.Label(tab, text='Indica qué columnas alimentan cada campo requerido', bg='white', fg='black')
        info.pack(anchor='w', padx=12, pady=8)

        frm = tk.Frame(tab, bg='white')
        frm.pack(padx=20, pady=10, fill=tk.X)

        # Combos de mapeo – asumimos nombres de encabezado comunes
        self.cmb_map = {}
        labels = {
            'cCodigoProducto': 'Código producto',
            'cUnidades': 'Cantidad',
            'cPrecio': 'Precio',
            'cCodigoAlmacen': 'Almacén',
            'cDescripcionExtra': 'Descripción (opcional)'
        }

        self.all_headers = ['codigo_producto','cantidad','precio','almacen','descripcion']
        for i,(sdk_field, label) in enumerate(labels.items()):
            tk.Label(frm, text=label, bg='white').grid(row=i, column=0, sticky='e', padx=6, pady=6)
            cmb = ttk.Combobox(frm, values=self.all_headers, width=30)
            # preselección básica
            guess = sdk_field.lower().replace('c','').replace('descripcionextra','descripcion')
            for h in self.all_headers:
                if guess in h.replace('_',''):
                    cmb.set(h)
                    break
            self.cmb_map[sdk_field] = cmb
            cmb.grid(row=i, column=1, sticky='w', padx=6)

        btn = ttk.Button(tab, text='Validar mapeo', command=self._validate_mapping)
        btn.pack(pady=12, anchor='w', padx=12)

    def _build_resumen_tab(self):
        tab = tk.Frame(self.notebook, bg='white')
        self.notebook.add(tab, text='4) Crear facturas')

        info = tk.Label(tab, text='Cuando todo esté listo, presiona "Crear facturas"', bg='white')
        info.pack(anchor='w', padx=12, pady=8)

        btn_sim = ttk.Button(tab, text='Simular (sin guardar)', command=lambda: self._crear_facturas(simular=True))
        btn_sim.pack(anchor='w', padx=12, pady=4)
        btn_go = ttk.Button(tab, text='Crear facturas (SDK)', command=lambda: self._crear_facturas(simular=False))
        btn_go.pack(anchor='w', padx=12, pady=4)

        self.log = ScrolledText(tab, height=16, bg='white', fg='black')
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # --- acciones ---
    def _scan_empresas(self):
        empresas = []
        try:
            for nombre in os.listdir(RUTA_EMPRESAS_BASE):
                ruta = os.path.join(RUTA_EMPRESAS_BASE, nombre)
                if os.path.isdir(ruta):
                    empresas.append(ruta)
        except Exception:
            pass
        if not empresas:
            messagebox.showinfo('Empresas', 'No se encontraron empresas en la ruta configurada.')
        self.cbo_emp['values'] = empresas
        if empresas:
            self.cbo_emp.set(empresas[0])

    def _browse_empresa(self):
        ruta = filedialog.askdirectory(title='Selecciona carpeta de la empresa (tiene el .mdb/.fdb interno)')
        if ruta:
            self.ruta_empresa_sel.set(ruta)

    def _do_login_open(self):
        try:
            usuario = self.usuario_var.get().strip()
            contrasena = self.pass_var.get().strip()
            if usuario and contrasena:
                try:
                    self.sdk.login(usuario, contrasena)
                    messagebox.showinfo('Sesión', 'Inicio de sesión correcto (o no requerido).')
                except Exception as e:
                    messagebox.showwarning('Sesión', f'No fue posible autenticar (se intentó fInicioSesionSDK).\nContinuaremos si tu instalación no requiere seguridad.\n\n{e}')
            ruta_emp = self.ruta_empresa_sel.get().strip()
            if not ruta_emp:
                messagebox.showerror('Empresa', 'Selecciona una empresa.')</n            else:
                self.sdk.abre_empresa(ruta_emp)
                messagebox.showinfo('Empresa', f'Empresa abierta:\n{ruta_emp}')
        except Exception as e:
            messagebox.showerror('SDK', str(e))

    def _load_csv(self):
        ruta = filedialog.askopenfilename(title='CSV con partidas', filetypes=[('CSV','*.csv')])
        if not ruta:
            return
        try:
            with open(ruta, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self._set_paste_from_rows(rows)
            messagebox.showinfo('CSV', f'Se cargaron {len(rows)} renglones.')
        except Exception as e:
            messagebox.showerror('CSV', str(e))

    def _set_paste_from_rows(self, rows):
        # rows: list[dict]
        self.txt.delete('1.0', tk.END)
        if not rows:
            return
        headers = list(rows[0].keys())
        self.txt.insert(tk.END, '\t'.join(headers) + '\n')
        for r in rows:
            self.txt.insert(tk.END, '\t'.join([str(r.get(h,'') or '') for h in headers]) + '\n')

    def _clear_paste(self):
        self.txt.delete('1.0', tk.END)
        for i in self.preview.get_children():
            self.preview.delete(i)
        self.paste_data = []

    def _preview_paste(self):
        for i in self.preview.get_children():
            self.preview.delete(i)
        raw = self.txt.get('1.0', tk.END).strip('\n')
        if not raw:
            return
        lines = [l for l in raw.splitlines() if l.strip()]
        if not lines:
            return
        headers = [h.strip() for h in lines[0].split('\t')]
        self.all_headers = headers
        rows = []
        for line in lines[1:]:
            parts = line.split('\t')
            rec = {headers[i]: (parts[i].strip() if i < len(parts) else '') for i in range(len(headers))}
            rows.append(rec)
        # Guardar
        self.paste_data = rows
        # Pintar preview
        for r in rows[:200]:
            self.preview.insert('', tk.END, values=(
                r.get('codigo_producto') or r.get('codigo') or '',
                r.get('cantidad') or '',
                r.get('precio') or r.get('precio_unitario') or '',
                r.get('almacen') or '1',
                r.get('descripcion') or ''
            ))
        # Actualizar combos de mapeo
        for cmb in self.cmb_map.values():
            cmb['values'] = headers

    def _validate_mapping(self):
        faltantes = []
        for f in ['cCodigoProducto','cUnidades','cPrecio','cCodigoAlmacen']:
            if not self.cmb_map[f].get().strip():
                faltantes.append(f)
        if faltantes:
            messagebox.showerror('Mapeo', f'Faltan columnas para: {", ".join(faltantes)}')
            return
        messagebox.showinfo('Mapeo', 'Mapeo OK.')

    def _crear_facturas(self, simular=False):
        if not self.paste_data:
            messagebox.showerror('Datos', 'No hay datos pegados/cargados.')
            return
        # Validación básica de encabezado de documento
        if not (self.concepto_var.get().strip() and self.serie_var.get().strip() and self.fecha_var.get().strip() and self.cliente_var.get().strip()):
            messagebox.showerror('Documento', 'Completa Concepto, Serie, Fecha y Cliente.')
            return

        # Preparar mapeo
        map_mov = {k: self.cmb_map[k].get().strip() for k in self.cmb_map if self.cmb_map[k].get().strip()}

        self.log.delete('1.0', tk.END)
        self.log.insert(tk.END, f"Iniciando {'SIMULACIÓN' if simular else 'CREACIÓN'}...\n\n")

        try:
            # Setear datos de encabezado comunes (por documento)
            self.sdk.set_doc('cCodConcepto', self.concepto_var.get().strip())
            self.sdk.set_doc('cSerie', self.serie_var.get().strip())
            if self.referencia_var.get().strip():
                self.sdk.set_doc('cReferencia', self.referencia_var.get().strip())
            self.sdk.set_doc('cFecha', self.fecha_var.get().strip())
            self.sdk.set_doc('cCodCteProv', self.cliente_var.get().strip())

            # Alta documento
            id_doc = -1
            if not simular:
                id_doc = self.sdk.alta_documento()
            self.log.insert(tk.END, f"Documento creado (id={id_doc})\n")

            # Partidas
            reng = 1
            for rec in self.paste_data:
                try:
                    codigo = rec.get(map_mov.get('cCodigoProducto',''), '').strip()
                    unidades = rec.get(map_mov.get('cUnidades',''), '').strip()
                    precio = rec.get(map_mov.get('cPrecio',''), '').strip()
                    almacen = rec.get(map_mov.get('cCodigoAlmacen',''), '1').strip() or '1'
                    descr = rec.get(map_mov.get('cDescripcionExtra',''), '').strip()

                    if not (codigo and unidades and precio):
                        raise ValueError('Faltan cCodigoProducto/cUnidades/cPrecio')

                    if not simular:
                        self.sdk.set_mov('cCodigoProducto', codigo)
                        self.sdk.set_mov('cUnidades', unidades)
                        self.sdk.set_mov('cPrecio', precio)
                        self.sdk.set_mov('cCodigoAlmacen', almacen)
                        if descr:
                            self.sdk.set_mov('cDescripcionExtra', descr)
                        id_mov = self.sdk.alta_movimiento(id_doc)
                        self.log.insert(tk.END, f"  + R{reng}: {codigo} x {unidades} @ {precio} (alm {almacen}) -> mov_id={id_mov}\n")
                    else:
                        self.log.insert(tk.END, f"  ~ R{reng} (SIM): {codigo} x {unidades} @ {precio} (alm {almacen})\n")
                except Exception as re:
                    self.log.insert(tk.END, f"  ! R{reng} ERROR: {re}\n")
                reng += 1

            if not simular:
                self.sdk.guarda_documento()
                self.log.insert(tk.END, "\nDocumento guardado.\n")
            else:
                self.log.insert(tk.END, "\nSIMULACIÓN terminada (no se guardó).\n")

        except Exception as e:
            messagebox.showerror('SDK', str(e))
        finally:
            self.log.see(tk.END)


def main():
    app = App()
    app.mainloop()

if __name__ == '__main__':
    main()
