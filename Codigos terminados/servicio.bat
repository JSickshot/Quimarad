@echo off
chcp 65001 >nul

REM
REM

sc query "Saci_CONTPAQi" | find "RUNNING" >nul
if %errorlevel%==0 (
    REM
    exit /b
)

net start "Saci_CONTPAQi" >nul 2>&1
exit /b
