$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" } }
uv sync --frozen --extra dev
Check-Exit
npm ci --ignore-scripts
Check-Exit
Push-Location apps/jarvis_app
flutter pub get --enforce-lockfile
Check-Exit
flutter analyze
Check-Exit
flutter test
Check-Exit
flutter build windows --release
Check-Exit
Pop-Location
dotnet publish native/windows/Jarvis.Executor -c Release -r win-x64 --self-contained true -o dist/JARVIS/executor
Check-Exit
uv run --with 'pyinstaller==6.20.0' pyinstaller --noconfirm --onedir --name Jarvis.Backend --paths backend --collect-all jarvis --collect-all keyring --distpath dist/JARVIS scripts/backend_entry.py
Check-Exit
Copy-Item apps/jarvis_app/build/windows/x64/runner/Release/* dist/JARVIS -Recurse -Force
Copy-Item node_modules dist/JARVIS/node_modules -Recurse -Force
Copy-Item (Get-Command node).Source dist/JARVIS/node.exe -Force
Copy-Item scripts/launch-windows.ps1 dist/JARVIS -Force
Copy-Item scripts/launch-windows.vbs dist/JARVIS -Force
Copy-Item .env.example dist/JARVIS -Force
New-Item artifacts -ItemType Directory -Force | Out-Null
Compress-Archive -Path dist/JARVIS/* -DestinationPath artifacts/JARVIS-Windows-portable.zip -Force
if (Get-Command ISCC.exe -ErrorAction SilentlyContinue) {
    ISCC.exe deploy/windows-installer.iss
    Check-Exit
}
