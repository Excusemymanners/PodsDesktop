# Builds dist\PodsDesktop.exe (single file) and, when Inno Setup is installed, dist\PodsDesktop-Setup.exe.
#   py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; .\packaging\build-windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
pip install --upgrade pip
pip install ".[gui,windows]" pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name PodsDesktop `
    --icon packaging\podsdesktop.ico `
    --collect-data podsdesktop `
    --collect-all bleak --collect-all winrt `
    --hidden-import podsdesktop.core.bluetooth_windows --hidden-import podsdesktop.gui.app `
    podsdesktop\__main__.py
Write-Host "built: dist\PodsDesktop.exe"
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) { $iscc = Get-Item "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue }
if ($iscc) {
    & $iscc.FullName packaging\PodsDesktop.iss
    Write-Host "built: dist\PodsDesktop-Setup.exe"
} else {
    Write-Host "Inno Setup not found; only the portable exe was built."
}
