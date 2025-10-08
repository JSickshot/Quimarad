# core/sql.py
import pyodbc

_ODBC_CANDIDATES = [
    "{ODBC Driver 18 for SQL Server}",
    "{ODBC Driver 17 for SQL Server}",
]

def first_available_driver() -> str:
    drivers = [d.strip() for d in pyodbc.drivers()]
    for cand in _ODBC_CANDIDATES:
        if any(cand.split('{')[1].split('}')[0] in d for d in drivers):
            return cand
    return "{" + drivers[-1] + "}" if drivers else "{ODBC Driver 17 for SQL Server}"

_DEF_DRIVER = first_available_driver()

def sql_conn(instance: str, *, trusted: bool, user: str = "", password: str = "", autocommit: bool = True) -> pyodbc.Connection:
    if trusted:
        conn_str = f"Driver={_DEF_DRIVER};Server={instance};Trusted_Connection=yes;"
    else:
        conn_str = f"Driver={_DEF_DRIVER};Server={instance};Uid={user};Pwd={password};Trusted_Connection=no;"
    return pyodbc.connect(conn_str, autocommit=autocommit)

def db_exists(conn: pyodbc.Connection, db_name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT DB_ID(?)", db_name)
    return cur.fetchone()[0] is not None

def run_tsql(conn: pyodbc.Connection, tsql: str) -> None:
    cur = conn.cursor()
    cur.execute(tsql)
    try:
        while True:
            if cur.nextset():
                continue
            break
    except pyodbc.ProgrammingError:
        pass
