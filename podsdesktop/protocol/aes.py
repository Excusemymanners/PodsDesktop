"""AES-128 single-block encryption/decryption in pure Python.

Only 16-byte blocks are ever processed (BLE address hashes and the 16-byte encrypted
tail of the proximity advertisement), so a dependency on a crypto library is not worth it.
Not constant-time; nothing here protects secrets against a local attacker.
"""

from __future__ import annotations

SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16"
)
INV_SBOX = bytes(SBOX.index(i) for i in range(256))
RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _xtime(a: int) -> int:
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def _mul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result


def _expand_key(key: bytes) -> list[list[int]]:
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    words = [list(key[i : i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = list(words[i - 1])
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= RCON[i // 4 - 1]
        words.append([words[i - 4][j] ^ temp[j] for j in range(4)])
    return [sum(words[4 * r : 4 * r + 4], []) for r in range(11)]


def _add_round_key(state: list[int], round_key: list[int]) -> list[int]:
    return [a ^ b for a, b in zip(state, round_key)]


def _shift_rows(s: list[int]) -> list[int]:
    out = list(s)
    for r in range(1, 4):
        for c in range(4):
            out[r + 4 * c] = s[r + 4 * ((c + r) % 4)]
    return out


def _inv_shift_rows(s: list[int]) -> list[int]:
    out = list(s)
    for r in range(1, 4):
        for c in range(4):
            out[r + 4 * ((c + r) % 4)] = s[r + 4 * c]
    return out


def _mix_columns(s: list[int]) -> list[int]:
    out = list(s)
    for c in range(4):
        a0, a1, a2, a3 = s[4 * c : 4 * c + 4]
        out[4 * c + 0] = _mul(a0, 2) ^ _mul(a1, 3) ^ a2 ^ a3
        out[4 * c + 1] = a0 ^ _mul(a1, 2) ^ _mul(a2, 3) ^ a3
        out[4 * c + 2] = a0 ^ a1 ^ _mul(a2, 2) ^ _mul(a3, 3)
        out[4 * c + 3] = _mul(a0, 3) ^ a1 ^ a2 ^ _mul(a3, 2)
    return out


def _inv_mix_columns(s: list[int]) -> list[int]:
    out = list(s)
    for c in range(4):
        a0, a1, a2, a3 = s[4 * c : 4 * c + 4]
        out[4 * c + 0] = _mul(a0, 14) ^ _mul(a1, 11) ^ _mul(a2, 13) ^ _mul(a3, 9)
        out[4 * c + 1] = _mul(a0, 9) ^ _mul(a1, 14) ^ _mul(a2, 11) ^ _mul(a3, 13)
        out[4 * c + 2] = _mul(a0, 13) ^ _mul(a1, 9) ^ _mul(a2, 14) ^ _mul(a3, 11)
        out[4 * c + 3] = _mul(a0, 11) ^ _mul(a1, 13) ^ _mul(a2, 9) ^ _mul(a3, 14)
    return out


def encrypt_block(key: bytes, block: bytes) -> bytes:
    """AES-128 encryption of exactly one 16-byte block (big-endian byte order)."""
    if len(block) != 16:
        raise ValueError("block must be 16 bytes")
    round_keys = _expand_key(key)
    state = _add_round_key(list(block), round_keys[0])
    for r in range(1, 10):
        state = [SBOX[b] for b in state]
        state = _mix_columns(_shift_rows(state))
        state = _add_round_key(state, round_keys[r])
    state = [SBOX[b] for b in state]
    state = _add_round_key(_shift_rows(state), round_keys[10])
    return bytes(state)


def decrypt_block(key: bytes, block: bytes) -> bytes:
    """AES-128 decryption of exactly one 16-byte block."""
    if len(block) != 16:
        raise ValueError("block must be 16 bytes")
    round_keys = _expand_key(key)
    state = _add_round_key(list(block), round_keys[10])
    for r in range(9, 0, -1):
        state = _inv_shift_rows(state)
        state = [INV_SBOX[b] for b in state]
        state = _add_round_key(state, round_keys[r])
        state = _inv_mix_columns(state)
    state = _inv_shift_rows(state)
    state = [INV_SBOX[b] for b in state]
    return bytes(_add_round_key(state, round_keys[0]))


def ble_ah(irk_big_endian: bytes, prand: bytes) -> bytes:
    """Bluetooth Core ``ah(k, r)``: 24-bit hash used in resolvable private addresses.

    ``irk_big_endian`` is the IRK as a big-endian 128-bit number, ``prand`` the 3 most
    significant address bytes (MSB first). Returns the 3 hash bytes (MSB first).
    """
    if len(prand) != 3:
        raise ValueError("prand must be 3 bytes")
    return encrypt_block(irk_big_endian, bytes(13) + prand)[-3:]


def parse_address(address: str) -> bytes:
    """``"AA:BB:CC:DD:EE:FF"`` -> 6 bytes, most significant first."""
    parts = address.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"not a Bluetooth address: {address!r}")
    return bytes(int(p, 16) for p in parts)


def resolve_rpa(irk_as_transmitted: bytes, address: str) -> bool:
    """True when ``address`` is a resolvable private address generated from this IRK.

    AirPods hand out their IRK over AAP (opcode 0x31) least-significant byte first,
    exactly as it travels over the air, which is why the key is reversed here.
    """
    if len(irk_as_transmitted) != 16:
        return False
    try:
        addr = parse_address(address)
    except ValueError:
        return False
    if (addr[0] & 0xC0) != 0x40:  # top two bits 0b01 mark a resolvable private address
        return False
    irk_big_endian = bytes(reversed(irk_as_transmitted))
    return ble_ah(irk_big_endian, addr[:3]) == addr[3:]


def decrypt_proximity_payload(enc_key: bytes, payload: bytes) -> bytes:
    """Decrypt the 16-byte tail of a proximity advertisement with the AAP ``ENC_KEY``.

    Apple encrypts it with AES-128 in CBC mode with a zero IV; for one block that is a
    plain ECB decryption with the key bytes used as received.
    """
    if len(enc_key) != 16 or len(payload) != 16:
        raise ValueError("key and payload must both be 16 bytes")
    return decrypt_block(enc_key, payload)
