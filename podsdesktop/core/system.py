"""Small platform helpers: open the system Bluetooth settings."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def open_bluetooth_settings() -> bool:
    try:
        if sys.platform == "win32":
            os.startfile("ms-settings:bluetooth")  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.BluetoothSettings"])
            return True
        candidates = [
            ["systemsettings", "kcm_bluetooth"], ["systemsettings5", "kcm_bluetooth"],
            ["gnome-control-center", "bluetooth"], ["blueman-manager"], ["xfce4-settings-manager"],
        ]
        for cmd in candidates:
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
    except OSError:
        pass
    return False
