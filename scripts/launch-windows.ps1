$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:JARVIS_RUNTIME_DIR = $PSScriptRoot
$env:JARVIS_WINDOWS_EXECUTOR = Join-Path $PSScriptRoot 'executor/Jarvis.Executor.exe'
$env:PATH = "$PSScriptRoot;$env:PATH"
$env:JARVIS_MCP_ENABLED = 'true'
try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2 } catch { $health = $null }
if ($null -eq $health) {
    Start-Process -FilePath (Join-Path $PSScriptRoot 'Jarvis.Backend/Jarvis.Backend.exe') -ArgumentList 'serve' -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1; break } catch { Start-Sleep -Milliseconds 500 }
    }
}
if ($null -eq $health -or $health.version -ne '0.1.0') { throw 'No se pudo verificar el backend JARVIS local.' }
Start-Process -FilePath (Join-Path $PSScriptRoot 'jarvis_app.exe')
