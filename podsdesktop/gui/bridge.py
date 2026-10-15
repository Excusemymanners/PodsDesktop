"""Runs the asyncio engine on its own thread and relays its events as Qt signals."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Coroutine

from PySide6.QtCore import QObject, Signal

from ..core.engine import Engine

log = logging.getLogger(__name__)


class EngineBridge(QObject):
    event = Signal(str, object)

    def __init__(self, engine: Engine, parent: QObject | None = None):
        super().__init__(parent)
        self.engine = engine
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._run, name="podsdesktop-engine", daemon=True)
        engine.subscribe(self._on_engine_event)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self.engine.run())
        except Exception:  # noqa: BLE001
            log.exception("engine crashed")
            self.event.emit("error", "engine crashed, see the log")
        finally:
            self._loop.close()

    def _on_engine_event(self, name: str, payload) -> None:
        # called on the engine thread; the signal is queued onto the GUI thread
        self.event.emit(name, payload)

    def call(self, coro: Coroutine) -> None:
        """Schedule a coroutine on the engine loop from the GUI thread."""
        if self._loop is None or self._loop.is_closed():
            coro.close()
            return
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.add_done_callback(self._log_failure)

    @staticmethod
    def _log_failure(future) -> None:
        try:
            future.result()
        except Exception:  # noqa: BLE001
            log.exception("engine call failed")

    def stop(self, timeout: float = 5.0) -> None:
        self.engine.stop_threadsafe()
        self._thread.join(timeout)
