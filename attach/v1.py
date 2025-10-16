import os, shutil, tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyodbc

APP_TITLE = "Migracion CONTPAQi"
DEFAULT_INSTANCE = r"localhost\COMPAC"

# Control global: lectura de ERRORLOG en fallos (se ajusta desde el checkbox del GUI)
READ_ERRORLOG_ON_FAIL = True

CATALOGS_IN_ORDER = [
    "DB_Directory",
    "predeterminada",
    "generalessql",
    "CompacwAdmin",
    "repositorioadminpaq",
    "Nomgenerales",
]

CATALOG_ALT_NAMES = {
    "DB_Directory": ["db_directory","DB_DIRECTORY"],
    "predeterminada": [],
    "generalessql": ["GeneralesSQL","GENERALESSQL"],
    "CompacwAdmin": ["compacwadmin","COMPACWADMIN"],
    "repositorioadminpaq": [],
    "Nomgenerales": ["nomgenerales","NOMGENERALES"],
}

EXCLUDE_DB_NAMES = set([
    "master","model","msdb","tempdb",
    "DB_Directory","db_directory","DB_DIRECTORY",
    "predeterminada",
    "generalessql","GeneralesSQL","GENERALESSQL",
    "CompacwAdmin","compacwadmin","COMPACWADMIN",
    "repositorioadminpaq",
    "Nomgenerales","nomgenerales","NOMGENERALES",
])

def norm(s:str)->str: return (s or "").lower().replace("_","").replace("-","").replace(" ","")
def log(t:tk.Text, msg:str): t.insert("end", msg+"\n"); t.see("end"); t.update_idletasks()
def choose_folder(var, title="Selecciona carpeta"):
    p = filedialog.askdirectory(title=title)
    if p:
        if not p.endswith("\\"): p += "\\"
        var.set(p)

def get_driver():
    ds = [d for d in pyodbc.drivers() if "ODBC Driver" in d and "SQL Server" in d]
    if any("ODBC Driver 18" in d for d in ds): return "{ODBC Driver 18 for SQL Server}"
    if any("ODBC Driver 17" in d for d in ds): return "{ODBC Driver 17 for SQL Server}"
    return "{SQL Server}"

def connect_instance(server, sql_auth=False, uid="", pwd=""):
    d = get_driver()
    if sql_auth:
        enc = "yes" if "18" in d else "no"
        extra = "TrustServerCertificate=yes;" if "18" in d else ""
        cs = f"DRIVER={d};SERVER={server};UID={uid};PWD={pwd};Encrypt={enc};{extra}"
    else:
        cs = f"DRIVER={d};SERVER={server};Trusted_Connection=yes;Encrypt=no"
    return pyodbc.connect(cs, timeout=8, autocommit=True)

def detect_data_path(cnx)->str:
    sql = r"""
    DECLARE @p nvarchar(4000);
    IF TRY_CONVERT(int,PARSENAME(CONVERT(varchar(50),SERVERPROPERTY('ProductVersion')),4))>=13
        SELECT @p = CAST(SERVERPROPERTY('InstanceDefaultDataPath') as nvarchar(4000));
    IF @p IS NULL
    BEGIN
        DECLARE @r nvarchar(4000)='';
        EXEC master.dbo.xp_instance_regread 
             N'HKEY_LOCAL_MACHINE',N'Software\Microsoft\MSSQLServer\MSSQLServer',N'DefaultData', @r OUTPUT,'no_output';
        SELECT @p = NULLIF(@r,'');
    END
    SELECT @p;
    """
    c = cnx.cursor(); c.execute(sql); row = c.fetchone(); c.close()
    if not row or not row[0]: raise RuntimeError("No pude determinar la carpeta DATA de la instancia.")
    p = row[0];  return p if p.endswith("\\") else p+"\\"

def server_compat_target(cnx)->int:
    c=cnx.cursor(); c.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') as varchar(50));"); v=c.fetchone()[0]; c.close()
    major = int(str(v).split(".")[0])
    return 160 if major>=16 else (150 if major==15 else 140)

def db_exists(cnx, name)->bool:
    c=cnx.cursor(); c.execute("SELECT DB_ID(?)", name); r=c.fetchone(); c.close()
    return bool(r and r[0] is not None)

def walk_collect(root):
    mdfs,ldfs,ndfs=set(),set(),set()
    for r,_,files in os.walk(root):
        for fn in files:
            full = os.path.join(r,fn)
            l = full.lower()
            if l.endswith(".mdf"): mdfs.add(full)
            elif l.endswith(".ldf"): ldfs.add(full)
            elif l.endswith(".ndf"): ndfs.add(full)
    return mdfs,ldfs,ndfs

def list_files_in_data_via_sql(cnx, data_path):
    # Mejora de rendimiento: si la ruta es local y accesible, usa os.walk directamente
    folder = data_path.rstrip("\\/")
    if os.path.exists(folder):
        mdfs,ldfs,_ = walk_collect(folder)
        return mdfs, ldfs

    # Fallback: intentar xp_dirtree solo si la ruta no es accesible desde el proceso Python
    mdfs,ldfs=set(),set()
    sql=f"""
    DECLARE @p nvarchar(4000)=N'{folder}';
    CREATE TABLE #t(name nvarchar(4000), depth int, isfile bit);
    BEGIN TRY
        INSERT #t EXEC master..xp_dirtree @p, 5, 1;
        SELECT name FROM #t WHERE isfile=1;
    END TRY BEGIN CATCH SELECT CAST(NULL as nvarchar(4000)) WHERE 1=0; END CATCH
    DROP TABLE #t;
    """
    try:
        c=cnx.cursor(); c.execute(sql); rows=c.fetchall(); c.close()
        if rows:
            for (name,) in rows:
                if not name: continue
                rel = str(name).replace("/","\\")
                full = os.path.join(folder, rel)
                l = full.lower()
                if l.endswith(".mdf"): mdfs.add(full)
                elif l.endswith(".ldf"): ldfs.add(full)
        else:
            raise Exception()
    except Exception:
        # último intento
        mdfs,ldfs,_ = walk_collect(folder)
    return mdfs,ldfs

def resolve_ldf_for_alias_in_dest(dest_path, alias)->str|None:
    trials=[f"mastlog.ldf{alias}.ldf", f"{alias}_log.ldf", f"{alias}.ldf"]
    for t in trials:
        cand=os.path.join(dest_path, t)
        if os.path.exists(cand): return cand
    try:
        for fn in os.listdir(dest_path):
            l=fn.lower()
            if l.endswith(".ldf") and (alias.lower() in l):
                return os.path.join(dest_path, fn)
    except Exception: pass
    return None

def preflight_path(cnx,tbox, mdf, ldf):
    ok=True
    for p in [mdf]+([ldf] if ldf else []):
        if not p: continue
        if not os.path.exists(p):
            log(tbox,f" No existe en disco: {p}"); ok=False; continue
        try:
            mode=os.stat(p).st_mode
            if mode & 0o222 == 0:
                os.chmod(p,0o666); log(tbox,f" Quité solo-lectura: {os.path.basename(p)}")
        except Exception as e:
            log(tbox,f" No pude ajustar permisos: {e}")
        try:
            c=cnx.cursor(); c.execute("EXEC master..xp_fileexist ?", p); row=c.fetchone(); c.close()
            if not (row and row[0]==1):
                log(tbox,f"      (X) SQL Server NO ve: {p}"); ok=False
            else:
                log(tbox,f"      (✓) SQL Server ve: {os.path.basename(p)}")
        except Exception:
            pass
    return ok

def attach_by_paths(cnx,tbox, name, mdf, ldf):
    log(tbox,f"      Prechequeo archivos para [{name}] …")
    if not preflight_path(cnx,tbox, mdf, ldf):
        log(tbox,f"   [{name}] pre-chequeo falló  omito attach"); return False
    mdf_sql=mdf.replace("/", "\\")
    if ldf:
        ldf_sql=ldf.replace("/", "\\")
        sql=f"CREATE DATABASE [{name}] ON (FILENAME=N'{mdf_sql}'), (FILENAME=N'{ldf_sql}') FOR ATTACH;"
    else:
        sql=f"CREATE DATABASE [{name}] ON (FILENAME=N'{mdf_sql}') FOR ATTACH_REBUILD_LOG;"
    try:
        c=cnx.cursor(); c.execute(sql); c.close()
        log(tbox,f"   [{name}] adjuntada OK ({os.path.basename(mdf_sql)})"); return True
    except Exception as e:
        log(tbox,f"   [{name}] ERROR: {e}")
        if READ_ERRORLOG_ON_FAIL:
            try:
                c=cnx.cursor()
                c.execute("EXEC master.dbo.xp_readerrorlog 0,1,N'Error',NULL,NULL,NULL,N'desc';")
                rows=c.fetchall(); c.close()
                shown=0; log(tbox,"      --- ERRORLOG reciente (resumen) ---")
                for r in rows:
                    line=" ".join(str(x) for x in r if x is not None)
                    if any(k in line for k in ("5120","5105","Access is denied","Operating system error")):
                        log(tbox,"      "+line); shown+=1
                    if shown>=20: break
                if shown==0: log(tbox,"      (sin entradas relevantes en ERRORLOG)")
            except Exception as e2:
                log(tbox,f"      (no pude leer ERRORLOG: {e2})")
        return False

def auto_copy_all_data(origin, dest, tbox:tk.Text):
    log(tbox, "[0/3] Copiando DATA ")
    mdfs,ldfs,ndfs = walk_collect(origin)
    total = len(mdfs)+len(ldfs)+len(ndfs)
    log(tbox, f"   Encontrados en ORIGEN: {len(mdfs)} MDF, {len(ldfs)} LDF, {len(ndfs)} NDF (total {total})")
    os.makedirs(dest, exist_ok=True)
    copied = skipped = errors = 0

    def _copy_one(src):
        nonlocal copied, skipped, errors
        dst = os.path.join(dest, os.path.basename(src))
        if os.path.exists(dst):
            skipped += 1
            return f"      ya existe, no se copia: {os.path.basename(dst)}"
        try:
            shutil.copy2(src, dst)
            copied += 1
            return f"      copiado: {os.path.basename(src)}"
        except Exception as e:
            errors += 1
            return f"      ERROR  {os.path.basename(src)}: {e}"

    for group, lbl in ((mdfs,"MDF"), (ldfs,"LDF"), (ndfs,"NDF")):
        if not group: continue
        log(tbox, f"   Copiando {lbl}…")
        for src in sorted(group, key=lambda p:p.lower()):
            log(tbox, _copy_one(src))
    log(tbox, f"   Resumen copia: copiados={copied}, omitidos={skipped}, errores={errors}")

def attach_catalogs_in_order(cnx, dest_path, tbox):
    mdfs,ldfs = list_files_in_data_via_sql(cnx, dest_path)
    log(tbox,"[1/3] Adjuntando catálogos")
    for name in CATALOGS_IN_ORDER:
        if db_exists(cnx, name):
            log(tbox,f"   [{name}] ya adjunta"); continue
        mdf=None
        for full in mdfs:
            if os.path.basename(full).lower()==f"{name.lower()}.mdf":
                mdf=full; break

        if not mdf:
            cand=os.path.join(dest_path, f"{name}.mdf")
            if os.path.exists(cand): mdf=cand
        if not mdf:
            for alt in CATALOG_ALT_NAMES.get(name,[]):
                cand=os.path.join(dest_path, f"{alt}.mdf")
                if os.path.exists(cand): mdf=cand; break
        if not mdf:
            log(tbox,f"   [{name}] no se encontro MDF en DESTINO, omitida"); continue

        base = os.path.splitext(os.path.basename(mdf))[0]
        ldf = resolve_ldf_for_alias_in_dest(dest_path, base)
        if not ldf:
            ldf = resolve_ldf_for_alias_in_dest(os.path.dirname(mdf), base)
        attach_by_paths(cnx,tbox, name, mdf, ldf)

def ensure_catalog_attached(cnx, tbox, dest_path, logical_name:str):
    if db_exists(cnx, logical_name):
        log(tbox, f"   [{logical_name}] catálogo ya adjunto"); return True
    for alt in CATALOG_ALT_NAMES.get(logical_name,[]):
        if db_exists(cnx, alt):
            log(tbox, f"   [{alt}] catálogo alterno ya adjunto "); return True
    try: files=[f for f in os.listdir(dest_path) if f.lower().endswith(".mdf")]
    except Exception: files=[]
    target_names = [logical_name] + CATALOG_ALT_NAMES.get(logical_name,[])
    cand=None
    for fn in files:
        base=os.path.splitext(fn)[0]
        if any(norm(base)==norm(t) or norm(t) in norm(base) for t in target_names):
            cand=os.path.join(dest_path, fn); break
    if not cand:
        log(tbox, f"   (Aviso) No hallé MDF para catálogo {logical_name} en DESTINO "); return False
    base=os.path.splitext(os.path.basename(cand))[0]
    ldf = resolve_ldf_for_alias_in_dest(dest_path, base)
    ok = attach_by_paths(cnx, tbox, logical_name, cand, ldf)
    return ok

def run_query_table(cnx, db, query, tbox):
    c=cnx.cursor(); c.execute(f"USE [{db}]; {query}")
    cols=[d[0] for d in c.description]; rows=c.fetchall(); c.close()
    return [{cols[i]:r[i] for i in range(len(cols))} for r in rows]

def fetch_aliases_force(cnx, tbox):
    contab, nom, comer, addset = set(), set(), set(), set()

    tried = ("generalessql","GeneralesSQL","GENERALESSQL")
    for dbname in tried:
        try:
            if not db_exists(cnx, dbname): 
                continue
            rows=run_query_table(cnx, dbname, "SELECT aliasbdd FROM listaempresas WHERE NULLIF(aliasbdd,'') IS NOT NULL;", tbox)
            for r in rows:
                a=(r.get("aliasbdd") or "").strip()
                if a: contab.add(a)
            log(tbox, f"   (Contabilidad) {dbname}: {len(rows)} alias")
            break
        except Exception as e:
            log(tbox, f"   (Contabilidad) {dbname} error: {e}")

    tried = ("Nomgenerales","nomgenerales","NOMGENERALES")
    for dbname in tried:
        try:
            if not db_exists(cnx, dbname):
                continue
            rows=run_query_table(cnx, dbname, "SELECT rutaempresa FROM nom10000 WHERE NULLIF(rutaempresa,'') IS NOT NULL;", tbox)
            for r in rows:
                a=(r.get("rutaempresa") or "").strip()
                if a: nom.add(a)
            log(tbox, f"   (Nóminas) {dbname}: {len(rows)} alias")
            break
        except Exception as e:
            log(tbox, f"   (Nóminas) {dbname} error: {e}")

    tried = ("CompacwAdmin","compacwadmin","COMPACWADMIN")
    for dbname in tried:
        try:
            if not db_exists(cnx, dbname): 
                continue
            rows=run_query_table(cnx, dbname, r"""
            ;WITH E AS (SELECT crutadatos FROM Empresas WHERE cidempresa<>1)
            SELECT Alias = REVERSE(SUBSTRING(REVERSE(crutadatos),1,CHARINDEX('\',REVERSE(crutadatos))-1))
            FROM E WHERE crutadatos LIKE '%\%';
            """, tbox)
            for r in rows:
                a=(r.get("Alias") or "").strip()
                if a: comer.add(a)
            log(tbox, f"   (Comercial) {dbname}: {len(rows)} alias")
            break
        except Exception as e:
            log(tbox, f"   (Comercial) {dbname} error: {e}")

    tried = ("DB_Directory","db_directory","DB_DIRECTORY")
    for dbname in tried:
        try:
            if not db_exists(cnx, dbname): 
                continue
            rows=run_query_table(cnx, dbname, """
                SELECT DB_DocumentsMetadata,DB_DocumentsContent,DB_OthersMetadata,DB_OthersContent
                FROM DatabaseDirectory;
            """, tbox)
            for r in rows:
                for col in ("DB_DocumentsMetadata","DB_DocumentsContent","DB_OthersMetadata","DB_OthersContent"):
                    a=(str(r.get(col) or "")).strip()
                    if a: addset.add(a)
            log(tbox, f"   (ADD) {dbname}: {len(rows)} filas / {len(addset)} alias únicos")
            break
        except Exception as e:
            log(tbox, f"   (ADD) {dbname} error: {e}")

    log(tbox, f"   Aliases CONTAB:{len(contab)}  NOM:{len(nom)}  COMER:{len(comer)}  ADD:{len(addset)}")
    return contab, nom, comer, addset

def attach_aliases_from_dest(cnx, dest_path, tbox, aliases:set, titulo:str):
    if not aliases: 
        log(tbox, f"   ({titulo}) sin alias para adjuntar."); 
        return set(), set()
    log(tbox, f"   ({titulo}) adjuntando desde DESTINO: {dest_path}")
    ok=set(); fail=set()
    try: files=os.listdir(dest_path)
    except Exception: files=[]
    md_map=[f for f in files if f.lower().endswith(".mdf")]

    for alias in sorted(set(aliases)):
        name=alias.strip()
        if not name: continue
        if db_exists(cnx, name):
            log(tbox,f"      [{name}] ya adjunta"); ok.add(name); continue

        mdf=os.path.join(dest_path, f"{name}.mdf")
        if not os.path.exists(mdf):
            for fn in md_map:
                base=os.path.splitext(fn)[0]
                if norm(base)==norm(name) or norm(name) in norm(base):
                    mdf=os.path.join(dest_path, fn); break
        if not os.path.exists(mdf):
            log(tbox, f"      [{name}] sin MDF en DESTINO, omito"); fail.add(name); continue
        ldf = resolve_ldf_for_alias_in_dest(dest_path, os.path.splitext(os.path.basename(mdf))[0])
        if attach_by_paths(cnx,tbox, name, mdf, ldf): ok.add(name)
        else: fail.add(name)
    return ok, fail

def attach_orphans_from_dest(cnx, tbox, dest_path):
    try:
        files = [f for f in os.listdir(dest_path) if f.lower().endswith(".mdf")]
    except Exception:
        log(tbox, "   (Plan B) No pude listar DESTINO."); return
    log(tbox, f"   (Plan B) Buscando orfanas en DESTINO…")
    for fn in sorted(files, key=lambda x:x.lower()):
        base = os.path.splitext(fn)[0]
        if base in EXCLUDE_DB_NAMES:
            continue
        if db_exists(cnx, base):
            continue
        mdf = os.path.join(dest_path, fn)
        ldf = resolve_ldf_for_alias_in_dest(dest_path, base)
        attach_by_paths(cnx, tbox, base, mdf, ldf)

def post_update_all(cnx, target_level:int):
    sql=f"""
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
    c=cnx.cursor(); c.execute(sql); c.close()

def quick_check(cnx, tbox):
    try:
        c=cnx.cursor(); c.execute("SELECT name FROM sys.databases WHERE database_id>4 ORDER BY name;")
        names=[r[0] for r in c.fetchall()]; c.close()
        for n in names:
            try:
                c=cnx.cursor(); c.execute(f"DBCC CHECKDB([{n}]) WITH NO_INFOMSGS, PHYSICAL_ONLY;"); c.close()
                log(tbox,f"   CHECKDB OK: {n}")
            except Exception as e:
                log(tbox,f"   CHECKDB ERROR {n}: {e}")
    except Exception as e:
        log(tbox,f"(Aviso) No pude listar DBs para CHECKDB: {e}")

def verify_report(cnx, tbox):
    c=cnx.cursor(); c.execute("SELECT CAST(SERVERPROPERTY('ProductMajorVersion') as int), CAST(SERVERPROPERTY('ProductVersion') as varchar(50));")
    major, ver = c.fetchone(); c.close()
    target = 160 if major>=16 else (150 if major==15 else 140)
    label = "SQL Server 2022" if target==160 else ("SQL Server 2019" if target==150 else f"SQL {major}")

    c=cnx.cursor()
    c.execute("""
      SELECT name, state_desc, compatibility_level,
             suser_sname(owner_sid) AS owner, page_verify_option_desc,
             is_auto_close_on, is_auto_shrink_on
      FROM sys.databases WHERE database_id>4 ORDER BY name;
    """)
    rows=c.fetchall(); c.close()

    log(tbox,f"Servidor: {label} (ProductVersion={ver}) | Target compatibility={target}")
    ok=True
    for (name,state_desc,lvl,owner,pv,ac,ash) in rows:
        issues=[]
        if state_desc!="ONLINE": issues.append(f"state={state_desc}")
        if lvl!=target: issues.append(f"compat={lvl} (target {target})")
        if (owner or "").lower()!="sa": issues.append(f"owner={owner}")
        if pv!="CHECKSUM": issues.append(f"page_verify={pv}")
        if ac!=0: issues.append("AUTO_CLOSE=ON")
        if ash!=0: issues.append("AUTO_SHRINK=ON")
        if issues: ok=False; log(tbox,f"[{name}] "+", ".join(issues))
        else: log(tbox,f"[{name}] OK")
    if ok:
        msg = "Conversión OK a SQL Server 2022 (compat=160)" if target==160 else \
              "Conversión OK a SQL Server 2019 (compat=150)" if target==150 else \
              f"Conversión OK (compat={target})"
        log(tbox,msg); messagebox.showinfo(APP_TITLE, msg)
    else:
        log(tbox,"Hay bases con pendientes. Revisa detalles arriba.")
        messagebox.showwarning(APP_TITLE,"Hay bases con pendientes (ver log).")

def test_connection(instance_var, use_sql_auth_var, uid_var, pwd_var, datapath_var, tbox):
    try:
        inst=instance_var.get().strip() or DEFAULT_INSTANCE
        use_sql = bool(use_sql_auth_var.get()==1)
        uid = uid_var.get().strip() if use_sql else ""
        pwd = pwd_var.get() if use_sql else ""
        cnx = connect_instance(inst, sql_auth=use_sql, uid=uid, pwd=pwd)
        log(tbox, f"Conexión OK a {inst} ({'SQL Auth' if use_sql else 'Windows Auth'})")
        if not datapath_var.get().strip():
            dp = detect_data_path(cnx); datapath_var.set(dp); log(tbox,f"DATA detectada: {dp}")
        messagebox.showinfo(APP_TITLE,"Conexión exitosa.")
    except Exception as e:
        messagebox.showerror(APP_TITLE, f"Error de conexión: {e}"); log(tbox,f"ERROR de conexión: {e}")

def action_run(instance_var, origin_var, datapath_var, autocopy_var, check_var, verify_var,
               use_sql_auth_var, uid_var, pwd_var, skip_errorlog_var, tbox, btn):
    global READ_ERRORLOG_ON_FAIL
    READ_ERRORLOG_ON_FAIL = (skip_errorlog_var.get() == 0)  # si el checkbox está marcado, no leer errorlog

    btn.config(state="disabled")
    try:
        inst=instance_var.get().strip() or DEFAULT_INSTANCE
        use_sql=bool(use_sql_auth_var.get()==1)
        uid = uid_var.get().strip() if use_sql else ""
        pwd = pwd_var.get() if use_sql else ""
        cnx = connect_instance(inst, sql_auth=use_sql, uid=uid, pwd=pwd)
        log(tbox, f"Conectado a {inst} ({'SQL Auth' if use_sql else 'Windows Auth'})")

        dest = datapath_var.get().strip() or detect_data_path(cnx)
        if not dest.endswith("\\"): dest += "\\"
        datapath_var.set(dest)
        log(tbox, f"DATA DESTINO: {dest}")

        origin = origin_var.get().strip()
        if autocopy_var.get()==1 and origin:
            if not origin.endswith("\\"): origin += "\\"; origin_var.set(origin)
            if os.path.exists(origin): auto_copy_all_data(origin, dest, tbox)
            else: log(tbox, f"(Aviso) ORIGEN no existe: {origin}, omito copias")
        elif autocopy_var.get()==1 and not origin:
            log(tbox, "(Aviso) No se indicó ORIGEN")

        attach_catalogs_in_order(cnx, dest, tbox)

        for cat in ("generalessql","Nomgenerales","DB_Directory","CompacwAdmin"):
            ensure_catalog_attached(cnx, tbox, dest, cat)

        log(tbox, "[2/3] Queries")
        contab, nom, comer, addset = fetch_aliases_force(cnx, tbox)

        ok_c, fail_c = attach_aliases_from_dest(cnx, dest, tbox, contab, "CONTABILIDAD")
        ok_n, fail_n = attach_aliases_from_dest(cnx, dest, tbox, nom,    "NÓMINAS")
        ok_m, fail_m = attach_aliases_from_dest(cnx, dest, tbox, comer,  "COMERCIAL")
        ok_a, fail_a = attach_aliases_from_dest(cnx, dest, tbox, addset, "ADJUNTAR MASIVO ADD")

        if not contab: log(tbox, "   (Plan B Contab) Sin alias  adjunto orfanas…"); attach_orphans_from_dest(cnx, tbox, dest)
        if not nom:    log(tbox, "   (Plan B Nóminas) Sin alias  adjunto orfanas…"); attach_orphans_from_dest(cnx, tbox, dest)
        if not comer:  log(tbox, "   (Plan B Comercial) Sin alias  adjunto orfanas…"); attach_orphans_from_dest(cnx, tbox, dest)
        if not addset: log(tbox, "   (Plan B ADD) Sin alias  adjunto orfanas…"); attach_orphans_from_dest(cnx, tbox, dest)

        log(tbox, "[3/3] Migracion")
        target = server_compat_target(cnx)
        post_update_all(cnx, target)

        if verify_var.get()==1: verify_report(cnx, tbox)
        if check_var.get()==1:
            log(tbox,"CHECKDB")
            quick_check(cnx, tbox)

        expected = set().union(contab, nom, comer, addset)
        final_missing = [a for a in expected if not db_exists(cnx, a)]
        log(tbox, "----- Resumen de empresas/ADD -----")
        log(tbox, f"Adjuntadas OK: {len((ok_c|ok_n|ok_m|ok_a))}")
        if final_missing:
            log(tbox, f"Faltantes: {len(final_missing)}")
            for a in final_missing: log(tbox, f"   - {a}")
            messagebox.showwarning(APP_TITLE, f"Quedaron {len(final_missing)} alias sin adjuntar (ver log).")
        else:
            log(tbox, "Queries ejecutados y alias adjuntos.")
            messagebox.showinfo(APP_TITLE,"Proceso completado (queries ejecutados y alias adjuntos).")

    except Exception as e:
        messagebox.showerror(APP_TITLE, f"Error: {e}"); log(tbox,f"ERROR: {e}")
    finally:
        btn.config(state="normal")

# -------------- GUI --------------
def main():
    root=tk.Tk(); root.title(APP_TITLE); root.geometry("1040x820"); root.minsize(1000,760)
    frm=ttk.Frame(root,padding=10); frm.pack(fill="both", expand=True)

    instance_var=tk.StringVar(value=DEFAULT_INSTANCE)
    origin_var  =tk.StringVar(value="")
    datapath_var=tk.StringVar(value="")
    autocopy_var=tk.IntVar(value=1)
    check_var   =tk.IntVar(value=0)
    verify_var  =tk.IntVar(value=1)
    skip_errorlog_var = tk.IntVar(value=1)  # 1 = no leer ERRORLOG en fallos (recomendado para rendimiento)

    use_sql_auth_var=tk.IntVar(value=0)
    uid_var=tk.StringVar(value="")
    pwd_var=tk.StringVar(value="")

    lf1=ttk.LabelFrame(frm, text="Parámetros de conexión"); lf1.pack(fill="x", padx=4, pady=4)
    ttk.Label(lf1,text="Instancia SQL:").grid(row=0,column=0,sticky="w",padx=6,pady=6)
    ttk.Entry(lf1,textvariable=instance_var,width=40).grid(row=0,column=1,sticky="w")
    ttk.Checkbutton(lf1,text="Usar SQL Authentication (Usuario/Contraseña)",variable=use_sql_auth_var).grid(row=0,column=2,padx=6,pady=6)
    ttk.Label(lf1,text="Usuario:").grid(row=1,column=0,sticky="w",padx=6)
    user_entry=ttk.Entry(lf1,textvariable=uid_var,width=32,state="disabled"); user_entry.grid(row=1,column=1,sticky="w")
    ttk.Label(lf1,text="Contraseña:").grid(row=1,column=2,sticky="e",padx=6)
    pass_entry=ttk.Entry(lf1,textvariable=pwd_var,width=32,show="*",state="disabled"); pass_entry.grid(row=1,column=3,sticky="w")
    def _toggle(*_):
        st="normal" if use_sql_auth_var.get()==1 else "disabled"
        user_entry.configure(state=st); pass_entry.configure(state=st)
    use_sql_auth_var.trace_add("write", _toggle)

    lf2=ttk.LabelFrame(frm, text="Carpetas de datos y opciones"); lf2.pack(fill="x", padx=4, pady=4)
    ttk.Label(lf2,text="Carpeta DATA ORIGEN (vieja):").grid(row=0,column=0,sticky="w",padx=6,pady=6)
    ttk.Entry(lf2,textvariable=origin_var,width=60).grid(row=0,column=1,sticky="we")
    ttk.Button(lf2,text="Elegir…",command=lambda: choose_folder(origin_var,"Selecciona carpeta DATA ORIGEN")).grid(row=0,column=2,padx=6)

    ttk.Label(lf2,text="Carpeta DATA DESTINO (instancia):").grid(row=1,column=0,sticky="w",padx=6,pady=6)
    ttk.Entry(lf2,textvariable=datapath_var,width=60).grid(row=1,column=1,sticky="we")
    ttk.Button(lf2,text="Elegir…",command=lambda: choose_folder(datapath_var,"Selecciona carpeta DATA DESTINO")).grid(row=1,column=2,padx=6)

    ttk.Checkbutton(lf2,text="Copiar TODO (*.mdf/*.ldf/*.ndf) desde ORIGEN (sin sobrescribir)",variable=autocopy_var).grid(row=0,column=3,padx=6)
    ttk.Checkbutton(lf2,text="CHECKDB ",variable=check_var).grid(row=1,column=3,padx=6)
    ttk.Checkbutton(lf2,text="Verificar conversión al finalizar",variable=verify_var).grid(row=1,column=4,padx=6)
    ttk.Checkbutton(lf2,text="No leer ERRORLOG en fallos de attach (más rápido)",variable=skip_errorlog_var).grid(row=0,column=4,padx=6)

    for i in range(6): lf2.grid_columnconfigure(i,weight=0)
    lf2.grid_columnconfigure(1,weight=1)

    btns=ttk.Frame(frm); btns.pack(fill="x", pady=6)
    btn_test=ttk.Button(btns,text="Probar conexión",
        command=lambda: test_connection(instance_var, use_sql_auth_var, uid_var, pwd_var, datapath_var, tbox))
    btn_test.pack(side="left", padx=4)

    btn_run=ttk.Button(btns,text="Adjuntar + Convertir (forzando queries)",
        command=lambda: action_run(instance_var, origin_var, datapath_var, autocopy_var,
                                   check_var, verify_var, use_sql_auth_var, uid_var, pwd_var,
                                   skip_errorlog_var, tbox, btn_run))
    btn_run.pack(side="left", padx=4)

    lf3=ttk.LabelFrame(frm,text="Log"); lf3.pack(fill="both", expand=True, padx=4, pady=4)
    global tbox
    tbox=tk.Text(lf3,height=28,wrap="word"); tbox.pack(fill="both", expand=True, padx=6, pady=6)
    tbox.configure(font=("Consolas",10))

    status=ttk.Label(root,text="Listo.",anchor="w"); status.pack(fill="x")
    root.mainloop()

if __name__=="__main__":
    main()
