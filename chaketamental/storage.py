import os
import json

ARCHIVO_CONFIG = "config.json"

def guardar_xsd_usado(nombre_xsd, ruta_xsd):
    """
    Guarda la ruta de un XSD con su nombre en el archivo de configuración.
    """
    config = {}
    if os.path.exists(ARCHIVO_CONFIG):
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)

    if "xsds" not in config:
        config["xsds"] = {}

    config["xsds"][nombre_xsd] = ruta_xsd

    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def cargar_xsds_guardados():
    """
    Recupera todos los XSD guardados en forma de diccionario {nombre: ruta}.
    """
    if os.path.exists(ARCHIVO_CONFIG):
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("xsds", {})
    return {}
