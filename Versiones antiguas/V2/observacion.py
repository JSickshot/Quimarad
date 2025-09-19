import pandas as pd

def generar_observacion(ruta_excel):
    df = pd.read_excel(ruta_excel, keep_default_na=False)
    observacion = ""
    for _, fila in df.iterrows():
        fila_texto = "".join([str(fila[col]) for col in df.columns])
        observacion += fila_texto
    return observacion
