import calendar
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

conn = sqlite3.connect('QCG.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS vacaciones (
                    empleado TEXT,
                    fecha TEXT)''')
conn.commit()

COLORES_EMPLEADOS = {
    "Mustri": "#FFFF99",
    "Limon": "#98FB98",
    "CCI": "#FFA07A",
    "Toño": "#ADD8E6",
    "Sick": "#8B0000",
    "Garo": "#E00000",
    "Oso":  "#C7C7C6",
    "Jesus":"#FC4B08"
}

class Empleado:
    def __init__(self, nombre):
        self.nombre = nombre
        self.vacaciones = self.cargar_vacaciones()
    
    def asignar_vacacion(self, fecha):
        self.vacaciones.append(fecha)
        cursor.execute("INSERT INTO vacaciones (empleado, fecha) VALUES (?, ?)", (self.nombre, fecha.strftime('%Y-%m-%d')))
        conn.commit()
    
    def cargar_vacaciones(self):
        cursor.execute("SELECT fecha FROM vacaciones WHERE empleado=?", (self.nombre,))
        fechas = cursor.fetchall()
        return [datetime.strptime(fecha[0], '%Y-%m-%d') for fecha in fechas]

class CalendarioVacaciones:
    def __init__(self):
        self.empleados = []
        self.ventana_principal = None
        self.canvas = None
        self.scrollable_frame = None
    
    def agregar_empleado(self, nombre):
        if len(self.empleados) <= 8:
            self.empleados.append(Empleado(nombre))
        else:
            messagebox.showwarning("8 nomas ")
    
    def asignar_vacacion_empleado(self, nombre, fecha):
        for empleado in self.empleados:
            if empleado.nombre == nombre:
                empleado.asignar_vacacion(fecha)
                break
        else:
            messagebox.showerror("Error", f"Empleado {nombre} no encontrado.")
    
    def obtener_vacaciones_por_dia(self, year, month, day):
        nombres = []
        for empleado in self.empleados:
            for fecha in empleado.vacaciones:
                if fecha.year == year and fecha.month == month and fecha.day == day:
                    nombres.append(empleado.nombre)
        return nombres
    
    def exportar_vacaciones(self):
        archivo = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if archivo:
            with open(archivo, 'w') as f:
                f.write("Empleado,Fecha\n")
                cursor.execute("SELECT empleado, fecha FROM vacaciones")
                for empleado, fecha in cursor.fetchall():
                    f.write(f"{empleado},{fecha}\n")
            messagebox.showinfo("Exportado", "Vacaciones exportadas correctamente.")
    
    def exportar_vacaciones_empleado(self):
        nombre = simpledialog.askstring("Exportar Vacaciones", "Nombre del empleado:")
        if nombre:
            archivo = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if archivo:
                with open(archivo, 'w') as f:
                    f.write("Empleado,Fecha\n")
                    cursor.execute("SELECT fecha FROM vacaciones WHERE empleado=?", (nombre,))
                    for fecha, in cursor.fetchall():
                        f.write(f"{nombre},{fecha}\n")
                messagebox.showinfo("Exportado", f"Vacaciones de {nombre} exportadas correctamente.")
    
    def mostrar_calendario(self):
        if self.ventana_principal is None:
            self.ventana_principal = tk.Tk()
            self.ventana_principal.title("Calendario de Vacaciones 2024-2025")
            self.ventana_principal.geometry("1200x800")

            menu = tk.Menu(self.ventana_principal)
            self.ventana_principal.config(menu=menu)
            archivo_menu = tk.Menu(menu, tearoff=0)
            menu.add_cascade(label="Archivo", menu=archivo_menu)
            archivo_menu.add_command(label="Exportar Vacaciones", command=self.exportar_vacaciones)
            archivo_menu.add_command(label="Exportar Vacaciones de un Empleado", command=self.exportar_vacaciones_empleado)

            self.canvas = tk.Canvas(self.ventana_principal)
            scrollbar_y = tk.Scrollbar(self.ventana_principal, orient="vertical", command=self.canvas.yview)
            scrollbar_x = tk.Scrollbar(self.ventana_principal, orient="horizontal", command=self.canvas.xview)
            self.scrollable_frame = ttk.Frame(self.canvas)

            self.scrollable_frame.bind(
                "<Configure>",
                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            )

            self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
            self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

            self.canvas.pack(side="left", fill="both", expand=True)
            scrollbar_y.pack(side="right", fill="y")
            scrollbar_x.pack(side="bottom", fill="x")

        self.actualizar_calendario()
        self.ventana_principal.mainloop()
    
    def actualizar_calendario(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for year in [2024, 2025]:
            pestaña_año = ttk.LabelFrame(self.scrollable_frame, text=f"Calendario {year}")
            pestaña_año.pack(padx=5, pady=5, fill="both", expand=True)
            self.crear_calendario_anual(pestaña_año, year)
    
    def crear_calendario_anual(self, contenedor, year):
        for mes in range(1, 13):
            marco_mes = ttk.Labelframe(contenedor, text=calendar.month_name[mes])
            marco_mes.grid(row=(mes-1)//6, column=(mes-1)%6, padx=5, pady=5, sticky='nsew')

            contenedor.grid_rowconfigure((mes-1)//6, weight=1)
            contenedor.grid_columnconfigure((mes-1)%6, weight=1)
            
            self.crear_mes(marco_mes, year, mes)

    def crear_mes(self, marco, year, mes):
        dias_semana = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
        for i, dia in enumerate(dias_semana):
            tk.Label(marco, text=dia, bg="#d3d3d3", width=3, height=1, relief="ridge").grid(row=0, column=i, sticky='nsew')
        cal = calendar.monthcalendar(year, mes)
        for i, semana in enumerate(cal):
            for j, dia in enumerate(semana):
                if dia != 0:
                    nombres_vacaciones = self.obtener_vacaciones_por_dia(year, mes, dia)
                    color = COLORES_EMPLEADOS.get(nombres_vacaciones[0], "#f5f5f5") if nombres_vacaciones else "#f5f5f5"
                    texto = f"{dia}\n{', '.join(nombres_vacaciones)}" if nombres_vacaciones else str(dia)
                    tk.Button(marco, text=texto, bg=color, width=3, height=1, relief="groove",
                              command=lambda y=year, m=mes, d=dia: self.asignar_vacacion_interactiva(y, m, d)).grid(row=i+1, column=j, sticky='nsew')
    
    def asignar_vacacion_interactiva(self, year, month, day):
        nombre = simpledialog.askstring("Asignar Vacación", "Nombre del empleado:")
        if nombre:
            fecha = datetime(year, month, day)
            self.asignar_vacacion_empleado(nombre, fecha)
            self.actualizar_calendario()

calendario = CalendarioVacaciones()
for nombre in ["Mustri", "Limon", "CCI", "Toño", "Sick","Garo","Oso","Jesus"]:
    calendario.agregar_empleado(nombre)
calendario.mostrar_calendario()
