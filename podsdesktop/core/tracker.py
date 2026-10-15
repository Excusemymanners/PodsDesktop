"""Turns a stream of proximity advertisements into one picture of *our* AirPods.

Two problems make this harder than it looks:

* AirPods rotate their random BLE address every ~15 minutes, so the address alone cannot
  tell our pair from a colleague's.  With the IRK obtained over AAP the address becomes
  *resolvable* and the answer is exact; without it we fall back to continuity heuristics
  (same model, signal floor, battery and RSSI must not jump between consecutive packets).
* One pair shows up as one or two advertisers (each pod has its own radio, the case has
  none). Both are merged, freshest data wins per component.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from ..protocol import aes
from ..protocol.proximity import CONN_DISCONNECTED, ExactBattery, ProximityAdvert

log = logging.getLogger(__name__)

LOST_AFTER = 10.0        # seconds without any packet -> device gone
SIDE_STALE_AFTER = 10.0  # seconds without packets from one pod -> drop that pod's data
MAX_BATTERY_JUMP = 10    # percent, between consecutive packets of the same side
MAX_RSSI_JUMP = 50       # dBm

OURS = "ours"
MAYBE = "maybe"
FOREIGN = "foreign"


class IdentityFilter:
    """Decides whether an advertisement could come from the bound device."""

    def __init__(self, irk: bytes | None = None, model_id: int | None = None, rssi_min: int = -80):
        self.irk = irk
        self.model_id = model_id
        self.rssi_min = rssi_min
        self.bound_connected = False

    def classify(self, address: str, rssi: int | None, adv: ProximityAdvert) -> str:
        if self.irk:
            return OURS if aes.resolve_rpa(self.irk, address) else FOREIGN
        if self.model_id is not None and adv.model_id != self.model_id:
            return FOREIGN
        if rssi is not None and rssi < self.rssi_min:
            return FOREIGN
        # Our pods, while connected to this computer, never advertise "disconnected".
        if self.bound_connected and adv.connection_state == CONN_DISCONNECTED:
            return FOREIGN
        return MAYBE


@dataclass
class Observation:
    address: str
    rssi: int | None
    adv: ProximityAdvert
    seen: float
    exact: ExactBattery | None = None


@dataclass
class BleSnapshot:
    model_id: int
    left_level: int | None = None
    right_level: int | None = None
    case_level: int | None = None
    left_charging: bool = False
    right_charging: bool = False
    case_charging: bool = False
    left_in_ear: bool = False
    right_in_ear: bool = False
    both_in_case: bool = False
    lid_open: bool | None = None
    connection_state: int = CONN_DISCONNECTED
    rssi: int | None = None
    exact: bool = False
    identified: bool = False
    seen: float = 0.0
    addresses: tuple[str, ...] = field(default_factory=tuple)

    def __eq__(self, other: object) -> bool:  # ignore timestamps/rssi when comparing
        if not isinstance(other, BleSnapshot):
            return NotImplemented
        keys = ("model_id", "left_level", "right_level", "case_level", "left_charging",
                "right_charging", "case_charging", "left_in_ear", "right_in_ear",
                "both_in_case", "lid_open", "connection_state", "exact", "identified")
        return all(getattr(self, k) == getattr(other, k) for k in keys)


class BleTracker:
    def __init__(self, identity: IdentityFilter, enc_key: bytes | None = None):
        self.identity = identity
        self.enc_key = enc_key
        self.left: Observation | None = None
        self.right: Observation | None = None
        self.snapshot: BleSnapshot | None = None
        self.last_seen = 0.0

    # ---- input -------------------------------------------------------------------------
    def observe(self, address: str, rssi: int | None, adv: ProximityAdvert, now: float | None = None) -> BleSnapshot | None:
        """Feed one packet. Returns the new snapshot when something changed, else None."""
        now = time.monotonic() if now is None else now
        verdict = self.identity.classify(address, rssi, adv)
        if verdict == FOREIGN:
            return None
        if verdict == MAYBE and not self._plausible(address, rssi, adv):
            return None

        exact = None
        if self.enc_key and verdict == OURS:
            try:
                exact = adv.decrypt(self.enc_key)
            except ValueError:
                exact = None
        obs = Observation(address, rssi, adv, now, exact)
        if adv.primary_left or adv.is_headset:
            self.left = obs
        else:
            self.right = obs
        self.last_seen = now
        return self._rebuild(now, identified=(verdict == OURS))

    def tick(self, now: float | None = None) -> bool:
        """Expire stale data. Returns True when the device was just lost."""
        now = time.monotonic() if now is None else now
        changed = False
        for side in ("left", "right"):
            obs = getattr(self, side)
            if obs and now - obs.seen > SIDE_STALE_AFTER:
                setattr(self, side, None)
                changed = True
        if self.snapshot is not None and now - self.last_seen > LOST_AFTER:
            self.reset()
            return True
        if changed:
            self._rebuild(now, identified=self.snapshot.identified if self.snapshot else False)
        return False

    def reset(self) -> None:
        self.left = self.right = None
        self.snapshot = None

    # ---- internals ---------------------------------------------------------------------
    def _plausible(self, address: str, rssi: int | None, adv: ProximityAdvert) -> bool:
        side_obs = self.left if adv.primary_left else self.right
        other_obs = self.right if adv.primary_left else self.left
        for cached in (side_obs, other_obs):
            if cached and cached.adv.model_id != adv.model_id:
                log.debug("reject %s: model differs from cached", address)
                return False
        if side_obs and side_obs.address != address:
            # The address rotated (or it is another pair): batteries and signal must be close.
            for mine, theirs in ((side_obs.adv.left_battery, adv.left_battery),
                                 (side_obs.adv.right_battery, adv.right_battery),
                                 (side_obs.adv.case_battery, adv.case_battery)):
                if mine is not None and theirs is not None and abs(mine - theirs) > MAX_BATTERY_JUMP:
                    log.debug("reject %s: battery jump", address)
                    return False
            if rssi is not None and side_obs.rssi is not None and abs(rssi - side_obs.rssi) > MAX_RSSI_JUMP:
                log.debug("reject %s: rssi jump", address)
                return False
        if other_obs and rssi is not None and other_obs.rssi is not None and abs(rssi - other_obs.rssi) > MAX_RSSI_JUMP:
            log.debug("reject %s: rssi far from the other pod", address)
            return False
        return True

    def _rebuild(self, now: float, identified: bool) -> BleSnapshot | None:
        obs = [o for o in (self.left, self.right) if o is not None]
        if not obs:
            self.snapshot = None
            return None
        freshest = max(obs, key=lambda o: o.seen)
        adv = freshest.adv
        snap = BleSnapshot(model_id=adv.model_id, seen=freshest.seen, rssi=freshest.rssi,
                           identified=identified, addresses=tuple(o.address for o in obs))

        def pick(attr: str):
            # the freshest observation that actually knows this value
            for o in sorted(obs, key=lambda o: o.seen, reverse=True):
                if getattr(o.adv, attr) is not None:
                    return o
            return None

        for comp in ("left", "right", "case"):
            src = pick(f"{comp}_battery")
            if src is None:
                continue
            level = getattr(src.adv, f"{comp}_battery")
            charging = getattr(src.adv, f"{comp}_charging")
            if src.exact is not None:
                exact_level = getattr(src.exact, comp)
                if exact_level is not None:
                    level, charging = exact_level, getattr(src.exact, f"{comp}_charging")
                    snap.exact = True
            setattr(snap, f"{comp}_level", level)
            setattr(snap, f"{comp}_charging", charging)
        snap.left_in_ear = adv.left_in_ear
        snap.right_in_ear = adv.right_in_ear
        snap.both_in_case = adv.both_in_case
        lid_src = next((o for o in sorted(obs, key=lambda o: o.seen, reverse=True) if o.adv.lid_open is not None), None)
        snap.lid_open = lid_src.adv.lid_open if lid_src else None
        snap.connection_state = max(o.adv.connection_state for o in obs)
        changed = snap != self.snapshot
        self.snapshot = snap
        return snap if changed else None
