import tkinter as tk
from tkinter import filedialog, messagebox

def generar_xml(folio, referencia, observacion):
    xml = (
        "<cfdi:Addenda>\n"
        "    <Tickets>\n"
        f'        <Ticket Folio="{folio}" Referencia="{referencia}" Observacion="{observacion}"/>\n'
        "    </Tickets>\n"
        "</cfdi:Addenda>\n"
    )
    return xml

def agregar_addenda(xml_path, folio, referencia, observacion):
    with open(xml_path, "r", encoding="utf-8") as f:
        contenido = f.read()

    addenda = generar_xml(folio, referencia, observacion)

    if "</cfdi:Complemento>" in contenido:
        nuevo_contenido = contenido.replace("</cfdi:Complemento>", "</cfdi:Complemento>\n" + addenda, 1)
    else:
        messagebox.showerror("Error", "El archivo XML no contiene </cfdi:Complemento>")
        return
    
    #nuevoarchivo
    nuevo_path = xml_path.replace(".xml", "_addenda.xml")
    with open(nuevo_path, "w", encoding="utf-8") as f:
        f.write(nuevo_contenido)

    messagebox.showinfo("Éxito", f"Se generó el archivo con Addenda:\n{nuevo_path}")

def seleccionar_xml():
    xml_path = filedialog.askopenfilename(filetypes=[("Archivos XML", "*.xml")])
    if xml_path:
        folio = "12345"
        referencia = "REF-001"
        observacion = "Observación automática"
        agregar_addenda(xml_path, folio, referencia, observacion)

root = tk.Tk()
root.title("Agregar Addenda al XML")

btn_xml = tk.Button(root, text="Seleccionar XML", command=seleccionar_xml)
btn_xml.pack(pady=20)

root.mainloop()
