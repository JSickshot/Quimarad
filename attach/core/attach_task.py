import os
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
    "nomGenerales",
]
ALT_NAMES = {
    "DB_Directory": ["db_directory", "DB_DIRECTORY"],
    "predeterminada": ["Predeterminada"],
    "generalessql": ["GeneralesSQL", "GENERALESSQL"],
    "CompacwAdmin": ["compacwadmin", "COMPACWADMIN", "CompacWAdmin"],
    "repositorioadminpaq": ["RepositorioAdminPAQ"],
    "nomGenerales": ["Nomgenerales", "nomgenerales", "NOMGENERALES"],
}
EXCLUDE_ORPHANS = set(["master", "model", "msdb", "tempdb"]) | set(CORE_CATALOGS) | set(n for alts in ALT_NAMES.values() for n in alts)

def _db_exists(conn, name)->bool:
    try:
        c=conn.cursor(); c.execute("SELECT DB_ID(?)", name); r=c.fetchone(); c.close()
        return bool(r and r[0] is not None)
    except Exception:
        return False

def _candidates_mdf(data_path: str, name: str):
    names = [name] + ALT_NAMES.get(name, [])
    cands = []
    for n in names:
        p = os.path.join(data_path, f"{n}.mdf")
        if os.path.exists(p): cands.append(p)
    try:
        for fn in os.listdir(data_path):
            if fn.lower().endswith(".mdf"):
                base = os.path.splitext(fn)[0].lower()
                for n in names:
                    if n.lower() == base or n.lower() in base:
                        cands.append(os.path.join(data_path, fn))
    except Exception:
        pass
    seen, uniq = set(), []
    for p in cands:
        lp = p.lower()
        if lp not in seen:
            seen.add(lp); uniq.append(p)
    return uniq

def _candidates_ldf(data_path: str, base_without_ext: str):
    cands = []
    for pattern in (f"{base_without_ext}_log.ldf", f"{base_without_ext}.ldf"):
        p = os.path.join(data_path, pattern)
        if os.path.exists(p): cands.append(p)
    try:
        for fn in os.listdir(data_path):
            if fn.lower().endswith(".ldf") and base_without_ext.lower() in fn.lower():
                cands.append(os.path.join(data_path, fn))
    except Exception:
        pass
    seen, uniq = set(), []
    for p in cands:
        lp = p.lower()
        if lp not in seen:
            seen.add(lp); uniq.append(p)
    return uniq

def _force_attach_catalog(conn, data_path_for_sql: str, cat_name: str, log):
    if _db_exists(conn, cat_name):
        log(f"   [{cat_name}] ya adjunta (verificación).")
        return True
    data_path = data_path_for_sql.rstrip("\\/")
    mdf_list = _candidates_mdf(data_path, cat_name)
    if not mdf_list:
        log(f"   [MISS] {cat_name}: no encontré MDF en {data_path}")
        return False
    for mdf in mdf_list:
        base = os.path.splitext(os.path.basename(mdf))[0]
        ldfs = _candidates_ldf(os.path.dirname(mdf), base)
        mdf_sql = mdf.replace("/", "\\")
        try:
            c = conn.cursor()
            if ldfs:
                ldf_sql = ldfs[0].replace("/", "\\")
                sql = f"CREATE DATABASE [{cat_name}] ON (FILENAME=N'{mdf_sql}'), (FILENAME=N'{ldf_sql}') FOR ATTACH;"
            else:
                sql = f"CREATE DATABASE [{cat_name}] ON (FILENAME=N'{mdf_sql}') FOR ATTACH_REBUILD_LOG;"
            c.execute(sql); c.close()
            if _db_exists(conn, cat_name):
                log(f"   [FORCE OK] {cat_name}: {os.path.basename(mdf_sql)} | {(os.path.basename(ldf_sql) if ldfs else '(rebuild log)')}")
                return True
        except Exception as ex:
            log(f"   [FORCE Advertencia ] {cat_name}: {ex}")
    log(f"   [FORCE FAIL] {cat_name}: no se pudo adjuntar.")
    return False

def _run_query_table(conn, db, query):
    cur = conn.cursor()
    cur.execute(f"USE [{db}]; {query}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall(); cur.close()
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]

def _fetch_aliases(conn, log):
    contab, nom, comer, addset = set(), set(), set(), set()

    # CONTABILIDAD
    for dbn in ("generalessql", "GeneralesSQL", "GENERALESSQL"):
        try:
            if not _db_exists(conn, dbn): 
                continue
            rows = _run_query_table(conn, dbn, "SELECT aliasbdd FROM listaempresas WHERE NULLIF(aliasbdd,'') IS NOT NULL;")
            for r in rows:
                a = (r.get("aliasbdd") or "").strip()
                if a: contab.add(a)
            log(f"   (Contabilidad) {dbn}: {len(contab)} alias acumulados")
            break
        except Exception as e:
            log(f"   (Contabilidad) {dbn} Advertencia : {e}")

    # NOMINAS
    for dbn in ("Nomgenerales", "nomgenerales", "NOMGENERALES", "nomGenerales"):
        try:
            if not _db_exists(conn, dbn): 
                continue
            rows = _run_query_table(conn, dbn, "SELECT rutaempresa FROM nom10000 WHERE NULLIF(rutaempresa,'') IS NOT NULL;")
            for r in rows:
                ruta = (r.get("rutaempresa") or "").strip().rstrip("\\/")
                if ruta:
                    alias = ruta.split("\\")[-1]
                    if alias: nom.add(alias)
            log(f"   (Nóminas) {dbn}: {len(nom)} alias acumulados")
            break
        except Exception as e:
            log(f"   (Nóminas) {dbn} Advertencia : {e}")

    # COMERCIAL
    for dbn in ("CompacwAdmin","compacwadmin","COMPACWADMIN","CompacWAdmin"):
        try:
            if not _db_exists(conn, dbn): 
                continue
            rows = _run_query_table(conn, dbn, r"""
                SELECT 
                  Alias = REVERSE(SUBSTRING(REVERSE(crutadatos),1,CHARINDEX('\',REVERSE(crutadatos))-1))
                FROM Empresas
                WHERE NULLIF(crutadatos,'') IS NOT NULL
                  AND crutadatos LIKE '%\%';
            """)
            for r in rows:
                a = (r.get("Alias") or "").strip()
                if a: comer.add(a)
            log(f"   (Comercial) {dbn}: {len(comer)} alias acumulados")
            break
        except Exception as e:
            log(f"   (Comercial) {dbn} Advertencia : {e}")

    for dbn in ("DB_Directory","db_directory","DB_DIRECTORY"):
        try:
            if not _db_exists(conn, dbn): 
                continue
            rows = _run_query_table(conn, dbn, """
                SELECT DB_DocumentsMetadata,DB_DocumentsContent,DB_OthersMetadata,DB_OthersContent
                FROM DatabaseDirectory;
            """)
            for r in rows:
                for col in ("DB_DocumentsMetadata","DB_DocumentsContent","DB_OthersMetadata","DB_OthersContent"):
                    a = (str(r.get(col) or "")).strip()
                    if a: addset.add(a)
            log(f"   (ADD) {dbn}: {len(addset)} alias únicos")
            break
        except Exception as e:
            log(f"   (ADD) {dbn} Advertencia : {e}")

    log(f"   Aliases CONTA:{len(contab)}  NOM:{len(nom)}  COMER:{len(comer)}  ADD:{len(addset)}")
    return contab, nom, comer, addset

def _attach_one_db_by_files(conn, data_path: str, name: str, log):
    if _db_exists(conn, name):
        return True
    mdf = None
    cand1 = os.path.join(data_path, f"{name}.mdf")
    if os.path.exists(cand1):
        mdf = cand1
    else:
        try:
            for fn in os.listdir(data_path):
                if fn.lower().endswith(".mdf"):
                    base = os.path.splitext(fn)[0]
                    if base.lower()==name.lower() or name.lower() in base.lower():
                        mdf = os.path.join(data_path, fn); break
        except Exception:
            pass
    if not mdf:
        log(f"      [{name}] sin MDF en DESTINO, omito")
        return False
    base = os.path.splitext(os.path.basename(mdf))[0]
    ldf = None
    for pat in (f"{base}_log.ldf", f"{base}.ldf"):
        cand = os.path.join(data_path, pat)
        if os.path.exists(cand):
            ldf = cand; break
    if not ldf:
        try:
            for fn in os.listdir(data_path):
                if fn.lower().endswith(".ldf") and base.lower() in fn.lower():
                    ldf = os.path.join(data_path, fn); break
        except Exception:
            pass
    mdf_sql = mdf.replace("/", "\\")
    try:
        c = conn.cursor()
        if ldf and os.path.exists(ldf):
            ldf_sql = ldf.replace("/", "\\")
            sql = f"CREATE DATABASE [{name}] ON (FILENAME=N'{mdf_sql}'), (FILENAME=N'{ldf_sql}') FOR ATTACH;"
        else:
            sql = f"CREATE DATABASE [{name}] ON (FILENAME=N'{mdf_sql}') FOR ATTACH_REBUILD_LOG;"
        c.execute(sql); c.close()
        ok = _db_exists(conn, name)
        log(f"      [{'OK' if ok else 'Advertencia '}] attach {name}")
        return ok
    except Exception as ex:
        log(f"      Advertencia  attach {name}: {ex}")
        return False

def _attach_group_from_aliases(conn, data_path: str, aliases: set, titulo: str, log=None):
    if not aliases:
        if log: log(f"   ({titulo}) sin alias para adjuntar.")
        return set(), set()
    if log: log(f"   ({titulo}) adjuntando desde DESTINO: {data_path}")
    ok, fail = set(), set()
    for alias in sorted(set(aliases), key=lambda s:s.lower()):
        if _attach_one_db_by_files(conn, data_path, alias, log):
            ok.add(alias)
        else:
            fail.add(alias)
    return ok, fail

def _attach_orphans(conn, data_path: str, log):
    try:
        files = [f for f in os.listdir(data_path) if f.lower().endswith(".mdf")]
    except Exception:
        log("   Opcion 2 No pude listar DESTINO.")
        return
    log("   Opcion 2 Buscando  en DESTINO")
    for fn in sorted(files, key=lambda x: x.lower()):
        base = os.path.splitext(fn)[0]
        if base in EXCLUDE_ORPHANS: continue
        if _db_exists(conn, base): continue
        _attach_one_db_by_files(conn, data_path, base, log)

def run_attach_task(instance: str, user: str, password: str, data_src: str, data_dst: str, log_cb=print):
    def log(msg):
        if log_cb: log_cb(msg)

    if not instance: raise ValueError("Indica la instancia SQL.")
    if not data_src or not os.path.isdir(data_src): raise ValueError("DATA ORIGEN inválida.")
    if not data_dst: raise ValueError("DATA DESTINO requerida.")

    log(f"> Copiando : {data_src}    {data_dst}")
    copied = copy_data_tree(data_src, data_dst, skip_existing=True)
    if copied:
        for _, d in copied:
            log(f"  copiado: {os.path.basename(d)}")
    else:
        log("  (no había archivos nuevos por copiar)")

    data_path_for_sql = data_dst if data_dst.endswith("\\") else (data_dst + "\\")

    with sql_conn(instance, trusted=False, user=user, password=password) as conn:
        log("> Adjuntando catálogos")
        for db in CORE_CATALOGS:
            try:
                name, mdf, ldf = attach_catalog_by_name(conn, data_path_for_sql, db)
                log(f"   [OK] {name}: {os.path.basename(mdf)} | {os.path.basename(ldf) if ldf else '(rebuild log)'}")
            except FileNotFoundError as nf:
                log(f"   [MISS] {db}: {nf}")
            except Exception as ex1:
                log(f"   Advertencia  {db}: {ex1}")

        log("> Verificando catálogos")
        for db in CORE_CATALOGS:
            if not _db_exists(conn, db):
                _force_attach_catalog(conn, data_path_for_sql, db, log)
            else:
                log(f"   [{db}] OK.")

        log("[2/3] Consultando catálogos")
        contab, nom, comer, addset = _fetch_aliases(conn, log)
        
        ok_c, fail_c = _attach_group_from_aliases(conn, data_path_for_sql, contab, "CONTABILIDAD", log)
        ok_n, fail_n = _attach_group_from_aliases(conn, data_path_for_sql, nom,    "NÓMINAS", log)
        ok_m, fail_m = _attach_group_from_aliases(conn, data_path_for_sql, comer,  "COMERCIAL", log)
        ok_a, fail_a = set(), set()

        if not (contab or nom or comer or addset):
            log("   Opcion 2 Sin alias  adjunto ")
            _attach_orphans(conn, data_path_for_sql, log)

        log("[3/3] CHECKDB en las bases")
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sys.databases WHERE database_id>4 ORDER BY name;")
            dbs = [r[0] for r in cur.fetchall()]
            cur.close()
            for n in dbs:
                try:
                    c2 = conn.cursor(); c2.execute(f"DBCC CHECKDB([{n}]) WITH NO_INFOMSGS, PHYSICAL_ONLY;"); c2.close()
                except Exception as eck:
                    log(f"   Advertencia  CHECKDB {n}: {eck}")
            log("   [OK] CHECKDB finalizado.")
        except Exception as exck:
            log(f"   Advertencia  CHECKDB: {exck}")

        # 6) Resumen
        log("----- Resumen -----")
        def rep(lbl, s_ok, s_fail):
            log(f"{lbl}: OK={len(s_ok)}  FAIL={len(s_fail)}")
            if s_fail:
                for n in sorted(s_fail): log(f"   - {n}")
        rep("Contabilidad", ok_c, fail_c)
        rep("Nóminas", ok_n, fail_n)
        rep("Comercial", ok_m, fail_m)
        rep("ADD", ok_a, fail_a)
