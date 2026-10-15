# PodsDesktop

AirPods on **Linux and Windows**: battery in the tray, a popup when the case opens, automatic
pause/resume when a pod leaves your ear, and (on Linux) noise-control modes and exact battery
percentages straight from the AirPods.

Written from scratch in Python after reverse-engineering what
[AirPodsDesktop](https://github.com/SpriteOvO/AirPodsDesktop) does and why it so often shows
nothing, mixes up other people's AirPods or pops up every minute. The protocol notes are in the
module docstrings; the reasoning is below.

*(Română mai jos.)*

## What it does

| Feature | Linux | Windows |
|---|---|---|
| Setup assistant on first start (Bluetooth check, pick the AirPods, options) | ✔ | ✔ |
| Battery of left / right pod and case in the tray + popup, with a picture of the model | ✔ | ✔ |
| Popup when the case is opened near the computer | ✔ | ✔ |
| Pause media when a pod is removed, resume when it is back | ✔ (MPRIS, every player) | ✔ (system media session, media-key fallback) |
| Exact 1 % battery levels, instant ear detection | ✔ (AAP session) | with imported keys |
| Noise control: Off / ANC / Transparency / Adaptive, conversational awareness | ✔ | – |
| Recognise *your* AirPods among other pairs in the room | ✔ exact (IRK) | ✔ exact once keys are imported, heuristic otherwise |
| Low-battery notification, connect/disconnect from the tray, autostart | ✔ | partial (no connect) |
| Keeps the audio output awake (low latency mode) | ✔ | ✔ |
| CLI for scripts and status bars (`--battery`, `--json`, `--watch`) | ✔ | ✔ |
| Any Apple/Beats model, including ones not in the table yet | ✔ | ✔ |

## Why the original "doesn't really work", and what is different here

AirPodsDesktop only listens to the Bluetooth LE *proximity pairing* advertisements. That packet
has three structural problems:

1. **Battery comes in steps of 10 %** (one nibble per pod). Nothing finer is in the clear part.
2. **The sender uses a random address that rotates**, so there is no way to say "this packet is
   from *my* AirPods". The original guesses from signal strength and battery continuity; with a
   second pair in the room you get their popups (issues #151, #233, #132 upstream).
3. **Ear detection and lid state are inferred** from status bits that flip depending on which
   pod is transmitting and whether it sits in the case, hence the "video does not pause when I
   remove the left pod" class of bugs (#255).

PodsDesktop keeps the advertisement path (it is the only thing that works on Windows and the only
thing that works while the pods are in the case), but adds the channel Apple's own devices use:

* **AAP over L2CAP (PSM 0x1001)** – once the AirPods are connected for audio, the app opens the
  Apple Accessory Protocol channel (no root, no kernel patch, no BlueZ `Experimental`). The pods
  then push exact battery levels, ear-detection events, the listening mode and their name and
  firmware, and accept commands (noise control, conversational awareness…).
* **Device keys** – over the same channel the pods hand out their *IRK* and *encryption key*.
  With the IRK the random BLE address becomes resolvable (standard Bluetooth `ah()` hash), so
  only packets from **your** pair are accepted, and with the encryption key the 16-byte tail of
  the advertisement decrypts to 1 % battery levels. Both keys are saved; on Windows you can copy
  them from a Linux install (`settings.json`) and get the same exact identification there.
* A full product-id table (AirPods 1–5, Pro 1–3, Max incl. Max 2 `0x202D`, Beats) and a generic
  fallback for unknown ids instead of "No paired device found" (#251, #189, #154).
* Single auto-bind: if exactly one Apple audio device is paired it is used, no wizard.
* Popups only on real lid-open transitions of *your* case; a tray tooltip and a click cover the
  rest (#233, #203).

Data sources are ranked: AAP session → identified advertisement → heuristic advertisement, with
the freshest usable data per component. The merging rules are unit-tested with synthetic packets
(`tests/`), including the AirPods 5 captures from the upstream test-suite.

## Install and run

Ready-made builds (from the GitHub Actions workflow, or a release): `PodsDesktop-Setup.exe`
(Windows installer, adds a Start-menu entry and optional autostart), `PodsDesktop.exe` (portable)
and `PodsDesktop-linux-x86_64.bin` (single-file Linux binary). On first start the setup assistant
checks Bluetooth, lets you pick the AirPods and set the options; it can be run again from the tray
menu or with `podsdesktop --setup`.

### Linux (Fedora, Ubuntu, Arch… with BlueZ ≥ 5.50)

```bash
git clone https://github.com/Excusemymanners/PodsDesktop.git
cd PodsDesktop
./packaging/install-linux.sh      # venv in ~/.local/share/podsdesktop, command in ~/.local/bin
podsdesktop                       # tray application (the assistant opens the first time)
```

Or build the single-file binary yourself: `.venv/bin/pip install -e ".[gui]" pyinstaller &&
./packaging/build-linux.sh` → `dist/PodsDesktop`.

Development setup instead:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[gui]"
.venv/bin/python -m podsdesktop
.venv/bin/python -m unittest discover -s tests
```

Pair the AirPods once in the system Bluetooth settings; everything else is automatic. The first
time they are connected the keys are learned (you get a notification), from then on they are
recognised exactly even when not connected.

### Windows 10 / 11

```powershell
py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e ".[gui,windows]"
python -m podsdesktop
```

`packaging\build-windows.ps1` builds `dist\PodsDesktop.exe` with PyInstaller and, when Inno Setup
is installed, `dist\PodsDesktop-Setup.exe`. The GitHub Actions workflow does the same on every
push and smoke-tests the WinRT backend on a Windows runner. The Windows backend (WinRT device
enumeration with a PnP fallback for the product id, media session control, radio power) follows
the same API as the Linux one; it has been checked against the WinRT type stubs but not yet run
with real AirPods – reports welcome.

### CLI

```
podsdesktop --battery          Luca's AirPods Pro  Left: 87% ⚡  Right: 85%  Case: 60%  [AAP]
podsdesktop --json             full state as JSON (for waybar, polybar, scripts)
podsdesktop --watch --battery  print on every change
podsdesktop --scan             dump every Apple proximity advertisement in range, with verdict
podsdesktop --devices          paired Apple audio devices (* = bound)
podsdesktop --bind CC:08:FA:BC:3F:2F
podsdesktop --mode anc         off | anc | transparency | adaptive (Linux, pods connected)
podsdesktop --keys             read and store the device keys over AAP
podsdesktop --connect / --disconnect
podsdesktop --setup            tray app + setup assistant
podsdesktop --preview [popup|wizard|settings]   demo data, no radio (design work)
```

The windows follow the system's light or dark scheme (`PODSDESKTOP_THEME=light|dark` forces one).
On Wayland sessions the app runs through XWayland (`QT_QPA_PLATFORM=xcb`) so the popup can sit next
to the tray; set `QT_QPA_PLATFORM=wayland` to override.

Settings live in `~/.config/podsdesktop/settings.json` (`%APPDATA%\PodsDesktop` on Windows), the
log in `~/.local/state/podsdesktop/podsdesktop.log`.

## Layout

```
podsdesktop/protocol/   proximity.py (BLE packet), aap.py (AAP packets), aes.py (AES-128 + ah()),
                        models.py (product ids) – pure Python, unit-tested
podsdesktop/core/       engine.py (orchestration), tracker.py (identity + side merging),
                        aap_client.py (L2CAP session), ble_scanner.py (bleak), bluetooth_*.py
                        (BlueZ / WinRT), media.py (MPRIS / GSMTC), settings.py, state.py
podsdesktop/gui/        PySide6 tray, popup, setup assistant, settings dialog, icons, images,
                        i18n (ro/en), engine thread bridge
tests/                  unit tests for the protocol, tracker and engine (no radio needed)
packaging/              Linux installer and PyInstaller build, .desktop file, Windows PyInstaller
                        script + Inno Setup installer, icon generator; .github/workflows builds all
```

## Credits

* [AirPodsDesktop](https://github.com/SpriteOvO/AirPodsDesktop) (GPL-3.0) – the starting point,
  the advertisement layout, the merging rules and the product renders in `gui/assets`.
* [LibrePods](https://github.com/librepods-org/librepods) – AAP documentation, device keys,
  payload decryption.
* [zeffd/airpods](https://github.com/zeffd/airpods) (MIT) – proof that AAP needs nothing but a
  socket on Linux.
* [furiousMAC/continuity](https://github.com/furiousMAC/continuity) and Celosia & Cunche,
  *Discontinued Privacy* (PoPETs 2020) – the Continuity protocol research.

## License

GPL-3.0-or-later. Apple, AirPods and Beats are trademarks of Apple Inc.; this project is not
affiliated with Apple.

---

## Română

**PodsDesktop** arată bateria AirPods-urilor în zona de notificare pe Linux și Windows, deschide o
fereastră când deschizi carcasa, pune pe pauză muzica când scoți o cască și, pe Linux, schimbă
modul de zgomot (Oprit / Anulare zgomot / Transparență / Adaptiv) și citește procentele exacte
direct din căști.

**De ce nu mergea bine originalul.** AirPodsDesktop ascultă doar anunțurile Bluetooth LE: bateria
vine în pași de 10 %, adresa expeditorului e aleatoare și se schimbă (deci nu știe care sunt
AirPods-urile *tale* – de aici ferestrele pentru căștile altora), iar starea „în ureche” e ghicită
din biți care se inversează după căsca ce emite.

**Ce e diferit aici.** Pe lângă anunțuri, aplicația deschide canalul folosit de dispozitivele
Apple (AAP peste L2CAP, fără root), de unde primește baterie exactă, evenimente de ureche
instantanee și comenzi, plus cheile dispozitivului: cu ele adresa aleatoare devine verificabilă
(doar perechea ta e acceptată) și coada criptată a anunțului se decriptează în procente exacte.
Tabelul de modele e complet (inclusiv AirPods Max 2), iar modelele necunoscute nu sunt aruncate.

**Instalare.** Pachete gata făcute din GitHub Actions / Releases: `PodsDesktop-Setup.exe`
(instalator Windows), `PodsDesktop.exe` (portabil) și `PodsDesktop-linux-x86_64.bin`. La prima
pornire, asistentul de configurare verifică Bluetooth-ul, te lasă să alegi AirPods-urile și
opțiunile; poate fi repornit din meniul din tray sau cu `podsdesktop --setup`. Pe Linux din surse:
`./packaging/install-linux.sh`, apoi `podsdesktop`. Pentru scripturi: `podsdesktop --battery`,
`--json`, `--watch`. Setările sunt în `~/.config/podsdesktop/settings.json`.

**Windows din surse:** `pip install -e ".[gui,windows]"` și `python -m podsdesktop`;
`packaging\build-windows.ps1` face `PodsDesktop.exe` și instalatorul. Partea de Windows e verificată
față de declarațiile WinRT și în CI, dar nu a fost încă rulată cu AirPods reale.
