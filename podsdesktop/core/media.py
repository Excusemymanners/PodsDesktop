"""Pause and resume whatever is playing when the pods leave or re-enter the ears.

Linux: every MPRIS player on the session bus (Spotify, browsers, VLC, mpv…) through dbus-fast.
Windows: the Global System Media Transport Controls (``winrt-Windows.Media.Control``), with a
media-key fallback when that package is missing.
"""

from __future__ import annotations

import asyncio
import logging
import sys

log = logging.getLogger(__name__)


class MediaController:
    async def pause_playing(self) -> list[str]:
        """Pause everything that is playing; return handles to resume later."""
        return []

    async def resume(self, handles: list[str]) -> None:
        pass


class MprisController(MediaController):
    PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"

    def __init__(self):
        self._bus = None

    async def _get_bus(self):
        if self._bus is None:
            from dbus_fast import BusType
            from dbus_fast.aio import MessageBus

            self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        return self._bus

    async def _players(self) -> list[str]:
        from dbus_fast import Message

        bus = await self._get_bus()
        reply = await bus.call(Message(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                                       interface="org.freedesktop.DBus", member="ListNames"))
        return [n for n in reply.body[0] if n.startswith("org.mpris.MediaPlayer2.")]

    async def _status(self, name: str) -> str:
        from dbus_fast import Message, MessageType

        bus = await self._get_bus()
        reply = await bus.call(Message(destination=name, path="/org/mpris/MediaPlayer2",
                                       interface="org.freedesktop.DBus.Properties", member="Get",
                                       signature="ss", body=[self.PLAYER_IFACE, "PlaybackStatus"]))
        if reply.message_type == MessageType.ERROR:
            return ""
        value = reply.body[0]
        return value.value if hasattr(value, "value") else value

    async def _call(self, name: str, member: str) -> None:
        from dbus_fast import Message

        bus = await self._get_bus()
        await bus.call(Message(destination=name, path="/org/mpris/MediaPlayer2", interface=self.PLAYER_IFACE, member=member))

    async def pause_playing(self) -> list[str]:
        paused = []
        try:
            for name in await self._players():
                if await self._status(name) == "Playing":
                    await self._call(name, "Pause")
                    paused.append(name)
        except Exception as exc:  # noqa: BLE001
            log.warning("MPRIS pause failed: %s", exc)
        if paused:
            log.info("paused %s", ", ".join(paused))
        return paused

    async def resume(self, handles: list[str]) -> None:
        for name in handles:
            try:
                if await self._status(name) == "Paused":
                    await self._call(name, "Play")
                    log.info("resumed %s", name)
            except Exception as exc:  # noqa: BLE001
                log.warning("MPRIS resume failed for %s: %s", name, exc)


class WindowsMediaController(MediaController):
    def __init__(self):
        self._sessions: dict[str, object] = {}

    async def _manager(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager

        return await Manager.request_async()

    async def pause_playing(self) -> list[str]:
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status

            manager = await self._manager()
            paused = []
            for session in manager.get_sessions():
                if session.get_playback_info().playback_status == Status.PLAYING:
                    if await session.try_pause_async():
                        key = session.source_app_user_model_id
                        self._sessions[key] = session
                        paused.append(key)
            return paused
        except ImportError:
            return await self._media_key_fallback()
        except Exception as exc:  # noqa: BLE001
            log.warning("GSMTC pause failed: %s", exc)
            return []

    async def resume(self, handles: list[str]) -> None:
        for key in handles:
            session = self._sessions.pop(key, None)
            if session is None:
                if key == "media-key":
                    await self._media_key_fallback()
                continue
            try:
                await session.try_play_async()
            except Exception as exc:  # noqa: BLE001
                log.warning("GSMTC play failed: %s", exc)

    async def _media_key_fallback(self) -> list[str]:
        try:
            import ctypes

            VK_MEDIA_PLAY_PAUSE = 0xB3
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 2, 0)
            return ["media-key"]
        except Exception as exc:  # noqa: BLE001
            log.warning("media key fallback failed: %s", exc)
            return []


def create_media_controller() -> MediaController:
    if sys.platform.startswith("linux"):
        return MprisController()
    if sys.platform == "win32":
        return WindowsMediaController()
    return MediaController()
