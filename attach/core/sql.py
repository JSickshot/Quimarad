import pyodbc

def sql_conn(instance: str, trusted: bool = False, user: str | None = None, password: str | None = None):
    """
    Devuelve un connection abierto (context manager friendly) usando ODBC Driver 17.
    Siempre SQL Auth si trusted=False (recomendado para tu caso).
    """
    DRIVER = "{ODBC Driver 17 for SQL Server}"
    if trusted:
        conn_str = f"DRIVER={DRIVER};SERVER={instance};Trusted_Connection=yes;TrustServerCertificate=yes;"
    else:
        user = user or ""
        password = password or ""
        conn_str = (
            f"DRIVER={DRIVER};SERVER={instance};UID={user};PWD={password};"
            "TrustServerCertificate=yes;"
        )
    return pyodbc.connect(conn_str, autocommit=True)

def run_tsql(conn, tsql: str):
    with conn.cursor() as cur:
        cur.execute(tsql)
