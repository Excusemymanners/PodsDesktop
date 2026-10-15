"""Protocol layer: pure Python, no platform dependencies, fully unit-tested.

* ``proximity`` – Apple Continuity "Proximity Pairing" BLE advertisement (type 0x07).
* ``aap``       – Apple Accessory Protocol over L2CAP PSM 0x1001 (battery, ear detection,
                  noise control, device metadata, BLE keys).
* ``aes``       – AES-128 single block + the Bluetooth ``ah`` address hash, used to
                  recognise our own AirPods among others and to decrypt the advert payload.
* ``models``    – Apple/Beats product id table.
"""
