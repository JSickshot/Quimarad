import pandas as pd

def generar_xml():
    folio = input("f ")
    referencia = input("r ")
    excel = input("e")
    txt = input("txt ")

    df = pd.read_excel(excel)

    observacion = ""
    for _, fila in df.iterrows():
        observacion+="".join([str(fila[col]) for col in df.columns])

    xml = f"""
    <cfdi:Addenda>
    <Tickets>
    <Ticket Folio="{folio}" Referencia="{referencia}" Observacion="{observacion}"/>
    </Tickets>
    </cfdi:Addenda>
    """

    with open(txt, "w") as f:
        f.write(xml)

    print(f"txt{txt}")

if __name__ == "__main__":
    generar_xml()




    #df.columns son los títulos del Excel (Fecha, Hora, Usuario, etc.).
    #fila[col] toma el valor de la columna col en esa fila.
    #pd.notna(fila[col]) evita meter valores vacíos (NaN).
    #str(fila[col]) convierte el valor a texto para poder concatenarlo.
    #El for construye una lista de strings con todos los valores de la fila.