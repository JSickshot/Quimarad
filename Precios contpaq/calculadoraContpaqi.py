import tkinter as tk
from tkinter import messagebox

sistemas = {
    "Contabilidad": [
        {"tipo": "Licencia nueva multi - RFC", "precio": 5190, "costo_adicional": 1490},
        {"tipo": "Renovación multi - RFC", "precio": 4890, "costo_adicional": 1490},
        {"tipo": "Licencia nueva mono - RFC", "precio": 3790, "costo_adicional": 1490},
        {"tipo": "Renovación mono - RFC", "precio": 3690, "costo_adicional": 1490}
    ],
    "Nóminas": [
        {"tipo": "Licencia nueva 1 RFC", "precio": 4890, "costo_adicional": 1490},
        {"tipo": "Renovación 1 RFC", "precio": 4590, "costo_adicional": 1490},
        {"tipo": "Licencia nueva multi RFC", "precio": 6490, "costo_adicional": 1590},
        {"tipo": "Renovación multi RFC", "precio": 6090, "costo_adicional": 1590}
    ],
    "Bancos": [
        {"tipo": "Licencia nueva", "precio": 4490, "costo_adicional": 1390},
        {"tipo": "Renovación", "precio": 4190, "costo_adicional": 1390}
    ],
    "Comercial Premium": [
        {"tipo": "Licencia nueva multi - RFC", "precio": 8990, "costo_adicional": 2390},
        {"tipo": "Renovación multi - RFC", "precio": 8690, "costo_adicional": 2390}
    ],
    
    "Comercial start": [
        {"tipo": "Licencia nueva 1 RFC", "precio": 2390, "costo_adicional": 790},
        {"tipo": "Renovación 1 RFC", "precio": 2290, "costo_adicional": 690},
        {"tipo": "Licencia nueva multi - RFC", "precio": 3590, "costo_adicional": 1090},
        {"tipo": "Renovación Multi - RFC", "precio": 3390, "costo_adicional": 990}
    ],
    
    "XML en linea": [
        {"tipo": "Licencia nueva", "precio": 1790, "costo_adicional": 0},
        {"tipo": "Renovación", "precio": 1690, "costo_adicional": 0}
    ]
}

ventana = tk.Tk()
ventana.title("Cotizador CONTPAQi")
ventana.configure(bg="#f5f5f5")  


modo_suite = False
sistemas_seleccionados = []


def mostrar_menu_individual():
    global modo_suite
    modo_suite = False
    limpiar_busqueda()
    sistema_menu.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
    tipo_licencia_menu.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
    boton_agregar.grid_remove()

def mostrar_menu_suite():
    global modo_suite
    modo_suite = True
    limpiar_busqueda()
    sistema_menu.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
    tipo_licencia_menu.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
    boton_agregar.grid(row=4, column=0, columnspan=2, pady=10)

def actualizar_tipos_licencia(sistema_seleccionado):
    tipo_licencia_menu['menu'].delete(0, 'end')
    for licencia in sistemas[sistema_seleccionado]:
        tipo_licencia_menu['menu'].add_command(label=licencia["tipo"], command=tk._setit(tipo_licencia_var, licencia["tipo"]))

def agregar_sistema():
    sistema_seleccionado = sistema_var.get()
    tipo_licencia_seleccionado = tipo_licencia_var.get()
    
    try:
        usuarios_adicionales = int(entry_usuarios.get())
    except ValueError:
        messagebox.showerror("Error", "Ingresa un número de usuarios")
        return

    licencia = next((lic for lic in sistemas[sistema_seleccionado] if lic["tipo"] == tipo_licencia_seleccionado), None)
    if not licencia:
        messagebox.showerror("Error", "Selecciona un tipo de licencia")
        return

    sistemas_seleccionados.append({
        "sistema": sistema_seleccionado,
        "tipo": tipo_licencia_seleccionado,
        "precio": licencia["precio"],
        "costo_adicional": licencia["costo_adicional"],
        "usuarios_adicionales": usuarios_adicionales
    })
    messagebox.showinfo("Agregado", f"{sistema_seleccionado} - {tipo_licencia_seleccionado} agregado con {usuarios_adicionales} usuarios adicionales.")
    limpiar_busqueda()

def calcular_total():
    if not modo_suite:
        sistema_seleccionado = sistema_var.get()
        tipo_licencia_seleccionado = tipo_licencia_var.get()
        
        try:
            usuarios_adicionales = int(entry_usuarios.get())
        except ValueError:
            messagebox.showerror("Error", "ingresa un número de usuarios adicionales.")
            return

        licencia = next((lic for lic in sistemas[sistema_seleccionado] if lic["tipo"] == tipo_licencia_seleccionado), None)
        if not licencia:
            messagebox.showerror("Error", "Selecciona un tipo de licencia")
            return

        total = licencia["precio"] + (usuarios_adicionales * licencia["costo_adicional"])
    else:
        total = 0
        for seleccion in sistemas_seleccionados:
            total += seleccion["precio"] + (seleccion["usuarios_adicionales"] * seleccion["costo_adicional"])
        total *= 0.85 

    resultado_label.config(text=f"Total: ${total:.2f}")
    resultado_label.config(text=f"Total: ${total:,.2f}")
    limpiar_busqueda()

def limpiar_busqueda():
    sistema_var.set("Contabilidad")
    tipo_licencia_var.set("Seleccione un tipo de licencia")
    entry_usuarios.delete(0, tk.END)
    entry_usuarios.insert(0, "0")

boton_individual = tk.Button(ventana, text="Individual", command=mostrar_menu_individual, bg="#d9d9d9", fg="#333333", font=("Arial", 10, "bold"))
boton_individual.grid(row=0, column=0, padx=10, pady=10)
boton_suite = tk.Button(ventana, text="Suite (15% descuento)", command=mostrar_menu_suite, bg="#d9d9d9", fg="#333333", font=("Arial", 10, "bold"))
boton_suite.grid(row=0, column=1, padx=10, pady=10)

tk.Label(ventana, text="Sistema:", bg="#f5f5f5", fg="#333333", font=("Arial", 10)).grid(row=1, column=0, padx=10, pady=10)
sistema_var = tk.StringVar(ventana)
sistema_var.set("Contabilidad")
sistema_menu = tk.OptionMenu(ventana, sistema_var, *sistemas.keys(), command=lambda _: actualizar_tipos_licencia(sistema_var.get()))
sistema_menu.config(bg="#e6e6e6", fg="#333333", font=("Arial", 10))
sistema_menu.grid(row=2, column=1, padx=10, pady=10)

tk.Label(ventana, text="Usuarios adicionales:", bg="#f5f5f5", fg="#333333", font=("Arial", 10)).grid(row=5, column=0, padx=10, pady=10)
entry_usuarios = tk.Entry(ventana, bg="#ffffff", fg="#333333", font=("Arial", 10))
entry_usuarios.grid(row=5, column=1, padx=10, pady=10)
entry_usuarios.insert(0, "0")

tk.Label(ventana, text="Tipo de Licencia:", bg="#f5f5f5", fg="#333333", font=("Arial", 10)).grid(row=3, column=0, padx=10, pady=10)
tipo_licencia_var = tk.StringVar(ventana)
tipo_licencia_var.set("Seleccione un tipo de licencia")
tipo_licencia_menu = tk.OptionMenu(ventana, tipo_licencia_var, "")
tipo_licencia_menu.config(bg="#e6e6e6", fg="#333333", font=("Arial", 10))
tipo_licencia_menu.grid(row=3, column=1, padx=10, pady=10)

boton_agregar = tk.Button(ventana, text="Agregar", command=agregar_sistema, bg="#b0b0b0", fg="#333333", font=("Arial", 10))
boton_agregar.grid(row=4, column=0, columnspan=2, pady=10)
boton_agregar.grid_remove()

boton_calcular = tk.Button(ventana, text="Total", command=calcular_total, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))
boton_calcular.grid(row=6, column=0, columnspan=2, pady=10)

resultado_label = tk.Label(ventana, text="", bg="#f5f5f5", fg="#333333", font=("Arial", 12, "bold"))
resultado_label.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

ventana.mainloop()


# pyinstaller --onefile --noconsole --clean --icon=logo.ico calculadoraContpaqi.py


