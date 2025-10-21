from __future__ import annotations
import os
from typing import Callable, Set, Tuple

from core.sql import sql_conn, run_tsql
from core.attach import attach_catalog_by_name
from core.files import copy_data_tree  
from core.scripts import (
    tsql_contabilidad,
    tsql_nominas,
    tsql_comercial,
    tsql_add,
    tsql_checkdb_all,
)

CORE_CATALOGS = [
    "DB_Directory",
    "predeterminada",
    "generalessql",
    "CompacwAdmin",
    "repositorioadminpaq",
    "Nomgenerales",
]

def _log_noop(_: str) -> None:
    pass

def _attach_catalogs(conn, data_dst: str, log: Callable[[str], None]) -> Tuple[Set[str], Set[str]]:

    ok, fail = set(), set()
    log("Bases principales")
    for name in CORE_CATALOGS:
        try:
            attached = attach_catalog_by_name(conn, name, data_dst, on_log=log)
            if attached is False:
                log(f"   · {name}: ya existía (OK)")
            else:
                log(f"   · {name}: OK")
            ok.add(name)
        except Exception as ex:
            fail.add(name)
            log(f"   · {name}: ERROR  {ex}")
    return ok, fail

def _attach_empresas(conn, data_dst: str, log: Callable[[str], None]) -> Tuple[Tuple[Set[str], Set[str]], Tuple[Set[str], Set[str]], Tuple[Set[str], Set[str]]]:
    ok_c, fail_c = set(), set()
    ok_n, fail_n = set(), set()
    ok_m, fail_m = set(), set()

    log("Adjuntando EMPRESAS")
    try:
        run_tsql(conn, tsql_contabilidad(data_dst))
        log("   · Contabilidad: OK")
        ok_c.add("Contabilidad")
    except Exception as ex:
        fail_c.add("Contabilidad")
        log(f"   · Contabilidad: aviso/ERROR -> {ex}")

    try:
        run_tsql(conn, tsql_nominas(data_dst))
        log("   · Nóminas: OK")
        ok_n.add("Nóminas")
    except Exception as ex:
        fail_n.add("Nóminas")
        log(f"   · Nóminas: aviso/ERROR -> {ex}")

    try:
        run_tsql(conn, tsql_comercial(data_dst))
        log("   · Comercial: OK")
        ok_m.add("Comercial")
    except Exception as ex:
        fail_m.add("Comercial")
        log(f"   · Comercial: aviso/ERROR -> {ex}")

    return (ok_c, fail_c), (ok_n, fail_n), (ok_m, fail_m)

def _attach_add(conn, data_dst: str, log: Callable[[str], None]) -> Tuple[Set[str], Set[str]]:

    ok, fail = set(), set()
    log(" Adjuntando ADD")
    for caso in (1, 2, 3):
        try:
            run_tsql(conn, tsql_add(data_dst, caso))
            log(f"   · ADD (variante {caso}): OK")
            ok.add(f"ADD-var{caso}")
        except Exception as ex:
            fail.add(f"ADD-var{caso}")
            log(f"   · ADD (variante {caso}): aviso/ERROR  {ex}")
    return ok, fail

def _checkdb(conn, log: Callable[[str], None]) -> None:
    log("CHECKDB ")
    try:
        run_tsql(conn, tsql_checkdb_all())
        log("   · CHECKDB: OK ")
    except Exception as ex:
        log(f"   · CHECKDB: aviso/ERROR  {ex}")

def run_attach_task(
    instance: str,
    user: str | None,
    password: str | None,
    data_src: str,   
    data_dst: str,
    log_cb: Callable[[str], None] | None = None
) -> None:
   
    log = log_cb or _log_noop

    if not data_dst or not os.path.isdir(data_dst):
        raise RuntimeError(f"DATA DESTINO inválida o no existe: {data_dst}")

    log("Conectando a SQL…")
    with sql_conn(instance=instance, user=user, password=password, trusted=False) as conn:
        ok_cat, fail_cat = _attach_catalogs(conn, data_dst, log)
        (ok_c, fail_c), (ok_n, fail_n), (ok_m, fail_m) = _attach_empresas(conn, data_dst, log)
        ok_a, fail_a = _attach_add(conn, data_dst, log)

        _checkdb(conn, log)

        log("Resumen")
        def rep(lbl: str, s_ok: Set[str], s_fail: Set[str]) -> None:
            log(f"{lbl}: OK={len(s_ok)}  FAIL={len(s_fail)}")
            if s_ok:
                log("   OK:   " + ", ".join(sorted(s_ok)))
            if s_fail:
                log("   FAIL: " + ", ".join(sorted(s_fail)))
        rep("Catálogos", ok_cat, fail_cat)
        rep("Contabilidad", ok_c, fail_c)
        rep("Nóminas", ok_n, fail_n)
        rep("Comercial", ok_m, fail_m)
        rep("ADD", ok_a, fail_a)
