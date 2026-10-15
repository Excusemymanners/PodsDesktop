"""Console + rotating file logging."""

from __future__ import annotations

import logging
import logging.handlers
import sys

from .core.settings import state_dir


def setup_logging(verbose: bool = False, to_file: bool = True) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)
    if to_file:
        try:
            state_dir().mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(state_dir() / "podsdesktop.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
            handler.setLevel(logging.DEBUG if verbose else logging.INFO)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
            root.addHandler(handler)
        except OSError:
            pass
    for noisy in ("bleak", "dbus_fast", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING if not verbose else logging.INFO)
