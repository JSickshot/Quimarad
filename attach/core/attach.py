# core/attach.py
import os
from typing import Tuple
import pyodbc
from core.sql import db_exists

def _find_case_insensitive(dir_path: str, filename: str) -> str | None:
    target = filename.lower()
    try:
        for entry in os.listdir(dir_path):
            if entry.lower() == target:
                return os.path.join(dir_path, entry)
    except FileNotFoundError:
        return None
    return None

class AttachError(Exception):
    pass

def attach_database(conn: pyodbc.Connection, db_name: str, mdf_path: str, ldf_path: str) -> None:
    if not os.path.exists(mdf_path):
        raise AttachError(f"No existe MDF: {mdf_path}")
    if not os.path.exists(ldf_path):
        raise AttachError(f"No existe LDF: {ldf_path}")
    if db_exists(conn, db_name):
        return
    tsql = f"""
    CREATE DATABASE [{db_name}] ON 
      (FILENAME = N'{mdf_path}'),
      (FILENAME = N'{ldf_path}')
    FOR ATTACH;
    """
    conn.execute(tsql)

def attach_nomGenerales(conn: pyodbc.Connection, folder: str, force_name: str = "nomGenerales") -> Tuple[str, str]:
    mdf_file = _find_case_insensitive(folder, "nomGenerales.mdf")
    ldf_file = _find_case_insensitive(folder, "nomGenerales_log.ldf")
    if not mdf_file:
        raise AttachError("No se encontró 'nomGenerales.mdf' en la carpeta seleccionada.")
    if not ldf_file:
        raise AttachError("No se encontró 'nomGenerales_log.ldf' en la carpeta seleccionada.")
    attach_database(conn, force_name, mdf_file, ldf_file)
    return mdf_file, ldf_file

KNOWN_CATALOGS = [
    "DB_Directory",
    "predeterminada",
    "generalessql",
    "CompacwAdmin",
    "repositorioadminpaq",
    "nomGenerales",
]

def expected_files_for(db_name: str) -> Tuple[str, str]:
    return f"{db_name}.mdf", f"{db_name}_log.ldf"

def attach_catalog_by_name(conn: pyodbc.Connection, folder: str, db_name: str) -> Tuple[str, str, str]:
    if db_name.lower() == "nomgenerales":
        mdf, ldf = attach_nomGenerales(conn, folder)
        return ("nomGenerales", mdf, ldf)
    mdf_expected, ldf_expected = expected_files_for(db_name)
    mdf_file = _find_case_insensitive(folder, mdf_expected)
    ldf_file = _find_case_insensitive(folder, ldf_expected)
    if not mdf_file:
        raise AttachError(f"No se encontró '{mdf_expected}' en la carpeta seleccionada.")
    if not ldf_file:
        raise AttachError(f"No se encontró '{ldf_expected}' en la carpeta seleccionada.")
    attach_database(conn, db_name, mdf_file, ldf_file)
    return (db_name, mdf_file, ldf_file)
