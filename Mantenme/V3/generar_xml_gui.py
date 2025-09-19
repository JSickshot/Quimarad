from interfaz import entry_folio, entry_referencia


from tkinter import filedialog, messagebox


def generar_xml_gui():
    folio = entry_folio.get()
    referencia = entry_referencia.get()

    if not folio or not referencia:
        messagebox.showerror("Error", "Debe ingresar Folio y Referencia")
        return

    ruta_excel = filedialog.askopenfilename(
        title="Selecciona el archivo Excel",
        filetypes=[("Archivos Excel", "*.xlsx *.xls")]
    )
    if not ruta_excel:
        return

    salida_txt = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Archivo TXT", "*.txt")],
        title="Guardar archivo como"
    )
    if not salida_txt:
        return

    observacion = generar_observacion(ruta_excel)
    xml = construir_xml(folio, referencia, observacion)
    guardar_xml(xml, salida_txt)

    messagebox.showinfo("Éxito", f"Archivo generado en: {salida_txt}")