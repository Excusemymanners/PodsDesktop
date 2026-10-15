"""Tiny translation table: Romanian and English."""

from __future__ import annotations

import locale
import os

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "left": "Left", "right": "Right", "case": "Case", "battery": "Battery",
        "in_ear": "in ear", "charging": "charging", "unknown": "–",
        "not_connected": "Not connected", "connected": "Connected", "searching": "Searching…",
        "out_of_range": "Out of range", "no_device": "No AirPods bound",
        "noise_control": "Noise control", "mode_off": "Off", "mode_anc": "Noise Cancellation",
        "mode_transparency": "Transparency", "mode_adaptive": "Adaptive",
        "conversational_awareness": "Conversational awareness",
        "connect": "Connect", "disconnect": "Disconnect", "device": "Device", "refresh": "Refresh list",
        "settings": "Settings", "ear_detection": "Pause media when a pod is removed",
        "low_latency": "Low audio latency (keep the output awake)", "popup_on_lid": "Show battery when the case opens",
        "notifications": "Notifications", "ble_scan": "Listen to BLE advertisements", "autostart": "Start with the session",
        "show_battery": "Show battery", "fetch_keys": "Read device keys (exact identification)",
        "quit": "Quit", "about": "About PodsDesktop",
        "notify_low_title": "Battery low", "notify_low_body": "{name}: {level}% left",
        "notify_connected": "{name} connected", "notify_disconnected": "{name} disconnected",
        "notify_keys": "Device keys learned – your AirPods are now recognised exactly, even among others.",
        "source_aap": "live (AAP)", "source_ble": "advertisement", "source_ble_exact": "advertisement (identified)",
        "error": "PodsDesktop", "none_paired": "No paired Apple audio device. Pair the AirPods in the system settings first.",
        "tray_unavailable": "No system tray available; the app keeps running in the background (Ctrl-C to quit).",
    },
    "ro": {
        "left": "Stânga", "right": "Dreapta", "case": "Carcasă", "battery": "Baterie",
        "in_ear": "în ureche", "charging": "se încarcă", "unknown": "–",
        "not_connected": "Neconectate", "connected": "Conectate", "searching": "Caut…",
        "out_of_range": "În afara razei", "no_device": "Nicio pereche de AirPods aleasă",
        "noise_control": "Control zgomot", "mode_off": "Oprit", "mode_anc": "Anulare zgomot",
        "mode_transparency": "Transparență", "mode_adaptive": "Adaptiv",
        "conversational_awareness": "Conștientizare conversație",
        "connect": "Conectează", "disconnect": "Deconectează", "device": "Dispozitiv", "refresh": "Reîmprospătează lista",
        "settings": "Setări", "ear_detection": "Pauză la scoaterea unei căști din ureche",
        "low_latency": "Latență audio redusă (ține ieșirea trează)", "popup_on_lid": "Arată bateria la deschiderea carcasei",
        "notifications": "Notificări", "ble_scan": "Ascultă anunțurile BLE", "autostart": "Pornește odată cu sesiunea",
        "show_battery": "Arată bateria", "fetch_keys": "Citește cheile dispozitivului (identificare exactă)",
        "quit": "Ieșire", "about": "Despre PodsDesktop",
        "notify_low_title": "Baterie slabă", "notify_low_body": "{name}: a mai rămas {level}%",
        "notify_connected": "{name} s-au conectat", "notify_disconnected": "{name} s-au deconectat",
        "notify_keys": "Cheile dispozitivului au fost citite – AirPods-urile tale sunt acum recunoscute exact, chiar și printre altele.",
        "source_aap": "live (AAP)", "source_ble": "anunț BLE", "source_ble_exact": "anunț BLE (identificat)",
        "error": "PodsDesktop", "none_paired": "Niciun dispozitiv audio Apple pairat. Pairează întâi AirPods-urile din setările sistemului.",
        "tray_unavailable": "Nu există zonă de notificare; aplicația rulează în fundal (Ctrl-C pentru ieșire).",
    },
}

_language = "en"


def detect_language() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "ro" if value.lower().startswith("ro") else "en"
    try:
        code = locale.getlocale()[0] or ""
    except ValueError:
        code = ""
    return "ro" if code.lower().startswith("ro") else "en"


def set_language(code: str) -> None:
    global _language
    _language = code if code in STRINGS else detect_language()


def t(key: str, **kwargs) -> str:
    text = STRINGS.get(_language, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
