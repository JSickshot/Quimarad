from typing import Literal

def _esc(path: str) -> str:
    return path.replace("\\", "\\\\")

def tsql_contabilidad(data_path: str) -> str:
    ruta = _esc(data_path)
    return f"""
USE generalessql;
DECLARE @aliasempresa nvarchar(1000);
DECLARE @MDF nvarchar(1000), @LDF nvarchar(1000), @ruta nvarchar(1000);
SET @ruta = N'{ruta}';
DECLARE Empresas CURSOR FOR SELECT aliasbdd FROM listaempresas;
OPEN Empresas; FETCH NEXT FROM Empresas INTO @aliasempresa;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @aliasempresa + N'.mdf';
    SET @LDF = @ruta + @aliasempresa + N'_log.ldf';
    EXEC sp_attach_db @dbname = @aliasempresa, @filename1 = @MDF, @filename2 = @LDF;
    FETCH NEXT FROM Empresas INTO @aliasempresa;
END;
CLOSE Empresas; DEALLOCATE Empresas;
"""

def tsql_nominas(data_path: str) -> str:
    ruta = _esc(data_path)
    return f"""
USE nomgenerales;
DECLARE @aliasEmpresa nvarchar(1000);
DECLARE @MDF nvarchar(1000), @LDF nvarchar(1000), @ruta nvarchar(1000);
SET @ruta = N'{ruta}';
DECLARE Empresas CURSOR FOR SELECT rutaempresa FROM nom10000;
OPEN Empresas; FETCH NEXT FROM Empresas INTO @aliasEmpresa;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @aliasEmpresa + N'.mdf';
    SET @LDF = @ruta + @aliasEmpresa + N'_log.ldf';
    EXEC sp_attach_db @dbname = @aliasEmpresa, @filename1 = @MDF, @filename2 = @LDF;
    FETCH NEXT FROM Empresas INTO @aliasEmpresa;
END;
CLOSE Empresas; DEALLOCATE Empresas;
"""

def tsql_comercial(data_path: str) -> str:
    ruta = _esc(data_path)
    return f"""
USE CompacwAdmin;
DECLARE @aliasEmpresa nvarchar(100);
DECLARE @MDF nvarchar(100), @LDF nvarchar(100), @ruta nvarchar(100);
SET @ruta = N'{ruta}';
DECLARE CursorEmpresas CURSOR FOR
    SELECT REVERSE(SUBSTRING(REVERSE(crutadatos), 1, CHARINDEX('\\\\', REVERSE(crutadatos)) - 1))
    FROM Empresas WHERE cidempresa <> 1;
OPEN CursorEmpresas; FETCH NEXT FROM CursorEmpresas INTO @aliasEmpresa;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @aliasEmpresa + N'.mdf';
    SET @LDF = @ruta + @aliasEmpresa + N'_log.ldf';
    EXEC sp_attach_db @dbname = @aliasEmpresa, @filename1 = @MDF, @filename2 = @LDF;
    FETCH NEXT FROM CursorEmpresas INTO @aliasEmpresa;
END;
CLOSE CursorEmpresas; DEALLOCATE CursorEmpresas;
"""

def tsql_add(data_path: str, case: Literal[1, 2, 3]) -> str:
    ruta = _esc(data_path)
    if case == 1:
        ldf_expr = "+ N'mastlog.ldf' + {0} + N'.ldf'"
    elif case == 2:
        ldf_expr = "+ {0} + N'_log.ldf'"
    else:
        ldf_expr = "+ {0} + N'.ldf'"
    return f"""
USE DB_Directory;
DECLARE @DB_DocumentsMetadata nvarchar(1000);
DECLARE @DB_DocumentsContent nvarchar(1000);
DECLARE @DB_OthersMetadata nvarchar(1000);
DECLARE @DB_OthersContent nvarchar(1000);
DECLARE @MDF nvarchar(1000), @LDF nvarchar(1000), @ruta nvarchar(1000);
SET @ruta = N'{ruta}';

DECLARE Empresas CURSOR FOR
SELECT DB_DocumentsMetadata, DB_DocumentsContent, DB_OthersMetadata, DB_OthersContent
FROM DatabaseDirectory;

OPEN Empresas;
FETCH NEXT FROM Empresas INTO @DB_DocumentsMetadata, @DB_DocumentsContent, @DB_OthersMetadata, @DB_OthersContent;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @DB_DocumentsMetadata + N'.mdf';
    SET @LDF = @ruta {ldf_expr.format('@DB_DocumentsMetadata')};
    EXEC sp_attach_db @dbname = @DB_DocumentsMetadata, @filename1 = @MDF, @filename2 = @LDF;

    SET @MDF = @ruta + @DB_DocumentsContent + N'.mdf';
    SET @LDF = @ruta {ldf_expr.format('@DB_DocumentsContent')};
    EXEC sp_attach_db @dbname = @DB_DocumentsContent, @filename1 = @MDF, @filename2 = @LDF;

    SET @MDF = @ruta + @DB_OthersMetadata + N'.mdf';
    SET @LDF = @ruta {ldf_expr.format('@DB_OthersMetadata')};
    EXEC sp_attach_db @dbname = @DB_OthersMetadata, @filename1 = @MDF, @filename2 = @LDF;

    SET @MDF = @ruta + @DB_OthersContent + N'.mdf';
    SET @LDF = @ruta {ldf_expr.format('@DB_OthersContent')};
    EXEC sp_attach_db @dbname = @DB_OthersContent, @filename1 = @MDF, @filename2 = @LDF;

    FETCH NEXT FROM Empresas INTO @DB_DocumentsMetadata, @DB_DocumentsContent, @DB_OthersMetadata, @DB_OthersContent;
END;

CLOSE Empresas;
DEALLOCATE Empresas;
"""

def tsql_checkdb_all(quick: bool = True) -> str:
    """
    Recorre todas las bases de la instancia (excepto master, model, msdb, tempdb)
    y ejecuta DBCC CHECKDB. Modo rápido usa PHYSICAL_ONLY (mucho más veloz).
    """
    options = "WITH PHYSICAL_ONLY, NO_INFOMSGS" if quick else "WITH NO_INFOMSGS, ALL_ERRORMSGS"
    return f"""
DECLARE @db sysname;
DECLARE dbs CURSOR FOR
SELECT name FROM sys.databases
WHERE name NOT IN ('master','model','msdb','tempdb');

OPEN dbs; FETCH NEXT FROM dbs INTO @db;
WHILE @@FETCH_STATUS = 0
BEGIN
    PRINT 'CHECKDB -> ' + @db;
    DECLARE @sql nvarchar(max) = N'DBCC CHECKDB(''' + @db + ''') {options};';
    EXEC(@sql);
    FETCH NEXT FROM dbs INTO @db;
END
CLOSE dbs; DEALLOCATE dbs;
"""
