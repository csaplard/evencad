# One command for Windows: backend + glasses app + simulator.
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# Options:  -NoSimulator   only the backend and the app dev server
#           -Docker        run the backend in Docker instead of a local Python
#           -Glasses       real G2: no simulator. The app talks to this PC over Wi-Fi and a QR code is shown.
#           -Ip <address>  the Wi-Fi address of this PC, if the script picks the wrong one
param([switch]$NoSimulator, [switch]$Docker, [switch]$Glasses, [string]$Ip)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-Tool($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Wait-Url($url, $seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { Start-Sleep -Seconds 1 }
    }
    return $false
}

if (-not (Test-Tool 'node')) { throw 'Node.js is missing. Install Node.js 22 LTS.' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env'; Write-Host 'Created .env from .env.example. Add ANTHROPIC_API_KEY to it.' }

# An older run that was not stopped keeps the ports. Then the new backend cannot start and the old code answers.
# Stop an old python or node on our ports. Anything else on a port is not ours: stop with a clear message.
foreach ($port in 8000, 5173, 5174) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $owners) {
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $p) { continue }
        if ($p.ProcessName -in 'python', 'node') {
            Write-Host "Port ${port}: stopping an older run ($($p.ProcessName), process $id)."
            taskkill /PID $id /T /F 2>$null | Out-Null
        }
        elseif ($port -ne 5174) { throw "Port $port is used by $($p.ProcessName) (process $id). Close it first." }
    }
}
Get-Process -Name 'evenhub-simulator' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if ($Glasses) {
    # The phone loads the app from this PC and the app calls the backend on this PC. "localhost" would be the phone.
    if (-not $Ip) {
        $all = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress
        $Ip = @($all | Where-Object { $_ -like '192.168.*' }) + @($all | Where-Object { $_ -like '10.*' }) + @($all) | Select-Object -First 1
    }
    if (-not $Ip) { throw 'No network address found. Give it with -Ip.' }
    $env:VITE_BACKEND_URL = "http://${Ip}:8000"
    $NoSimulator = $true
    Write-Host "Glasses mode. This PC: $Ip. The phone must be on the same Wi-Fi."
}

$jobs = @()
try {
    if ($Docker) {
        if (-not (Test-Tool 'docker')) { throw 'Docker is missing.' }
        docker compose up --build -d
        if ($LASTEXITCODE -ne 0) { throw 'docker compose failed.' }
    }
    else {
        $py = if (Test-Tool 'py') { 'py' } elseif (Test-Tool 'python') { 'python' } else { throw 'Python 3.11+ is missing.' }
        if (-not (Test-Path '.venv')) {
            Write-Host 'Creating the Python environment (first run takes a few minutes)...'
            if ($py -eq 'py') { py -3.11 -m venv .venv } else { python -m venv .venv }
        }
        & .venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'pip install failed.' }
        $env:STT_WARMUP = '1'
        $jobs += Start-Process -PassThru -NoNewWindow -FilePath '.venv\Scripts\python.exe' `
            -ArgumentList '-m', 'uvicorn', 'server.main:app', '--host', '0.0.0.0', '--port', '8000'
    }
    if (-not (Wait-Url 'http://127.0.0.1:8000/health' 90)) { throw 'The backend did not start on port 8000.' }
    Write-Host 'Backend:   http://localhost:8000  (API docs: /docs)'

    Push-Location app
    if (-not (Test-Path 'node_modules')) { npm install --no-fund --no-audit; if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' } }
    $jobs += Start-Process -PassThru -NoNewWindow -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev'
    Pop-Location
    if (-not (Wait-Url 'http://localhost:5173/' 60)) { throw 'The app dev server did not start on port 5173.' }
    Write-Host 'App:       http://localhost:5173'

    if (-not $NoSimulator) {
        Push-Location app
        $jobs += Start-Process -PassThru -NoNewWindow -FilePath 'cmd.exe' -ArgumentList '/c', 'npx evenhub-simulator http://localhost:5173'
        Pop-Location
        Write-Host 'Simulator: started. Click = tap. Speak into the PC microphone, or type in the app page.'
    }
    if ($Glasses) {
        Write-Host "Scan this code in the Even Realities app (developer mode, Even Hub). If Windows asks about the firewall, allow access."
        Push-Location app
        cmd /c "npx evenhub qr --url http://${Ip}:5173"
        Pop-Location
    }
    Write-Host 'Press Ctrl+C to stop everything.'
    while ($true) { Start-Sleep -Seconds 2 }
}
finally {
    foreach ($j in $jobs) { if ($j -and -not $j.HasExited) { taskkill /PID $j.Id /T /F 2>$null | Out-Null } }
    if ($Docker) { docker compose down }
}
