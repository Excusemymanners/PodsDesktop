"""Start PodsDesktop with the user session (XDG autostart on Linux, Run key on Windows)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _launch_command() -> str:
    exe = Path(sys.executable)
    if exe.name.lower().startswith("python"):
        return f'"{exe}" -m podsdesktop'
    return f'"{exe}"'


def _desktop_file() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "autostart" / "podsdesktop.desktop"


def is_enabled() -> bool:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "PodsDesktop")
                return True
        except OSError:
            return False
    return _desktop_file().exists()


def set_enabled(enabled: bool) -> None:
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, "PodsDesktop", 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, "PodsDesktop")
                except FileNotFoundError:
                    pass
        return
    path = _desktop_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=PodsDesktop\n"
            f"Exec={_launch_command()}\nIcon=audio-headphones\nTerminal=false\n"
            "X-GNOME-Autostart-enabled=true\nX-KDE-autostart-after=panel\n",
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()
