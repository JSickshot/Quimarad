@echo off
setlocal

title Reparar Windows

echo  Quimarad consulting Group
echo  Equipo: %COMPUTERNAME%
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Haz clic derecho sobre el .bat y elige:
    echo "Ejecutar como administrador".
    echo.
    pause
    exit /b 1
)

set "LOGDIR=%SystemRoot%\Logs\Mantenimiento"
if not exist "%LOGDIR%" md "%LOGDIR%" >nul 2>&1

set "DATESTAMP=%DATE:~-4%%DATE:~3,2%%DATE:~0,2%_%TIME:~0,2%%TIME:~3,2%"
set "DATESTAMP=%DATESTAMP: =0%"

set "LOGFILE=%LOGDIR%\reparacion_%COMPUTERNAME%_%DATESTAMP%.log"

echo Log: %LOGFILE%
echo ==================================================>> "%LOGFILE%"
echo  Reparacion %COMPUTERNAME% >> "%LOGFILE%"
echo  Fecha/Hora: %DATE% %TIME% >> "%LOGFILE%"
echo.>> "%LOGFILE%"

echo Ejecutando DISM /Online /Cleanup-Image /RestoreHealth
echo [DISM] Inicio: %DATE% %TIME% >> "%LOGFILE%"
DISM /Online /Cleanup-Image /RestoreHealth >> "%LOGFILE%" 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] DISM fallo. Revisa el log:
    echo        %LOGFILE%
    echo.
    echo [NOTA] Aun asi puedes intentar correr SFC manualmente.
    echo.
    pause
    goto :EOF
)

echo [DISM] Finalizado correctamente. >> "%LOGFILE%"
echo DISM finalizado correctamente.
echo.
echo Ejecutando SFC /scannow ...
echo [SFC] Inicio: %DATE% %TIME% >> "%LOGFILE%"
sfc /scannow >> "%LOGFILE%" 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [AVISO] SFC terminó con errores. Revisa el log:
    echo         %LOGFILE%
    echo.
    pause
    goto :EOF
)

echo [SFC] Finalizado correctamente. >> "%LOGFILE%"
echo SFC finalizado correctamente.
echo.

echo  PROCESO TERMINADO

pause
endlocal
