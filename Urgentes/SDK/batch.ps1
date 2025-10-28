# Requires -RunAsAdministrator
# Uso: clic derecho "Run with PowerShell" o: powershell -ExecutionPolicy Bypass -File .\build_sdk_app.ps1

$ErrorActionPreference = "Stop"

function Ensure-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "Re-ejecutando como Administrador..." -ForegroundColor Yellow
        Start-Process powershell "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
        exit
    }
}
Ensure-Admin

# 1) Ruta del SDK (x86) por defecto
$DefaultSdkDir = "C:\Program Files (x86)\Compac\COMERCIAL"

# 2) Confirmar ubicación del proyecto (debe existir app.py)
if (-not (Test-Path ".\app.py")) {
    Write-Error "No se encontró .\app.py en el directorio actual. Abre una consola aquí."
}

# 3) Buscar Python 3.11 x86
function Get-Py311x86 {
    $pyList = & "$env:WINDIR\py.exe" -0 2>$null
    if ($LASTEXITCODE -eq 0 -and $pyList) {
        foreach ($l in $pyList) {
            if ($l -match "3\.11-32") { return "$env:WINDIR\py.exe" }
        }
    }
    return $null
}

$pyLauncher = "$env:WINDIR\py.exe"
$have311x86 = Get-Py311x86

if (-not $have311x86) {
    Write-Host "Instalando Python 3.11 (32-bit) con winget..." -ForegroundColor Cyan
    # Nota: Si falla este ID, usa el de 3.11.x más cercano disponible en winget
    winget install -e --id Python.Python.3.11 --architecture x86 --accept-package-agreements --accept-source-agreements
    Start-Sleep -Seconds 5
    $have311x86 = Get-Py311x86
    if (-not $have311x86) {
        Write-Error "No se pudo encontrar ni instalar Python 3.11 (32-bit). Abre Microsoft Store/winget e instálalo manualmente."
    }
}

# 4) Crear venv con 3.11-32
Write-Host "Creando entorno .venv con Python 3.11 (32-bit)..." -ForegroundColor Cyan
& $pyLauncher -3.11-32 -m venv .venv
if ($LASTEXITCODE -ne 0) { Write-Error "Falló la creación del venv." }

$venvPy = Join-Path ".venv" "Scripts\python.exe"
$venvPip = Join-Path ".venv" "Scripts\pip.exe"

# 5) Actualizar pip y dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip
# Requisitos mínimos (ajusta si usas otros módulos)
@"
pillow==11.0.0
pyinstaller==6.6.0
"@ | Out-File -Encoding UTF8 -FilePath requirements.txt -Force
& $venvPip install -r requirements.txt

# 6) Variable de entorno del SDK (COMPAC_SDK_DIR) si no existe
if (-not $env:COMPAC_SDK_DIR) {
    if (Test-Path $DefaultSdkDir) {
        Write-Host "Estableciendo COMPAC_SDK_DIR -> $DefaultSdkDir" -ForegroundColor Cyan
        setx COMPAC_SDK_DIR "$DefaultSdkDir" | Out-Null
        $env:COMPAC_SDK_DIR = $DefaultSdkDir
    } else {
        Write-Warning "No se encontró $DefaultSdkDir. Si tu SDK está en otra ruta, define COMPAC_SDK_DIR manualmente."
    }
} else {
    Write-Host "COMPAC_SDK_DIR ya definido: $env:COMPAC_SDK_DIR" -ForegroundColor Green
}

# 7) Comprobación rápida: MGW000.DLL/MGWSERVICIOS.DLL existen
if ($env:COMPAC_SDK_DIR -and -not (Test-Path (Join-Path $env:COMPAC_SDK_DIR "MGW000.DLL"))) {
    Write-Warning "No se encontró MGW000.DLL en $env:COMPAC_SDK_DIR. Verifica tu instalación de CONTPAQi Comercial (x86)."
}
if ($env:COMPAC_SDK_DIR -and -not (Test-Path (Join-Path $env:COMPAC_SDK_DIR "MGWSERVICIOS.DLL"))) {
    Write-Warning "No se encontró MGWSERVICIOS.DLL en $env:COMPAC_SDK_DIR."
}

# 8) Compilar con PyInstaller (onefile, noconsole, clean)
Write-Host "Compilando app.py → dist\app.exe ..." -ForegroundColor Cyan
& $venvPy -m PyInstaller --noconfirm --clean --noconsole --onefile app.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Falló PyInstaller. Revisa los avisos anteriores."
} else {
    Write-Host "¡Listo! Ejecutable en .\dist\app.exe" -ForegroundColor Green
}

Write-Host "Nota: Si ves errores de 'VC++ runtimes', instala el 'Microsoft Visual C++ 2015-2022 Redistributable (x86)'." -ForegroundColor Yellow
