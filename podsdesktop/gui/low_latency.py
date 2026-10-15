"""Keep the audio output awake by looping silence, so short sounds are not clipped
while the Bluetooth sink wakes up. Uses Qt Multimedia (works on Linux and Windows)."""

from __future__ import annotations

import logging
import struct
import wave

from PySide6.QtCore import QObject, QUrl

from ..core.settings import state_dir

log = logging.getLogger(__name__)


def _silence_file():
    path = state_dir() / "silence.wav"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(struct.pack("<h", 0) * 2 * 48000 * 2)  # two seconds
    return path


class SilenceKeeper(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._output = None
        self.active = False

    def start(self) -> None:
        if self.active:
            return
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._output = QAudioOutput(self)
            self._output.setVolume(0.02)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._output)
            self._player.setSource(QUrl.fromLocalFile(str(_silence_file())))
            self._player.setLoops(QMediaPlayer.Infinite)
            self._player.play()
            self.active = True
            log.info("low latency: silence loop started")
        except Exception as exc:  # noqa: BLE001
            log.warning("low latency unavailable: %s", exc)

    def stop(self) -> None:
        if not self.active:
            return
        try:
            self._player.stop()
        except Exception:  # noqa: BLE001
            pass
        self._player = self._output = None
        self.active = False
        log.info("low latency: silence loop stopped")
