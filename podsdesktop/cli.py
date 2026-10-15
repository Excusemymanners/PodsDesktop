"""Command line entry point.

    podsdesktop                 start the tray application
    podsdesktop --battery       print the battery once (AAP or BLE) and exit
    podsdesktop --json          same, as JSON
    podsdesktop --watch         keep printing on every change
    podsdesktop --scan          dump every Apple proximity advertisement in range
    podsdesktop --devices       list paired Apple audio devices
    podsdesktop --bind ADDR     bind to that device (see --devices)
    podsdesktop --mode anc      set the listening mode: off | anc | transparency | adaptive
    podsdesktop --keys          read the device keys over AAP and store them
    podsdesktop --connect / --disconnect
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time

from . import __version__
from .core.engine import Engine
from .core.settings import Settings
from .core.state import DeviceState
from .logging_setup import setup_logging
from .protocol import aap

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="podsdesktop", description="AirPods battery, ear detection and noise control for Linux and Windows.")
    p.add_argument("--version", action="version", version=f"PodsDesktop {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("--setup", action="store_true", help="start the tray app with the setup assistant")
    p.add_argument("--preview", nargs="?", const="popup", choices=["popup", "wizard", "settings"],
                   help="show a window with demo data, no radio (design work, screenshots)")
    p.add_argument("--snapshot", metavar="FILE.png", help="with --preview: render the window into a PNG and exit "
                   "(use QT_QPA_PLATFORM=offscreen for a clean, screen-less render)")
    g = p.add_argument_group("one-shot commands")
    g.add_argument("--battery", action="store_true", help="print battery levels and exit")
    g.add_argument("--json", action="store_true", help="print the full state as JSON and exit")
    g.add_argument("--watch", action="store_true", help="with --battery/--json: keep printing on change")
    g.add_argument("--timeout", type=float, default=15.0, help="seconds to wait for data (default 15)")
    g.add_argument("--scan", action="store_true", help="dump Apple proximity advertisements")
    g.add_argument("--raw", action="store_true", help="with --scan: do not hide the encrypted tail")
    g.add_argument("--devices", action="store_true", help="list paired Apple audio devices")
    g.add_argument("--bind", metavar="ADDR", help="bind to the device with this address")
    g.add_argument("--unbind", action="store_true", help="forget the bound device")
    g.add_argument("--mode", choices=sorted(aap.MODE_KEYS), help="set the listening mode (needs AAP)")
    g.add_argument("--keys", action="store_true", help="read IRK/ENC keys over AAP and store them")
    g.add_argument("--connect", action="store_true", help="connect the bound device (Linux)")
    g.add_argument("--disconnect", action="store_true", help="disconnect the bound device (Linux)")
    g.add_argument("--no-scan", action="store_true", help="do not use BLE for the one-shot commands")
    return p


def format_battery(state: DeviceState) -> str:
    src = {"aap": "AAP", "ble-exact": "BLE+key", "ble": "BLE"}.get(state.source, "-")
    parts = [state.display_name]
    if state.is_headset:
        parts.append(f"Battery: {state.left.text()}")
    else:
        parts.append(f"Left: {state.left.text()}  Right: {state.right.text()}  Case: {state.case.text()}")
    ears = [name for name, c in (("L", state.left), ("R", state.right)) if c.in_ear]
    if ears:
        parts.append("in ear: " + "+".join(ears))
    if state.noise_mode:
        parts.append(f"mode: {aap.MODE_NAMES.get(state.noise_mode)}")
    parts.append(f"[{src}]")
    return "  ".join(parts)


async def _run_oneshot(args, settings: Settings) -> int:
    if args.no_scan:
        settings.ble_scan = False
    engine = Engine(settings)
    loop = asyncio.get_running_loop()
    done = loop.create_future()
    printed = {"n": 0}

    def on_event(event: str, payload):
        if event == "error":
            print(f"error: {payload}", file=sys.stderr)
        if event == "devices" and args.devices:
            if not done.done():
                done.set_result(payload)
            return
        if event == "keys" and args.keys and not done.done():
            done.set_result(True)
        if event != "state":
            return
        state: DeviceState = payload
        if args.mode and not done.done():
            if state.aap_connected:
                done.set_result(True)
            return
        if args.keys:
            return
        if not state.has_battery:
            return
        line = json.dumps(state.to_dict(), default=str) if args.json else format_battery(state)
        if args.watch:
            print(line, flush=True)
            printed["n"] += 1
        elif not done.done():
            done.set_result(line)

    engine.subscribe(on_event)
    runner = asyncio.create_task(engine.run())
    code = 0
    try:
        if args.bind or args.unbind:
            await asyncio.sleep(0.5)
            await engine.bind(None if args.unbind else args.bind)
            print("bound to", engine.settings.device_address or "nothing")
            return 0
        if args.connect or args.disconnect:
            await asyncio.sleep(0.5)
            await (engine.connect_device() if args.connect else engine.disconnect_device())
            print("done")
            return 0
        if args.watch:
            await asyncio.sleep(args.timeout if args.timeout > 0 else 3600 * 24)
            return 0
        try:
            result = await asyncio.wait_for(done, timeout=args.timeout)
        except asyncio.TimeoutError:
            if args.keys:
                print("no keys received (AAP session needed: Linux, pods connected)", file=sys.stderr)
            elif args.mode:
                print("no AAP session (Linux only, pods must be connected)", file=sys.stderr)
            else:
                print("no battery report within the timeout (device off, out of range or not bound)", file=sys.stderr)
            return 1
        if args.devices:
            if not result:
                print("no paired Apple audio devices")
            for d in result:
                mark = "*" if d.address.upper() == (settings.device_address or "").upper() else " "
                print(f"{mark} {d.address}  {d.name!s:28} {d.model_name:28} {'connected' if d.connected else ''}")
            return 0
        if args.mode:
            await engine.set_noise_mode(aap.MODE_KEYS[args.mode])
            await asyncio.sleep(0.5)
            print("mode set:", aap.MODE_NAMES[aap.MODE_KEYS[args.mode]])
            return 0
        if args.keys:
            print("keys stored in", settings.path)
            return 0
        print(result)
        return 0
    finally:
        engine.stop()
        try:
            await asyncio.wait_for(runner, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
    return code


async def _run_scan(args, settings: Settings) -> int:
    from .core.ble_scanner import BleScanner
    from .core.tracker import IdentityFilter

    identity = IdentityFilter(settings.irk_bytes, settings.model_id, settings.rssi_min)
    seen = {}

    def on_adv(address, rssi, adv):
        verdict = identity.classify(address, rssi, adv)
        data = adv.raw if args.raw else adv.desensitized()
        key = (address, data)
        if seen.get(key) == data and not args.verbose:
            return
        seen[key] = data
        ears = "".join(x for x, f in (("L", adv.left_in_ear), ("R", adv.right_in_ear)) if f) or "-"
        lid = {True: "open", False: "closed", None: "?"}[adv.lid_open]
        print(f"{time.strftime('%H:%M:%S')} {address} {rssi!s:>4} {verdict:7} {adv.model.name:24} "
              f"L{adv.left_battery!s:>4} R{adv.right_battery!s:>4} C{adv.case_battery!s:>4} "
              f"chg={int(adv.left_charging)}{int(adv.right_charging)}{int(adv.case_charging)} ear={ears} "
              f"case={'both' if adv.both_in_case else ('one' if adv.one_pod_in_case else 'no')} lid={lid} "
              f"conn={adv.connection_name} {'primary=L' if adv.primary_left else 'primary=R'} {data.hex()}", flush=True)

    scanner = BleScanner(on_adv)
    print("scanning for Apple proximity advertisements (Ctrl-C to stop)…", file=sys.stderr)
    await scanner.start()
    try:
        await asyncio.sleep(args.timeout if args.timeout > 0 else 3600 * 24)
    except asyncio.CancelledError:
        pass
    finally:
        await scanner.stop()
    print(f"{scanner.packets} packets", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    oneshot = any([args.battery, args.json, args.watch, args.scan, args.devices, args.bind, args.unbind,
                   args.mode, args.keys, args.connect, args.disconnect])
    setup_logging(args.verbose, to_file=not oneshot)
    settings = Settings.load()
    if not oneshot:
        import os

        if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
            # Wayland compositors ignore window positions; through XWayland the popup can sit by the tray.
            os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
        from .gui.app import run_gui

        return run_gui(settings, force_setup=args.setup or args.preview == "wizard", preview=args.preview,
                       snapshot=args.snapshot)
    try:
        if args.scan:
            return asyncio.run(_run_scan(args, settings))
        return asyncio.run(_run_oneshot(args, settings))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
