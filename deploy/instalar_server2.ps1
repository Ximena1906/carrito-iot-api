<#
.SYNOPSIS
  Despliegue de Carrito IoT API en Windows Server (AWS EC2) con HTTPS/WSS.

.DESCRIPTION
  1. Instala Python (si falta).
  2. Descarga el código desde GitHub (conserva .env, .venv y logs).
  3. Crea el entorno virtual e instala dependencias.
  4. Verifica .env y la conexión con Amazon RDS.
  5. Instala Caddy: proxy inverso con certificado Let's Encrypt automático (HTTPS + WSS).
  6. Registra la API y Caddy como servicios de Windows (arranque automático y reinicio ante fallos).
  7. Verifica http://127.0.0.1:8000 y https://<dominio>.

  Se puede volver a ejecutar para ACTUALIZAR el código después de un git push.

.EXAMPLE
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
  C:\instalar_server2.ps1 -Dominio carrito-ximena.duckdns.org
#>
param(
    [Parameter(Mandatory = $true)] [string]$Dominio,
    [string]$Repo = "Ximena1906/carrito-iot-api",
    [string]$Rama = "main",
    [string]$PythonVersion = "3.14.7",
    [string]$Destino = "C:\carrito_iot_api",
    [string]$CarpetaCaddy = "C:\caddy"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ServicioApi = "CarritoIoTAPI"
$ServicioCaddy = "CarritoIoTCaddy"
$WinSWUrl = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"

function Paso([string]$texto) { Write-Host "`n==> $texto" -ForegroundColor Magenta }
function Ok([string]$texto) { Write-Host "    [ OK ] $texto" -ForegroundColor Green }
function Aviso([string]$texto) { Write-Host "    [AVISO] $texto" -ForegroundColor Yellow }

function Descargar([string]$url, [string]$archivo) {
    Write-Host "    Descargando $url"
    Invoke-WebRequest -Uri $url -OutFile $archivo -UseBasicParsing
}

function Escribir-SinBOM([string]$ruta, [string]$contenido) {
    [IO.File]::WriteAllText($ruta, $contenido, (New-Object System.Text.UTF8Encoding($false)))
}

function Detener-Servicio([string]$id) {
    $svc = Get-Service -Name $id -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne "Stopped") {
        Stop-Service -Name $id -Force
        $svc.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
    }
}

function Instalar-Servicio([string]$carpeta, [string]$id, [string]$xml, [string]$winsw) {
    $exe = Join-Path $carpeta "$id.exe"
    if (Get-Service -Name $id -ErrorAction SilentlyContinue) {
        Detener-Servicio $id
        & $exe uninstall | Out-Null
        Start-Sleep -Seconds 3
    }
    Copy-Item $winsw $exe -Force
    Escribir-SinBOM (Join-Path $carpeta "$id.xml") $xml
    & $exe install | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar el servicio $id" }
    Start-Service -Name $id
    (Get-Service -Name $id).WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
    Ok "Servicio $id en ejecución (inicio automático)"
}

# ---------------------------------------------------------------- 0. Requisitos
$identidad = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $identidad.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Ejecuta PowerShell como Administrador."
}
$tmp = Join-Path $env:TEMP "carrito_deploy"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# ---------------------------------------------------------------- 1. Python
Paso "1/7 Python $PythonVersion"
$serie = ($PythonVersion.Split(".")[0..1] -join "")
$py = "C:\Program Files\Python$serie\python.exe"
if (-not (Test-Path $py)) {
    $instalador = Join-Path $tmp "python-$PythonVersion-amd64.exe"
    Descargar "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe" $instalador
    Start-Process -FilePath $instalador -Wait `
        -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0"
}
if (-not (Test-Path $py)) { throw "Python no quedó instalado en $py" }
Ok ((& $py --version) | Out-String).Trim()

# ---------------------------------------------------------------- 2. Código
Paso "2/7 Código desde GitHub ($Repo, rama $Rama)"
Detener-Servicio $ServicioApi
$zip = Join-Path $tmp "codigo.zip"
$extraido = Join-Path $tmp "codigo"
if (Test-Path $extraido) { Remove-Item $extraido -Recurse -Force }
Descargar "https://github.com/$Repo/archive/refs/heads/$Rama.zip" $zip
Expand-Archive -Path $zip -DestinationPath $extraido -Force
$origen = (Get-ChildItem $extraido -Directory | Select-Object -First 1).FullName
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
# Sin /MIR: nunca borra .env, .venv ni logs del servidor.
robocopy $origen $Destino /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falló (código $LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Ok "Código copiado en $Destino"

# ---------------------------------------------------------------- 3. Dependencias
Paso "3/7 Entorno virtual y dependencias"
$venvPy = Join-Path $Destino ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { & $py -m venv (Join-Path $Destino ".venv") }
& $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
& $venvPy -m pip install -r (Join-Path $Destino "requirements.txt") --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "pip install falló" }
Ok "Dependencias instaladas en .venv"

# ---------------------------------------------------------------- 4. .env + RDS
Paso "4/7 Configuración (.env) y conexión con Amazon RDS"
$archivoEnv = Join-Path $Destino ".env"
if (-not (Test-Path $archivoEnv)) {
    Copy-Item (Join-Path $Destino ".env.example") $archivoEnv
    Aviso "Se creó $archivoEnv a partir de .env.example."
    Aviso "Pega tus valores reales (los mismos de tu .env local), guarda y vuelve a ejecutar este script."
    Start-Process notepad.exe $archivoEnv
    exit 1
}
$textoEnv = Get-Content $archivoEnv -Raw
if ($textoEnv -notmatch "(?m)^\s*APP_HOST\s*=\s*127\.0\.0\.1\s*$") {
    Aviso "En el servidor se recomienda APP_HOST=127.0.0.1 (solo Caddy expone la API a Internet)."
}
& $venvPy (Join-Path $Destino "diagnostico_bd.py")
if ($LASTEXITCODE -ne 0) {
    throw "Falló la conexión con RDS. Revisa .env y que el Security Group de RDS permita 3306 desde server2-sg."
}

# ---------------------------------------------------------------- 5. Caddy
Paso "5/7 Caddy: HTTPS y WSS con certificado automático"
foreach ($c in @($CarpetaCaddy, "$CarpetaCaddy\data", "$CarpetaCaddy\config", "$CarpetaCaddy\logs")) {
    New-Item -ItemType Directory -Force -Path $c | Out-Null
}
$caddy = Join-Path $CarpetaCaddy "caddy.exe"
if (-not (Test-Path $caddy)) {
    Detener-Servicio $ServicioCaddy
    Descargar "https://caddyserver.com/api/download?os=windows&arch=amd64" $caddy
}
Ok ((& $caddy version) | Out-String).Trim()
$rutaCaddyfile = Join-Path $CarpetaCaddy "Caddyfile"
$logsCaddy = ($CarpetaCaddy -replace "\\", "/") + "/logs/acceso.log"
$caddyfile = @"
$Dominio {
	encode gzip
	reverse_proxy 127.0.0.1:8000
	log {
		output file $logsCaddy {
			roll_size 10MiB
			roll_keep 5
		}
	}
}
"@
Escribir-SinBOM $rutaCaddyfile $caddyfile
& $caddy validate --config $rutaCaddyfile --adapter caddyfile
if ($LASTEXITCODE -ne 0) { throw "Caddyfile inválido" }
Ok "Caddyfile válido para $Dominio"

# ---------------------------------------------------------------- 6. Servicios
Paso "6/7 Servicios de Windows (WinSW)"
$winsw = Join-Path $tmp "WinSW-x64.exe"
if (-not (Test-Path $winsw)) { Descargar $WinSWUrl $winsw }

$xmlApi = @"
<service>
  <id>$ServicioApi</id>
  <name>Carrito IoT API (FastAPI)</name>
  <description>API del Carrito IoT: Uvicorn en 127.0.0.1:8000, Amazon RDS y WebSocket.</description>
  <executable>$venvPy</executable>
  <arguments>-m app.main</arguments>
  <workingdirectory>$Destino</workingdirectory>
  <startmode>Automatic</startmode>
  <onfailure action="restart" delay="5 sec"/>
  <onfailure action="restart" delay="15 sec"/>
  <resetfailure>1 hour</resetfailure>
  <env name="PYTHONUNBUFFERED" value="1"/>
  <logpath>$Destino\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>5120</sizeThreshold>
    <keepFiles>5</keepFiles>
  </log>
</service>
"@
Instalar-Servicio $Destino $ServicioApi $xmlApi $winsw

$xmlCaddy = @"
<service>
  <id>$ServicioCaddy</id>
  <name>Carrito IoT Caddy (HTTPS/WSS)</name>
  <description>Proxy inverso HTTPS/WSS para $Dominio hacia 127.0.0.1:8000.</description>
  <executable>$caddy</executable>
  <arguments>run --config "$rutaCaddyfile" --adapter caddyfile</arguments>
  <workingdirectory>$CarpetaCaddy</workingdirectory>
  <startmode>Automatic</startmode>
  <onfailure action="restart" delay="5 sec"/>
  <onfailure action="restart" delay="15 sec"/>
  <resetfailure>1 hour</resetfailure>
  <env name="XDG_DATA_HOME" value="$CarpetaCaddy\data"/>
  <env name="XDG_CONFIG_HOME" value="$CarpetaCaddy\config"/>
  <logpath>$CarpetaCaddy\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>5120</sizeThreshold>
    <keepFiles>5</keepFiles>
  </log>
</service>
"@
Instalar-Servicio $CarpetaCaddy $ServicioCaddy $xmlCaddy $winsw

# ---------------------------------------------------------------- 7. Verificación
Paso "7/7 Verificación"
Start-Sleep -Seconds 5
try {
    $local = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10
    Ok "API local: $($local.estado)"
} catch {
    Aviso "La API no responde en 127.0.0.1:8000. Revisa $Destino\logs\$ServicioApi.err.log"
}

try {
    $ips = (Resolve-DnsName -Name $Dominio -Type A -ErrorAction Stop | Where-Object { $_.IPAddress }).IPAddress
    Ok "DNS $Dominio -> $($ips -join ', ')"
} catch { Aviso "No se pudo resolver $Dominio. Revisa la IP en duckdns.org" }

$httpsOk = $false
for ($i = 1; $i -le 18 -and -not $httpsOk; $i++) {
    try {
        $r = Invoke-RestMethod -Uri "https://$Dominio/health/db" -TimeoutSec 10
        Ok "https://$Dominio/health/db -> $($r.estado) ($($r.latencia_ms) ms)"
        $httpsOk = $true
    } catch {
        Write-Host "    Esperando certificado HTTPS... ($i/18)"
        Start-Sleep -Seconds 10
    }
}
if (-not $httpsOk) {
    Aviso "HTTPS aún no responde. Revisa $CarpetaCaddy\logs\$ServicioCaddy.err.log (puertos 80/443 abiertos y DNS correcto)."
}

Write-Host ""
Write-Host "================= LISTO =================" -ForegroundColor Magenta
Write-Host "  Swagger : https://$Dominio/docs"
Write-Host "  Salud   : https://$Dominio/health   y   https://$Dominio/health/db"
Write-Host "  WSS     : wss://$Dominio/ws/vehiculos/1"
Write-Host "  Servicios: Get-Service $ServicioApi, $ServicioCaddy"
Write-Host "  Logs API : $Destino\logs   |   Logs Caddy: $CarpetaCaddy\logs"
Write-Host "  Actualizar código: vuelve a ejecutar este script después de un git push."
