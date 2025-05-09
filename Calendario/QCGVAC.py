import calendar
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

EMPLEADOS_INFO = {
    "Esmeralda Reyes": {"ingreso": "2021-06-01"},
    "Juan Amador": {"ingreso": "2022-11-14"},
    "Alejandro Amador": {"ingreso": "2023-04-01"},
    "Antonio Barrera": {"ingreso": "2015-08-01"},
    "Julio Burgoin": {"ingreso": "2024-02-06"},
    "Edgar Quiroz": {"ingreso": "2012-01-01"},
    "Adolfo Quiroz": {"ingreso": "2012-01-01"},
    "Jesus Gonzalez": {"ingreso": "2024-12-02"},
    "Angela Villareal": {"ingreso": "2021-02-01"}
}

COLORES_EMPLEADOS = {
    "Esmeralda Reyes": "#FFFF99",
    "Juan Amador": "#98FB98",
    "Alejandro Amador": "#FFA07A",
    "Antonio Barrera": "#ADD8E6",
    "Julio Burgoin": "#8B0000",
    "Edgar Quiroz": "#E00000",
    "Adolfo Quiroz": "#C7C7C6",
    "Jesus Gonzalez": "#FC4B08",
    "Angela Villareal": "#572364"
}

conn = sqlite3.connect('QCG.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS vacaciones (
    empleado TEXT,
    fecha TEXT)''')
conn.commit()

class Empleado:
    def __init__(self, nombre):
        self.nombre = nombre
        self.vacaciones = self.cargar_vacaciones()

    def cargar_vacaciones(self):
        cursor.execute("SELECT fecha FROM vacaciones WHERE empleado=?", (self.nombre,))
        fechas = cursor.fetchall()
        return [datetime.strptime(fecha[0], '%Y-%m-%d') for fecha in fechas]

    def asignar_vacacion(self, fecha):
        if fecha not in self.vacaciones:
            self.vacaciones.append(fecha)
            cursor.execute("INSERT INTO vacaciones (empleado, fecha) VALUES (?, ?)", (self.nombre, fecha.strftime('%Y-%m-%d')))
            conn.commit()

    def eliminar_vacacion(self, fecha):
        if fecha in self.vacaciones:
            self.vacaciones.remove(fecha)
            cursor.execute("DELETE FROM vacaciones WHERE empleado=? AND fecha=?", (self.nombre, fecha.strftime('%Y-%m-%d')))
            conn.commit()

    def obtener_dias_disponibles(self, año):
        ingreso = datetime.strptime(EMPLEADOS_INFO[self.nombre]["ingreso"], "%Y-%m-%d")
        antiguedad = max(0, año - ingreso.year)

        if antiguedad == 0:
            totales = 0
        elif antiguedad == 1:
            totales = 12
        elif antiguedad == 2:
            totales = 14
        elif antiguedad == 3:
            totales = 16
        elif antiguedad == 4:
            totales = 18
        elif antiguedad == 5:
            totales = 20
        elif 6 <= antiguedad <= 10:
            totales = 22
        elif 11 <= antiguedad <= 15:
            totales = 24
        elif 16 <= antiguedad <= 20:
            totales = 26
        elif 21 <= antiguedad <= 25:
            totales = 28
        elif 26 <= antiguedad <= 30:
            totales = 30
        elif 31 <= antiguedad <= 35:
            totales = 32

        dias_usados = sum(1 for fecha in self.vacaciones if fecha.year == año)
        return max(0, totales - dias_usados)

class CalendarioVacaciones:
    def __init__(self):
        self.empleados = [Empleado(nombre) for nombre in EMPLEADOS_INFO]
        self.ventana_principal = None
        self.canvas = None
        self.scrollable_frame = None

    def mostrar_calendario(self):
        self.ventana_principal = tk.Tk()
        self.ventana_principal.title("Calendario de Vacaciones")
        self.ventana_principal.state("zoomed")

        menu = tk.Menu(self.ventana_principal)
        self.ventana_principal.config(menu=menu)
        archivo_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Archivo", menu=archivo_menu)
        archivo_menu.add_command(label="Exportar Vacaciones", command=self.exportar_vacaciones)
        archivo_menu.add_command(label="Exportar Vacaciones de un Empleado", command=self.exportar_vacaciones_empleado)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Días restantes", command=self.mostrar_vacaciones_restantes)
        
        self.canvas = tk.Canvas(self.ventana_principal)
        scrollbar_y = tk.Scrollbar(self.ventana_principal, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar_y.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

        self.actualizar_calendario()
        self.ventana_principal.mainloop()

    def actualizar_calendario(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.crear_calendario_anual(self.scrollable_frame, 2025) #modificar parametro para 2026

    def crear_calendario_anual(self, contenedor, year):
        for mes in range(1, 13):
            marco = ttk.LabelFrame(contenedor, text=calendar.month_name[mes])
            marco.grid(row=(mes-1)//6, column=(mes-1)%6, padx=5, pady=5)
            self.crear_mes(marco, year, mes)

    def crear_mes(self, marco, year, mes):
        dias_semana = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
        for i, dia in enumerate(dias_semana):
            tk.Label(marco, text=dia, bg="#1e0c85", fg="white", width=5, height=2).grid(row=0, column=i)

        cal = calendar.monthcalendar(year, mes)
        for i, semana in enumerate(cal):
            for j, dia in enumerate(semana):
                if dia != 0:
                    nombres = self.obtener_vacaciones_por_dia(year, mes, dia)
                    color = COLORES_EMPLEADOS.get(nombres[0], "#f5f5f5") if nombres else "#f5f5f5"
                    texto = f"{dia}\n{', '.join(nombres)}" if nombres else str(dia)
                    tk.Button(
                        marco,
                        text=texto,
                        bg=color,
                        width=4,
                        height=2,
                        wraplength=40,
                        justify="center",
                        command=lambda y=year, m=mes, d=dia: self.asignar_vacacion_interactiva(y, m, d)
                    ).grid(row=i+1, column=j)

    def obtener_vacaciones_por_dia(self, year, month, day):
        return [emp.nombre for emp in self.empleados if datetime(year, month, day) in emp.vacaciones]

    def asignar_vacacion_interactiva(self, year, month, day):
        ventana = tk.Toplevel(self.ventana_principal)
        ventana.title(f"Vacaciones {day}/{month}/{year}")
        ventana.geometry("300x300")

        tk.Label(ventana, text="Empleado:").pack()
        nombre_var = tk.StringVar()
        combo = ttk.Combobox(ventana, textvariable=nombre_var, values=[e.nombre for e in self.empleados])
        combo.pack()

        fecha = datetime(year, month, day)
        empleados_dia = self.obtener_vacaciones_por_dia(year, month, day)
        if empleados_dia:
            tk.Label(ventana, text="Ya asignado a:").pack()
            for nombre in empleados_dia:
                tk.Label(ventana, text=nombre).pack()

        def guardar():
            nombre = nombre_var.get()
            if nombre:
                empleado = next((e for e in self.empleados if e.nombre == nombre), None)
                if empleado:
                    empleado.asignar_vacacion(fecha)
                    self.actualizar_calendario()
                    ventana.destroy()

        def eliminar():
            nombre = nombre_var.get()
            if nombre:
                empleado = next((e for e in self.empleados if e.nombre == nombre), None)
                if empleado:
                    empleado.eliminar_vacacion(fecha)
                    self.actualizar_calendario()
                    ventana.destroy()

        tk.Button(ventana, text="Guardar", command=guardar, bg="#0E1F53", fg="white").pack(pady=10)
        tk.Button(ventana, text="Eliminar", command=eliminar, bg="red", fg="white").pack(pady=5)

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
        nombre = simpledialog.askstring("Exportar", "Nombre del empleado:")
        if nombre:
            archivo = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if archivo:
                with open(archivo, 'w') as f:
                    f.write("Empleado,Fecha\n")
                    cursor.execute("SELECT fecha FROM vacaciones WHERE empleado=?", (nombre,))
                    for fecha, in cursor.fetchall():
                        f.write(f"{nombre},{fecha}\n")
                messagebox.showinfo("Exportado", "Vacaciones del empleado exportadas.")

    def mostrar_vacaciones_restantes(self):
        ventana = tk.Toplevel(self.ventana_principal)
        ventana.title("Vacaciones Restantes por Empleado")
        ventana.geometry("600x400")
        año_actual = datetime.now().year

        tree = ttk.Treeview(ventana, columns=("Ingreso", "Días Restantes"), show="headings")
        tree["columns"] = ("Empleado", "Ingreso", "Días Restantes")
        tree.heading("Empleado", text="Empleado")
        tree.heading("Ingreso", text="Fecha Ingreso")
        tree.heading("Días Restantes", text=f"Días restantes")
        tree.column("Empleado", width=200)

        for empleado in self.empleados:
            nombre = empleado.nombre
            ingreso = EMPLEADOS_INFO[nombre]["ingreso"]
            restantes = empleado.obtener_dias_disponibles(año_actual)
            tree.insert("", "end", values=(nombre, ingreso, restantes))

        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def exportar():
            archivo = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if archivo:
                with open(archivo, "w") as f:
                    f.write("Empleado,Ingreso,Dias Restantes\n")
                    for row in tree.get_children():
                        valores = tree.item(row)['values']
                        f.write(",".join(str(v) for v in valores) + "\n")
                messagebox.showinfo("Exportado", "Vacaciones restantes exportadas.")

        tk.Button(ventana, text="Excel", command=exportar, bg="green", fg="white").pack(pady=10)

if __name__ == "__main__":
    calendario = CalendarioVacaciones()
    calendario.mostrar_calendario()
