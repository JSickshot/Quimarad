def tsql_contabilidad(ruta_data: str) -> str:
    ruta_sql = ruta_data.replace("'", "''").replace("/", "\\")
    return f"""
USE [generalessql];
IF DB_ID(N'generalessql') IS NULL AND DB_ID(N'GeneralesSQL') IS NOT NULL USE [GeneralesSQL];
IF DB_ID(N'generalessql') IS NULL AND DB_ID(N'GENERALESSQL') IS NOT NULL USE [GENERALESSQL];

DECLARE @alias nvarchar(1000),
        @MDF nvarchar(2000),
        @LDF nvarchar(2000),
        @ruta nvarchar(2000);
SET @ruta = N'{ruta_sql}';

DECLARE c CURSOR FOR
    SELECT aliasbdd
    FROM listaempresas
    WHERE NULLIF(aliasbdd,'') IS NOT NULL;

OPEN c;
FETCH NEXT FROM c INTO @alias;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @alias + N'.mdf';
    SET @LDF = CASE
                   WHEN EXISTS(SELECT 1 FROM sys.master_files WHERE physical_name = @ruta + N'mastlog.ldf' + @alias + N'.ldf')
                       THEN @ruta + N'mastlog.ldf' + @alias + N'.ldf'
                   WHEN EXISTS(SELECT 1 FROM sys.master_files WHERE physical_name = @ruta + @alias + N'_log.ldf')
                       THEN @ruta + @alias + N'_log.ldf'
                   ELSE @ruta + @alias + N'.ldf'
               END;

    BEGIN TRY
        EXEC (N'CREATE DATABASE [' + @alias + N'] ON ' +
              N'(FILENAME=N''' + @MDF + N'''), ' +
              N'(FILENAME=N''' + @LDF + N''') FOR ATTACH;');
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() IN (5105, 5120, 5173, 1813)
            EXEC (N'CREATE DATABASE [' + @alias + N'] ON ' +
                  N'(FILENAME=N''' + @MDF + N''') FOR ATTACH_REBUILD_LOG;');
        ELSE
            RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH;

    FETCH NEXT FROM c INTO @alias;
END

CLOSE c;
DEALLOCATE c;
"""


def tsql_comercial(ruta_data: str) -> str:
    ruta_sql = ruta_data.replace("'", "''").replace("/", "\\")
    return f"""
USE [CompacwAdmin];
IF DB_ID(N'CompacwAdmin') IS NULL AND DB_ID(N'compacwadmin') IS NOT NULL USE [compacwadmin];
IF DB_ID(N'CompacwAdmin') IS NULL AND DB_ID(N'COMPACWADMIN') IS NOT NULL USE [COMPACWADMIN];

DECLARE @alias nvarchar(1000),
        @MDF nvarchar(2000),
        @LDF nvarchar(2000),
        @ruta nvarchar(2000);
SET @ruta = N'{ruta_sql}';

;WITH E AS (
  SELECT crutadatos FROM Empresas WHERE cidempresa<>1 AND NULLIF(crutadatos,'') IS NOT NULL
)
SELECT @alias = NULL;

DECLARE c CURSOR FOR
    SELECT REVERSE(SUBSTRING(REVERSE(crutadatos),1,CHARINDEX('\',REVERSE(crutadatos))-1))
    FROM E
    WHERE crutadatos LIKE '%\%';

OPEN c;
FETCH NEXT FROM c INTO @alias;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @alias + N'.mdf';
    SET @LDF = CASE
                   WHEN EXISTS(SELECT 1 FROM sys.master_files WHERE physical_name = @ruta + N'mastlog.ldf' + @alias + N'.ldf')
                       THEN @ruta + N'mastlog.ldf' + @alias + N'.ldf'
                   WHEN EXISTS(SELECT 1 FROM sys.master_files WHERE physical_name = @ruta + @alias + N'_log.ldf')
                       THEN @ruta + @alias + N'_log.ldf'
                   ELSE @ruta + @alias + N'.ldf'
               END;

    BEGIN TRY
        EXEC (N'CREATE DATABASE [' + @alias + N'] ON ' +
              N'(FILENAME=N''' + @MDF + N'''), ' +
              N'(FILENAME=N''' + @LDF + N''') FOR ATTACH;');
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() IN (5105, 5120, 5173, 1813)
            EXEC (N'CREATE DATABASE [' + @alias + N'] ON ' +
                  N'(FILENAME=N''' + @MDF + N''') FOR ATTACH_REBUILD_LOG;');
        ELSE
            RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH;

    FETCH NEXT FROM c INTO @alias;
END

CLOSE c;
DEALLOCATE c;
"""


def tsql_nominas(ruta_data: str) -> str:
    """
    Detecta dinámicamente la BD de catálogos de nóminas (nomGenerales/Nomgenerales/nomgenerales),
    hace USE sobre la que exista y adjunta las empresas de nom10000.
    """
    ruta_sql = ruta_data.replace("'", "''").replace("/", "\\")
    return f"""
DECLARE @db sysname;
SELECT @db = 
    CASE 
        WHEN DB_ID(N'nomGenerales') IS NOT NULL THEN N'nomGenerales'
        WHEN DB_ID(N'Nomgenerales') IS NOT NULL THEN N'Nomgenerales'
        WHEN DB_ID(N'nomgenerales') IS NOT NULL THEN N'nomgenerales'
        ELSE NULL
    END;

IF @db IS NULL
BEGIN
    RAISERROR(N'No se encontró la BD de catálogo de nóminas (nomGenerales/Nomgenerales/nomgenerales).', 16, 1);
    RETURN;
END;

DECLARE @sql nvarchar(max) = N'USE [' + @db + N'];
DECLARE @alias nvarchar(1000),
        @MDF nvarchar(2000),
        @LDF nvarchar(2000),
        @ruta nvarchar(2000);
SET @ruta = N''' + N'{ruta_sql}' + N''';

DECLARE c CURSOR FOR
    SELECT rutaempresa FROM nom10000 WHERE NULLIF(rutaempresa, '''') IS NOT NULL;

OPEN c;
FETCH NEXT FROM c INTO @alias;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @alias + N''.mdf'';
    SET @LDF = CASE
                   WHEN EXISTS(SELECT 1 FROM sys.master_files WHERE physical_name = @ruta + N''mastlog.ldf'' + @alias + N''.ldf'')
                       THEN @ruta + N''mastlog.ldf'' + @alias + N''.ldf''
                   WHEN EXISTS(SELECT 1 FROM sys.master_files WHERE physical_name = @ruta + @alias + N''_log.ldf'')
                       THEN @ruta + @alias + N''_log.ldf''
                   ELSE @ruta + @alias + N''.ldf''
               END;

    BEGIN TRY
        EXEC (N''CREATE DATABASE ['' + @alias + N''] ON '' +
              N''(FILENAME=N'''''' + @MDF + N''''''), '' +
              N''(FILENAME=N'''''' + @LDF + N'''''' ) FOR ATTACH;'');
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() IN (5105, 5120, 5173, 1813)
            EXEC (N''CREATE DATABASE ['' + @alias + N''] ON '' +
                  N''(FILENAME=N'''''' + @MDF + N'''''' ) FOR ATTACH_REBUILD_LOG;'');
        ELSE
            RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH;

    FETCH NEXT FROM c INTO @alias;
END

CLOSE c;
DEALLOCATE c;';
EXEC sp_executesql @sql;
"""


def tsql_add(ruta_data: str, caso: int) -> str:
    """
    ADD – 3 variantes de nombre del LDF:
      1) mastlog.ldf{alias}.ldf
      2) {alias}_log.ldf
      3) {alias}.ldf
    Recorre DatabaseDirectory en DB_Directory (casing tolerante).
    """
    ruta_sql = ruta_data.replace("'", "''").replace("/", "\\")
    return f"""
DECLARE @db sysname;
SELECT @db = 
    CASE 
        WHEN DB_ID(N'DB_Directory') IS NOT NULL THEN N'DB_Directory'
        WHEN DB_ID(N'db_directory') IS NOT NULL THEN N'db_directory'
        WHEN DB_ID(N'DB_DIRECTORY') IS NOT NULL THEN N'DB_DIRECTORY'
        ELSE NULL
    END;

IF @db IS NULL
BEGIN
    RAISERROR(N'No se encontró la BD DB_Directory.', 16, 1);
    RETURN;
END;

DECLARE @sql nvarchar(max) = N'USE [' + @db + N'];
DECLARE @alias nvarchar(2000),
        @MDF nvarchar(4000),
        @LDF nvarchar(4000),
        @ruta nvarchar(2000);
SET @ruta = N''' + N'{ruta_sql}' + N''';

DECLARE c CURSOR FOR
SELECT DISTINCT v
FROM (
  SELECT DB_DocumentsMetadata AS v FROM DatabaseDirectory
  UNION ALL SELECT DB_DocumentsContent FROM DatabaseDirectory
  UNION ALL SELECT DB_OthersMetadata FROM DatabaseDirectory
  UNION ALL SELECT DB_OthersContent  FROM DatabaseDirectory
) A
WHERE NULLIF(v, '''') IS NOT NULL;

OPEN c;
FETCH NEXT FROM c INTO @alias;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @MDF = @ruta + @alias + N''.mdf'';

    IF {caso} = 1
        SET @LDF = @ruta + N''mastlog.ldf'' + @alias + N''.ldf'';
    ELSE IF {caso} = 2
        SET @LDF = @ruta + @alias + N''_log.ldf'';
    ELSE
        SET @LDF = @ruta + @alias + N''.ldf'';

    BEGIN TRY
        EXEC (N''CREATE DATABASE ['' + @alias + N''] ON '' +
              N''(FILENAME=N'''''' + @MDF + N''''''), '' +
              N''(FILENAME=N'''''' + @LDF + N'''''' ) FOR ATTACH;'');
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() IN (5105, 5120, 5173, 1813)
            EXEC (N''CREATE DATABASE ['' + @alias + N''] ON '' +
                  N''(FILENAME=N'''''' + @MDF + N'''''' ) FOR ATTACH_REBUILD_LOG;'');
        ELSE
            RAISERROR(ERROR_MESSAGE(), 16, 1);
    END CATCH;

    FETCH NEXT FROM c INTO @alias;
END

CLOSE c;
DEALLOCATE c;';
EXEC sp_executesql @sql;
"""


def tsql_checkdb_all(quick: bool = True) -> str:
    opts = "WITH NO_INFOMSGS, PHYSICAL_ONLY" if quick else "WITH NO_INFOMSGS"
    return f"""
DECLARE @name sysname, @sql nvarchar(max);
DECLARE dbs CURSOR FOR
SELECT name FROM sys.databases WHERE database_id>4 ORDER BY name;
OPEN dbs;
FETCH NEXT FROM dbs INTO @name;
WHILE @@FETCH_STATUS=0
BEGIN
    SET @sql = N'DBCC CHECKDB([' + @name + N']) {opts};';
    BEGIN TRY
        EXEC (@sql);
    END TRY
    BEGIN CATCH
        PRINT N'CHECKDB ERROR ' + @name + N': ' + ERROR_MESSAGE();
    END CATCH;
    FETCH NEXT FROM dbs INTO @name;
END
CLOSE dbs; DEALLOCATE dbs;
"""
