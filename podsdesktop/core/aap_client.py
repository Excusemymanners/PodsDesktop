"""An AAP session over a Linux L2CAP socket (PSM 0x1001), driven by asyncio.

No root, no kernel patch and no BlueZ ``Experimental`` flag is needed: the kernel lets an
ordinary user open an L2CAP SEQPACKET socket to a bonded device. The pods close the channel
themselves when they are put away, which shows up as a recv() error; the caller reconnects.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import sys
from typing import Awaitable, Callable

from ..protocol import aap

log = logging.getLogger(__name__)

EventCallback = Callable[[aap.Event], Awaitable[None] | None]


class AapError(Exception):
    pass


def aap_supported() -> bool:
    return sys.platform.startswith("linux") and hasattr(socket, "AF_BLUETOOTH")


class AapSession:
    def __init__(self, address: str, on_event: EventCallback):
        self.address = address
        self._on_event = on_event
        self._sock: socket.socket | None = None
        self.connected = False
        self.closed_reason: str | None = None

    async def connect(self, timeout: float = 8.0) -> None:
        if not aap_supported():
            raise AapError("AAP needs Linux with AF_BLUETOOTH sockets")
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        sock.setblocking(False)
        try:
            await asyncio.wait_for(loop.sock_connect(sock, (self.address, aap.PSM)), timeout)
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise AapError(f"L2CAP connect to {self.address} failed: {exc}") from exc
        self._sock = sock
        self.connected = True
        log.info("AAP channel open to %s", self.address)
        for pkt in (aap.HANDSHAKE, aap.SET_SPECIFIC_FEATURES, aap.REQUEST_NOTIFICATIONS):
            await self.send(pkt)
            await asyncio.sleep(0.15)

    async def send(self, data: bytes) -> None:
        if not self._sock:
            raise AapError("not connected")
        loop = asyncio.get_running_loop()
        try:
            await loop.sock_sendall(self._sock, data)
        except OSError as exc:
            raise AapError(f"send failed: {exc}") from exc
        log.debug("AAP -> %s", data.hex())

    async def request_keys(self) -> None:
        await self.send(aap.REQUEST_PROXIMITY_KEYS)

    async def run(self) -> None:
        """Receive until the pods close the channel. Raises AapError on loss."""
        if not self._sock:
            raise AapError("not connected")
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    data = await loop.sock_recv(self._sock, 4096)
                except OSError as exc:
                    raise AapError(f"channel closed: {exc}") from exc
                if not data:
                    raise AapError("channel closed by device")
                log.debug("AAP <- %s", data.hex())
                event = aap.parse(data)
                if event is None:
                    continue
                try:
                    result = self._on_event(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:  # noqa: BLE001
                    log.exception("AAP event handler failed")
        finally:
            await self.close()

    async def close(self) -> None:
        self.connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
