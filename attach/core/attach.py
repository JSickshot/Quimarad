# core/attach.py
import os
import shutil
import time
from typing import Tuple, Set, List

# ======= Catálogos base y utilidades =======

CATALOGS_IN_ORDER: List[str] = [
    "DB_Directory",
    "predeterminada",
    "generalessql",
    "CompacwAdmin",
    "repositorioadminpaq",
    "nomGenerales",  # variantes: Nomgenerales/nomgenerales
]

CATALOG_ALT_NAMES = {
    "DB_Directory": ["db_directory", "DB_DIRECTORY"],
    "predeterminada": [],
    "generalessql": ["GeneralesSQL", "GENERALESSQL"],
    "CompacwAdmin": ["compacwadmin", "COMPACWADMIN"],
    "repositorioadminpaq": ["RepositorioAdminPAQ", "REPOSITORIOADMINPAQ"],
    "nomGenerales": ["Nomgenerales", "nomgenerales"],
}

EXCLUDE_DB_NAMES = set([
    "master", "model", "msdb", "tempdb",
    "DB_Directory", "db_directory", "DB_DIRECTORY",
    "predeterminada",
    "generalessql", "GeneralesSQL", "GENERALESSQL",
    "CompacwAdmin", "compacwadmin", "COMPACWADMIN",
    "repositorioadminpaq", "RepositorioAdminPAQ", "REPOSITORIOADMINPAQ",
    "nomGenerales", "Nomgenerales", "nomgenerales",
])

READ_ERRORLOG_ON_FAIL = False  # el caller puede ajustarlo

def _log(tbox, msg: str):
    """Log seguro hacia un tk.Text u objeto similar."""
    try:
        tbox.insert("end", msg + "\n")
        tbox.see("end")
        tbox.update_idletasks()
    except Exception:
        # fallback silencioso
        pass

def _norm(s: str) -> str:
    return (s or "").lower().replace("_", "").replace("-", "").replace(" ", "")

# ======= Inspección de archivos =======

def walk_collect(root: str) -> Tuple[Set[str], Set[str], Set[str]]:
    mdfs, ldfs, ndfs = set(), set(), set()
    if not root:
        return mdfs, ldfs, ndfs
    for r, _, files in os.walk(root):
        for fn in files:
            full = os.path.join(r, fn)
            l = full.lower()
            if l.endswith(".mdf"):
                mdfs.add(full)
            elif l.endswith(".ldf"):
                ldfs.add(full)
            elif l.endswith(".ndf"):
                ndfs.add(full)
    return mdfs, ldfs, ndfs

def list_files_in_data_via_sql(conn, data_path: str):
    """Devuelve (mdfs, ldfs). Si la ruta es accesible desde el proceso, usa os.walk."""
    folder = data_path.rstrip("\\/")
    if os.path.exists(folder):
        mdfs, ldfs, _ = walk_collect(folder)
        return mdfs, ldfs

    # Fallback: igual intentar os.walk (por si no hay permisos xp_dirtree)
    mdfs, ldfs, _ = walk_collect(folder)
    return mdfs, ldfs

def resolve_ldf_for_alias_in_dest(dest_path: str, alias: str) -> str | None:
    """Heurística para encontrar LDF a partir del alias/base name."""
    trials = [f"{alias}_log.ldf", f"{alias}.ldf"]
    for t in trials:
        cand = os.path.join(dest_path, t)
        if os.path.exists(cand):
            return cand
    try:
        for fn in os.listdir(dest_path):
            l = fn.lower()
            if l.endswith(".ldf") and (_norm(alias) in _norm(os.path.splitext(fn)[0])):
                return os.path.join(dest_path, fn)
    except Exception:
        pass
    return None

# ======= SQL helpers =======

def db_exists(conn, name: str) -> bool:
    c = conn.cursor()
    c.execute("SELECT DB_ID(?)", name)
    r = c.fetchone()
    c.close()
    return bool(r and r[0] is not None)

def preflight_path(conn, tbox, mdf: str, ldf: str | None) -> bool:
    ok = True
    for p in [mdf] + ([ldf] if ldf else []):
        if not p:
            continue
        if not os.path.exists(p):
            _log(tbox, f"      (X) No existe en disco: {p}")
            ok = False
            continue
        try:
            mode = os.stat(p).st_mode
            if mode & 0o222 == 0:
                os.chmod(p, 0o666)
                _log(tbox, f"      Quité solo-lectura: {os.path.basename(p)}")
        except Exception as e:
            _log(tbox, f"      Aviso permisos: {e}")

        # Visibilidad para SQL Server (si xp_fileexist está disponible)
        try:
            c = conn.cursor()
            c.execute("EXEC master..xp_fileexist ?", p)
            row = c.fetchone()
            c.close()
            if not (row and row[0] == 1):
                _log(tbox, f"      (X) SQL Server NO ve: {p}")
                ok = False
            else:
                _log(tbox, f"      (✓) SQL ve: {os.path.basename(p)}")
        except Exception:
            pass
    return ok

def attach_by_paths(conn, tbox, name: str, mdf: str, ldf: str | None) -> bool:
    """Crea FOR ATTACH; evita parámetros (que causan @P1) y arma SQL literal."""
    _log(tbox, f"   > Checar [{name}] …")
    if not preflight_path(conn, tbox, mdf, ldf):
        _log(tbox, f"   [{name}] Checar falló  omito attach")
        return False

    mdf_sql = mdf.replace("'", "''").replace("/", "\\")
    if ldf:
        ldf_sql = (ldf or "").replace("'", "''").replace("/", "\\")
        sql = f"CREATE DATABASE [{name}] ON (FILENAME=N'{mdf_sql}'), (FILENAME=N'{ldf_sql}') FOR ATTACH;"
    else:
        sql = f"CREATE DATABASE [{name}] ON (FILENAME=N'{mdf_sql}') FOR ATTACH_REBUILD_LOG;"

    try:
        c = conn.cursor()
        c.execute(sql)
        c.close()
        _log(tbox, f"   [OK] {name}: {os.path.basename(mdf)} | {os.path.basename(ldf) if ldf else '(rebuild log)'}")
        return True
    except Exception as e:
        _log(tbox, f"   [WARN] {name}: {e}")
        if READ_ERRORLOG_ON_FAIL:
            try:
                c = conn.cursor()
                c.execute("EXEC master.dbo.xp_readerrorlog 0,1,N'Error',NULL,NULL,NULL,N'desc';")
                rows = c.fetchall()
                c.close()
                shown = 0
                _log(tbox, "      --- ERRORLOG reciente (resumen) ---")
                for r in rows:
                    line = " ".join(str(x) for x in r if x is not None)
                    if any(k in line for k in ("5120", "5105", "Access is denied", "Operating system error")):
                        _log(tbox, "      " + line)
                        shown += 1
                    if shown >= 20:
                        break
                if shown == 0:
                    _log(tbox, "      (sin entradas relevantes en ERRORLOG)")
            except Exception as e2:
                _log(tbox, f"      (no pude leer ERRORLOG: {e2})")
        return False

def attach_catalog_by_name(conn, data_path_for_sql: str, dbname: str) -> Tuple[str, str, str | None]:
    """
    Busca MDF/LDF en DATA destino y ejecuta FOR ATTACH. Retorna (nombre, mdf, ldf) si adjunta.
    Lanza FileNotFoundError si no encuentra MDF.
    """
    if db_exists(conn, dbname):
        return dbname, "", ""  

    mdfs, ldfs = list_files_in_data_via_sql(conn, data_path_for_sql)
    mdf = None


    for full in mdfs:
        if os.path.basename(full).lower() == f"{dbname.lower()}.mdf":
            mdf = full
            break

    if not mdf:
        for alt in CATALOG_ALT_NAMES.get(dbname, []):
            cand = os.path.join(data_path_for_sql, f"{alt}.mdf")
            if os.path.exists(cand):
                mdf = cand
                break

    if not mdf:
        for full in mdfs:
            base = os.path.splitext(os.path.basename(full))[0]
            if _norm(base) == _norm(dbname) or _norm(dbname) in _norm(base):
                mdf = full
                break

    if not mdf:
        raise FileNotFoundError(f"MDF de {dbname} no encontrado en DESTINO ({data_path_for_sql})")

    base = os.path.splitext(os.path.basename(mdf))[0]
    ldf = resolve_ldf_for_alias_in_dest(data_path_for_sql, base)
    ok = attach_by_paths(conn, None if tbox_dummy else tbox_dummy, dbname, mdf, ldf)  # safe if None
    return dbname, mdf, ldf

class _Dummy:
    def insert(self, *a, **kw): pass
    def see(self, *a, **kw): pass
    def update_idletasks(self): pass
tbox_dummy = _Dummy()

def attach_catalogs_in_order(conn, dest_path: str, tbox) -> dict:
    results = {"ok": [], "warn": []}
    _log(tbox, "> Adjuntando catálogos ")
    for db in CATALOGS_IN_ORDER:
        if db_exists(conn, db):
            _log(tbox, f"   [{db}] ya existe (adjunta).")
            results["ok"].append(db)
            continue
        try:
            name, mdf, ldf = attach_catalog_by_name(conn, dest_path, db)
            if db_exists(conn, name):
                results["ok"].append(db)
            else:
                results["warn"].append(f"{db}: adjunto no visible")
        except FileNotFoundError as nf:
            _log(tbox, f"   [WARN] {db}: {nf}")
            results["warn"].append(f"{db}: {nf}")
        except Exception as ex:
            _log(tbox, f"   [WARN] {db}: {ex}")
            results["warn"].append(f"{db}: {ex}")
    return results

def ensure_catalog_attached(conn, tbox, dest_path: str, logical_name: str) -> bool:
    if db_exists(conn, logical_name):
        _log(tbox, f"   [{logical_name}] catálogo ya adjunto")
        return True
    for alt in CATALOG_ALT_NAMES.get(logical_name, []):
        if db_exists(conn, alt):
            _log(tbox, f"   [{alt}] catálogo alterno ya adjunto")
            return True

    try:
        files = [f for f in os.listdir(dest_path) if f.lower().endswith(".mdf")]
    except Exception:
        files = []

    cand = None
    targets = [logical_name] + CATALOG_ALT_NAMES.get(logical_name, [])
    for fn in files:
        base = os.path.splitext(fn)[0]
        if any(_norm(base) == _norm(t) or _norm(t) in _norm(base) for t in targets):
            cand = os.path.join(dest_path, fn)
            break
    if not cand:
        _log(tbox, f" No se hallo MDF para {logical_name} en DESTINO")
        return False

    base = os.path.splitext(os.path.basename(cand))[0]
    ldf = resolve_ldf_for_alias_in_dest(dest_path, base)
    return attach_by_paths(conn, tbox, logical_name, cand, ldf)

def _run_query_table(conn, db: str, query: str) -> list[dict]:
    c = conn.cursor()
    c.execute(f"USE [{db}]; {query}")
    cols = [d[0] for d in c.description]
    rows = c.fetchall()
    c.close()
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]

def fetch_aliases_force(conn, tbox) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    contab, nom, comer, addset = set(), set(), set(), set()

    for dbname in ("generalessql", "GeneralesSQL", "GENERALESSQL"):
        try:
            if not db_exists(conn, dbname):
                continue
            rows = _run_query_table(conn, dbname,
                                    "SELECT aliasbdd FROM listaempresas WHERE NULLIF(aliasbdd,'') IS NOT NULL;")
            for r in rows:
                a = (r.get("aliasbdd") or "").strip()
                if a:
                    contab.add(a)
            _log(tbox, f"   (Contabilidad) {dbname}: {len(rows)} alias")
            break
        except Exception as e:
            _log(tbox, f"   (Contabilidad) {dbname} error: {e}")

    for dbname in ("Nomgenerales", "nomGenerales", "nomgenerales"):
        try:
            if not db_exists(conn, dbname):
                continue
            rows = _run_query_table(conn, dbname,
                                    "SELECT rutaempresa FROM nom10000 WHERE NULLIF(rutaempresa,'') IS NOT NULL;")
            for r in rows:
                a = (r.get("rutaempresa") or "").strip()
                if a:
                    nom.add(a)
            _log(tbox, f"   (Nóminas) {dbname}: {len(rows)} alias")
            break
        except Exception as e:
            _log(tbox, f"   (Nóminas) {dbname} error: {e}")

    for dbname in ("CompacwAdmin", "compacwadmin", "COMPACWADMIN"):
        try:
            if not db_exists(conn, dbname):
                continue
            rows = _run_query_table(conn, dbname, r"""
                ;WITH E AS (SELECT crutadatos FROM Empresas WHERE cidempresa<>1)
                SELECT Alias = REVERSE(SUBSTRING(REVERSE(crutadatos),1,CHARINDEX('\',REVERSE(crutadatos))-1))
                FROM E WHERE crutadatos LIKE '%\%';
            """)
            for r in rows:
                a = (r.get("Alias") or "").strip()
                if a:
                    comer.add(a)
            _log(tbox, f"   (Comercial) {dbname}: {len(rows)} alias")
            break
        except Exception as e:
            _log(tbox, f"   (Comercial) {dbname} error: {e}")

    for dbname in ("DB_Directory", "db_directory", "DB_DIRECTORY"):
        try:
            if not db_exists(conn, dbname):
                continue
            rows = _run_query_table(conn, dbname, """
                SELECT DB_DocumentsMetadata,DB_DocumentsContent,DB_OthersMetadata,DB_OthersContent
                FROM DatabaseDirectory;
            """)
            for r in rows:
                for col in ("DB_DocumentsMetadata", "DB_DocumentsContent", "DB_OthersMetadata", "DB_OthersContent"):
                    a = (str(r.get(col) or "")).strip()
                    if a:
                        addset.add(a)
            _log(tbox, f"   (ADD) {dbname}: {len(rows)} filas / {len(addset)} alias únicos")
            break
        except Exception as e:
            _log(tbox, f"   (ADD) {dbname} error: {e}")

    _log(tbox, f"   Aliases CONTAB:{len(contab)}  NOM:{len(nom)}  COMER:{len(comer)}  ADD:{len(addset)}")
    return contab, nom, comer, addset

def attach_aliases_from_dest(conn, dest_path: str, tbox, aliases: Set[str], titulo: str):
    if not aliases:
        _log(tbox, f"   ({titulo}) sin alias para adjuntar.")
        return set(), set()
    _log(tbox, f"   ({titulo}) adjuntando desde DESTINO: {dest_path}")
    ok, fail = set(), set()
    try:
        files = os.listdir(dest_path)
    except Exception:
        files = []
    md_map = [f for f in files if f.lower().endswith(".mdf")]

    for alias in sorted(set(aliases)):
        name = alias.strip()
        if not name:
            continue
        if db_exists(conn, name):
            _log(tbox, f"      [{name}] ya adjunta")
            ok.add(name)
            continue

        mdf = os.path.join(dest_path, f"{name}.mdf")
        if not os.path.exists(mdf):
            for fn in md_map:
                base = os.path.splitext(fn)[0]
                if _norm(base) == _norm(name) or _norm(name) in _norm(base):
                    mdf = os.path.join(dest_path, fn)
                    break
        if not os.path.exists(mdf):
            _log(tbox, f"      [{name}] sin MDF en DESTINO, omito")
            fail.add(name)
            continue

        base = os.path.splitext(os.path.basename(mdf))[0]
        ldf = resolve_ldf_for_alias_in_dest(dest_path, base)
        if attach_by_paths(conn, tbox, name, mdf, ldf):
            ok.add(name)
        else:
            fail.add(name)
    return ok, fail

def attach_orphans_from_dest(conn, tbox, dest_path: str):
    try:
        files = [f for f in os.listdir(dest_path) if f.lower().endswith(".mdf")]
    except Exception:
        _log(tbox, "   Opcion 2 No pude listar DESTINO.")
        return
    _log(tbox, f"   Opcion 2 Buscando huérfanas en DESTINO…")
    for fn in sorted(files, key=lambda x: x.lower()):
        base = os.path.splitext(fn)[0]
        if base in EXCLUDE_DB_NAMES:
            continue
        if db_exists(conn, base):
            continue
        mdf = os.path.join(dest_path, fn)
        ldf = resolve_ldf_for_alias_in_dest(dest_path, base)
        attach_by_paths(conn, tbox, base, mdf, ldf)

def server_compat_target(conn) -> int:
    c = conn.cursor()
    c.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') as varchar(50));")
    v = c.fetchone()[0]
    c.close()
    major = int(str(v).split(".")[0])
    return 160 if major >= 16 else (150 if major == 15 else 140)

def post_update_all(conn, target_level: int):
    sql = f"""
    DECLARE @lvl int={target_level};
    DECLARE @sql nvarchar(max)=N'';
    SELECT @sql = STRING_AGG(CONVERT(nvarchar(max),
        'IF DB_ID('''+name+''')>4 BEGIN ' +
        'ALTER DATABASE ['+name+'] SET COMPATIBILITY_LEVEL='+CAST(@lvl as varchar(10))+'; ' +
        'BEGIN TRY ALTER AUTHORIZATION ON DATABASE::['+name+'] TO sa; END TRY BEGIN CATCH END CATCH; ' +
        'ALTER DATABASE ['+name+'] SET AUTO_CLOSE OFF; ' +
        'ALTER DATABASE ['+name+'] SET AUTO_SHRINK OFF; ' +
        'ALTER DATABASE ['+name+'] SET PAGE_VERIFY CHECKSUM; ' +
        'END'
    ), ' ')
    FROM sys.databases WHERE database_id>4;
    EXEC (@sql);
    """
    c = conn.cursor()
    c.execute(sql)
    c.close()

def quick_check(conn, tbox):
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sys.databases WHERE database_id>4 ORDER BY name;")
        names = [r[0] for r in c.fetchall()]
        c.close()
        for n in names:
            try:
                c = conn.cursor()
                c.execute(f"DBCC CHECKDB([{n}]) WITH NO_INFOMSGS, PHYSICAL_ONLY;")
                c.close()
                _log(tbox, f"   CHECKDB OK: {n}")
            except Exception as e:
                _log(tbox, f"   CHECKDB ERROR {n}: {e}")
    except Exception as e:
        _log(tbox, f" No pude listar DBs para CHECKDB: {e}")


def _first_existing(*paths):
    for p in paths:
        if p and isinstance(p, str) and os.path.exists(p):
            return p
    return None

def force_refresh_nom_generales(conn, tbox, data_src: str, data_dst: str,
                                logicals=("nomGenerales", "Nomgenerales", "nomgenerales")) -> bool:

    name_present = None
    for n in logicals:
        try:
            if db_exists(conn, n):
                name_present = n
                break
        except Exception:
            pass
    name = name_present or logicals[0]

    try:
        if db_exists(conn, name):
            _log(tbox, f"[Nóminas] Preparando DETACH de [{name}] …")
            c = conn.cursor()
            c.execute(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;")
            c.execute("EXEC master.dbo.sp_detach_db @dbname=?", name)
            c.close()
            _log(tbox, f"[Nóminas] [{name}] des-adjuntada.")
            time.sleep(0.4)
    except Exception as e:
        _log(tbox, f"[Nóminas] Aviso en DETACH: {e}")

    try:
        os.makedirs(data_dst, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        qdir = os.path.join(data_dst, f"_quarantine_nom_{stamp}")
        os.makedirs(qdir, exist_ok=True)

        def _is_nom_file(fn: str) -> bool:
            b = os.path.splitext(os.path.basename(fn))[0].lower()
            return ("nomgenerales" in b)

        for fn in os.listdir(data_dst):
            full = os.path.join(data_dst, fn)
            if os.path.isfile(full) and (fn.lower().endswith((".mdf", ".ldf")) and _is_nom_file(fn)):
                shutil.move(full, os.path.join(qdir, fn))
                _log(tbox, f"[Nóminas] Movido a cuarentena: {fn}")
    except Exception as e:
        _log(tbox, f"[Nóminas] Aviso en quarantine: {e}")

    try:
        src_mdf = _first_existing(
            os.path.join(data_src, "nomGenerales.mdf"),
            os.path.join(data_src, "Nomgenerales.mdf"),
            _first_existing(*[
                os.path.join(data_src, f) for f in os.listdir(data_src)
                if f.lower().endswith(".mdf") and "nomgenerales" in f.lower()
            ])
        )
        src_ldf = _first_existing(
            os.path.join(data_src, "nomGenerales_log.ldf"),
            os.path.join(data_src, "Nomgenerales_log.ldf"),
            _first_existing(*[
                os.path.join(data_src, f) for f in os.listdir(data_src)
                if f.lower().endswith(".ldf") and "nomgenerales" in f.lower()
            ])
        )
    except Exception:
        src_mdf, src_ldf = None, None

    if not src_mdf:
        _log(tbox, "[Nóminas] ERROR: No encontré MDF de nomGenerales en ORIGEN.")
        return False

    dst_mdf = os.path.join(data_dst, os.path.basename(src_mdf))
    shutil.copy2(src_mdf, dst_mdf)
    _log(tbox, f"[Nóminas] Copiado MDF  {os.path.basename(dst_mdf)}")

    dst_ldf = None
    if src_ldf:
        dst_ldf = os.path.join(data_dst, os.path.basename(src_ldf))
        shutil.copy2(src_ldf, dst_ldf)
        _log(tbox, f"[Nóminas] Copiado LDF  {os.path.basename(dst_ldf)}")
    else:
        _log(tbox, "[Nóminas] No hay LDF en ORIGEN, se reconstruirá (REBUILD_LOG).")

    ok = attach_by_paths(conn, tbox, name, dst_mdf, dst_ldf)
    if ok:
        _log(tbox, f"[Nóminas] Adjuntada OK: [{name}]")
    else:
        _log(tbox, f"[Nóminas] No se pudo adjuntar [{name}] (revisa archivos).")
    return ok
