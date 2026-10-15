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
        "settings": "Quick settings", "settings_dialog": "Settings…", "setup": "Setup assistant…",
        "ear_detection": "Pause media when a pod is removed",
        "low_latency": "Low audio latency (keep the output awake)", "popup_on_lid": "Show battery when the case opens",
        "notifications": "Notifications", "ble_scan": "Listen to BLE advertisements", "autostart": "Start with the session",
        "tray_show_percent": "Show the percentage in the tray icon",
        "show_battery": "Show battery", "fetch_keys": "Read device keys (exact identification)",
        "quit": "Quit", "about": "About PodsDesktop",
        "notify_low_title": "Battery low", "notify_low_body": "{name}: {level}% left",
        "notify_connected": "{name} connected", "notify_disconnected": "{name} disconnected",
        "notify_keys": "Device keys learned – your AirPods are now recognised exactly, even among others.",
        "source_aap": "live (AAP)", "source_ble": "advertisement", "source_ble_exact": "advertisement (identified)",
        "error": "PodsDesktop", "none_paired": "No paired Apple audio device. Pair the AirPods in the system settings first.",
        "tray_unavailable": "No system tray available; the app keeps running in the background (Ctrl-C to quit).",
        # setup assistant
        "wizard_title": "PodsDesktop setup",
        "welcome_title": "Welcome",
        "welcome_text": "PodsDesktop shows the battery of your AirPods in the notification area, pauses what is playing when you take a pod out and, on Linux, switches noise cancellation modes.\n\nThis assistant takes about a minute and can be run again any time from the tray menu.",
        "language": "Language", "lang_auto": "System language",
        "bt_title": "Bluetooth",
        "bt_text": "The Bluetooth adapter must be on and the AirPods must be paired with this computer, the same way as with any headset.",
        "bt_on": "Bluetooth is on.", "bt_off": "Bluetooth is off.", "bt_unknown": "Checking Bluetooth…",
        "bt_turn_on": "Turn on Bluetooth", "bt_open_settings": "Open Bluetooth settings",
        "device_title": "Your AirPods",
        "device_text": "Pick the pair to follow. If the list is empty, pair the AirPods in the system Bluetooth settings (open the lid, hold the button on the case until the light blinks white) and press Refresh.",
        "device_none": "No paired Apple audio device found yet.", "device_later": "I will choose later from the tray menu",
        "options_title": "Options", "options_text": "Everything here can be changed later from the tray menu.",
        "done_title": "All set", "done_text": "PodsDesktop runs in the notification area. Click the icon for the battery, right-click for the menu.",
        "done_keys_hint": "The first time the AirPods connect, their keys are read so they are recognised exactly from then on, even next to other AirPods.",
        "status_now": "Status now", "rssi_min": "Minimum signal strength for advertisements (dBm)",
        "popup_seconds": "Popup duration (seconds)", "run_setup": "Run the setup assistant",
        "general": "General", "behaviour": "Behaviour", "advanced": "Advanced",
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
        "settings": "Setări rapide", "settings_dialog": "Setări…", "setup": "Asistent de configurare…",
        "ear_detection": "Pauză la scoaterea unei căști din ureche",
        "low_latency": "Latență audio redusă (ține ieșirea trează)", "popup_on_lid": "Arată bateria la deschiderea carcasei",
        "notifications": "Notificări", "ble_scan": "Ascultă anunțurile BLE", "autostart": "Pornește odată cu sesiunea",
        "tray_show_percent": "Arată procentul în iconița din tray",
        "show_battery": "Arată bateria", "fetch_keys": "Citește cheile dispozitivului (identificare exactă)",
        "quit": "Ieșire", "about": "Despre PodsDesktop",
        "notify_low_title": "Baterie slabă", "notify_low_body": "{name}: a mai rămas {level}%",
        "notify_connected": "{name} s-au conectat", "notify_disconnected": "{name} s-au deconectat",
        "notify_keys": "Cheile dispozitivului au fost citite – AirPods-urile tale sunt acum recunoscute exact, chiar și printre altele.",
        "source_aap": "live (AAP)", "source_ble": "anunț BLE", "source_ble_exact": "anunț BLE (identificat)",
        "error": "PodsDesktop", "none_paired": "Niciun dispozitiv audio Apple pairat. Pairează întâi AirPods-urile din setările sistemului.",
        "tray_unavailable": "Nu există zonă de notificare; aplicația rulează în fundal (Ctrl-C pentru ieșire).",
        # asistent
        "wizard_title": "Configurare PodsDesktop",
        "welcome_title": "Bun venit",
        "welcome_text": "PodsDesktop arată bateria AirPods-urilor în zona de notificare, pune pe pauză ce se redă când scoți o cască din ureche și, pe Linux, schimbă modurile de anulare a zgomotului.\n\nAsistentul durează cam un minut și poate fi pornit din nou oricând din meniul din tray.",
        "language": "Limbă", "lang_auto": "Limba sistemului",
        "bt_title": "Bluetooth",
        "bt_text": "Adaptorul Bluetooth trebuie să fie pornit, iar AirPods-urile pairate cu acest calculator, ca orice căști.",
        "bt_on": "Bluetooth este pornit.", "bt_off": "Bluetooth este oprit.", "bt_unknown": "Verific Bluetooth…",
        "bt_turn_on": "Pornește Bluetooth", "bt_open_settings": "Deschide setările Bluetooth",
        "device_title": "AirPods-urile tale",
        "device_text": "Alege perechea de urmărit. Dacă lista e goală, pairează AirPods-urile din setările Bluetooth ale sistemului (deschide capacul, ține apăsat butonul carcasei până clipește alb) și apasă Reîmprospătează.",
        "device_none": "Nu s-a găsit încă niciun dispozitiv audio Apple pairat.", "device_later": "Aleg mai târziu din meniul din tray",
        "options_title": "Opțiuni", "options_text": "Tot ce e aici se poate schimba ulterior din meniul din tray.",
        "done_title": "Gata", "done_text": "PodsDesktop rulează în zona de notificare. Clic pe iconiță arată bateria, clic dreapta deschide meniul.",
        "done_keys_hint": "La prima conectare a AirPods-urilor li se citesc cheile, iar de atunci sunt recunoscute exact, chiar și lângă alte AirPods.",
        "status_now": "Starea acum", "rssi_min": "Semnal minim acceptat pentru anunțuri (dBm)",
        "popup_seconds": "Durata ferestrei (secunde)", "run_setup": "Pornește asistentul de configurare",
        "general": "General", "behaviour": "Comportament", "advanced": "Avansat",
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


def current_language() -> str:
    return _language


def t(key: str, **kwargs) -> str:
    text = STRINGS.get(_language, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
