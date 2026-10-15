# Builds a single-file PodsDesktop.exe with PyInstaller (run in PowerShell on Windows 10/11).
#   py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; .\packaging\build-windows.ps1
$ErrorActionPreference = "Stop"
pip install --upgrade pip
pip install ".[gui,windows]" pyinstaller
pyinstaller --noconfirm --onefile --windowed --name PodsDesktop `
    --collect-all bleak --collect-all winrt `
    --hidden-import winrt.windows.media.control `
    --hidden-import winrt.windows.devices.enumeration `
    podsdesktop/__main__.py
Write-Host "built: dist\PodsDesktop.exe"
