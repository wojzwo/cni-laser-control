# FL-10xx-CW RS-232 protocol

Verified on **FL-1064-CW-20W** only. Other family members have not been tested. The controller uses **115200 8N1** and binary messages, not ASCII lines.

## PC request — GET / SET

| Byte(s) | Value | Meaning |
| --- | --- | --- |
| 0 | `53` | Start |
| 1 | `0A` | Length: 10 bytes |
| 2 | `00` / `01` | Channel: control / setting |
| 3 | `00` / `01` | Operation: GET / SET |
| 4–7 | 4 bytes | Unsigned 32-bit value, big-endian; zero for GET |
| 8 | 1 byte | `sum(bytes[0:8]) & 0xFF` |
| 9 | `0D` | End (already included; no extra CR/LF) |

The checksum is a **byte sum modulo 256**, not a CRC.

```text
GET control:    53 0A 00 00 00 00 00 00 5D 0D
GET setting:    53 0A 01 00 00 00 00 00 5E 0D
SET control 0:  53 0A 00 01 00 00 00 00 5E 0D
SET control 1:  53 0A 00 01 00 00 00 01 5F 0D
SET setting 1:  53 0A 01 01 00 00 00 01 60 0D
```

## Controller response

- **GET:** 10 bytes, start `41`, channel, operation `00`, four data bytes, checksum, end `0D`.
- **SET success:** `41 07 4F 4B 21 03 0D` (the observed `OK!` reply).
- **SET error:** `41 07 45 52 52 31 0D` (the documented `ERR1` reply).

The manufacturer's generic diagram lists **9 bytes** for SET acknowledgment and `53` as GET response start. Both conflict with documented examples and real replies from the tested controller: ACK frames have **7 bytes**, and GET replies start with `41`. The success ACK checksum `03` is correct: `(0x41 + 0x07 + 0x4F + 0x4B + 0x21) & 0xFF = 0x03`. The implementation matches complete known ACK frames exactly.

| Channel | GET | SET |
| --- | --- | --- |
| `00` | Software control register (`0` / `1`) | Request OFF (`0`) or ON (`1`) |
| `01` | Displayed setting (`1`–`100`) | Set displayed setting (`1`–`100`) |

The control register and an `OK!` acknowledgment do **not** independently verify optical emission or absence of light.
