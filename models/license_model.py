from dataclasses import dataclass, field
from typing import Optional
import struct, zlib
import secrets
from enum import IntEnum

from datetime import datetime

# ── Application ──────────────────────────────────────────────────────────────
APP_ID = bytes([0x01, 0x02, 0x03])          # 0x010203

# ── File IDs ─────────────────────────────────────────────────────────────────
FILE_SERIAL   = 0x01
FILE_TYPE     = 0x02
FILE_PARAMS   = 0x03
FILE_CHECKSUM = 0x04

# ── Access Keys ───────────────────────────────────────────────────────────────
KEY_APP_COMMON  = 0x00   # Key 1 – application common key
KEY_READ_DATA   = 0x01   # Key 2 – read Serial, Type, Checksum
KEY_WRITE_CHKSUM= 0x02   # Key 3 – write Checksum
KEY_WRITE_DATA  = 0x03   # Key 4 – write Serial, Type
KEY_RW_PARAMS   = 0x04   # Key 5 – read/write License Parameters
KEY_FREE        = 0xE   # DESFire free access nibble — no authentication required
KEY_NONE        = 0xF   # DESFire no access — operation denied

class KeyType(IntEnum):
    DES    = 8    # 8  bytes — 16 hex chars
    TDES2K = 16   # 16 bytes — 32 hex chars (2K3DES, default EV1)
    TDES3K = 24   # 24 bytes — 48 hex chars (3K3DES)
    AES128 = 16   # 16 bytes — 32 hex chars

KEY_TYPE_NAMES = {
    KeyType.DES:    "DES  (8 bytes — 16 hex)",
    KeyType.TDES2K: "2K3DES (16 bytes — 32 hex)",
    KeyType.TDES3K: "3K3DES (24 bytes — 48 hex)",
    KeyType.AES128: "AES-128 (16 bytes — 32 hex)",
}




# ── Communication modes ───────────────────────────────────────────────────────
class CommMode(IntEnum):
    PLAIN     = 0x00
    MACED     = 0x01
    ENCRYPTED = 0x03

# ── License types ─────────────────────────────────────────────────────────────
class LicenseType(IntEnum):
    PERPETUAL    = 0
    TIME_LIMITED = 1
    PER_USE      = 2

# File 3 sizes per license type
FILE_PARAMS_SIZE = {
    LicenseType.PERPETUAL:    1,   # 1 byte: 0x01=valid, 0x00=invalid
    LicenseType.TIME_LIMITED: 12,  # YYMMDDHHMMSS ASCII, All zeros == License Not Valid
    LicenseType.PER_USE:      4,   # uint16 num_uses, uint16 hours_per_use All zeros Not Valid
}
# ── Serial Number ─────────────────────────────────────────────────────────────
@dataclass
class SerialNumber:
    """Production timestamp encoded as YYMMDDHHMMSS (12 ASCII digits)."""
    dt: datetime = field(default_factory=datetime.utcnow)

    def encode(self) -> bytes:
        return self.dt.strftime("%y%m%d%H%M%S").encode("ascii")   # 12 bytes

    @classmethod
    def decode(cls, raw: bytes) -> "SerialNumber":
        s = raw.decode("ascii")
        dt = datetime.strptime(s, "%y%m%d%H%M%S")
        return cls(dt=dt)

    def __str__(self):
        return self.dt.strftime("%y%m%d%H%M%S")

# ── License Parameters ────────────────────────────────────────────────────────
@dataclass
class LicenseParams:
    license_type: LicenseType = LicenseType.PERPETUAL
    valid: bool = True  # Perpetual only: 0x01=valid, 0x00=invalid

    # Type 1
    expiration: Optional[datetime] = None

    # Type 2
    num_uses: int = 0          # 0-65535
    hours_per_use: int = 0     # 0-65535

    def encode(self) -> bytes:
        if self.license_type == LicenseType.PERPETUAL:
            return bytes([0x01 if self.valid else 0x00])
        elif self.license_type == LicenseType.TIME_LIMITED:
            return self.expiration.strftime("%y%m%d%H%M%S").encode("ascii")
        elif self.license_type == LicenseType.PER_USE:  # PER_USE
            return struct.pack(">HH", self.num_uses, self.hours_per_use)
        else:
            raise ValueError("Unknown license type")

    @classmethod
    def decode(cls, license_type: LicenseType, raw: bytes) -> "LicenseParams":
        if license_type == LicenseType.PERPETUAL:
            return cls(license_type=license_type)
        if license_type == LicenseType.TIME_LIMITED:
            dt = datetime.strptime(raw.decode("ascii"), "%y%m%d%H%M%S")
            return cls(license_type=license_type, expiration=dt)
        if license_type == LicenseType.PER_USE:
            n, h = struct.unpack(">HH", raw[:4])
            return cls(license_type=license_type, num_uses=n, hours_per_use=h)
        raise ValueError("Unknown license type")

# ── Full License Card Model ───────────────────────────────────────────────────
@dataclass
class LicenseCard:
    serial:       SerialNumber  = field(default_factory=SerialNumber)
    license_type: LicenseType   = LicenseType.PERPETUAL
    params:       LicenseParams = field(default_factory=LicenseParams)
    checksum:     int           = 0          # CRC-32 (stored value)
    comm_mode:    CommMode      = CommMode.PLAIN

    def compute_checksum(self) -> int:
        """CRC-32 over Serial + Type byte + Params."""
        payload  = self.serial.encode()
        payload += bytes([int(self.license_type)])
        payload += self.params.encode()
        checksum = zlib.crc32(payload) & 0xFFFF_FFFF
        return checksum

    def checksum_valid(self) -> bool:
        computed_checksum = self.compute_checksum()
        return self.checksum == computed_checksum


@dataclass
class AccessKey:
    name:     str
    key_type: KeyType = KeyType.TDES2K          # EV1 default
    key_bytes: bytes  = field(default_factory=lambda: b"\x00" * 8 + b"\xFF" * 8)

    def generate(self):
        self.key_bytes = secrets.token_bytes(int(self.key_type))

    def hex(self) -> str:
        return self.key_bytes.hex().upper()

    def expected_hex_len(self) -> int:
        return int(self.key_type) * 2

    @classmethod
    def from_hex(cls, name: str, hex_str: str, key_type: KeyType = KeyType.TDES2K):
        b = bytes.fromhex(hex_str.replace(" ", ""))
        if len(b) != int(key_type):
            raise ValueError(
                f"Expected {int(key_type)*2} hex chars for {key_type.name}, got {len(b)*2}."
            )
        return cls(name=name, key_type=key_type, key_bytes=b)

@dataclass
class KeyStore:
    """Holds the 5 application access keys for MC3."""
    keys: list = field(default_factory=lambda: [
        AccessKey(name="Key 0 – PICC Master Key"),
        AccessKey(name="Key 1 – Application Master Key"),
        AccessKey(name="Key 2 – Read Serial/Type/Checksum"),
        AccessKey(name="Key 3 – Write Checksum"),
        AccessKey(name="Key 4 – Write Serial/Type"),
        AccessKey(name="Key 5 – Read/Write Parameters"),
    ])

    def get(self, index: int) -> AccessKey:
        """index: 0-based (0=Key1 ... 4=Key5). Returns None if index == KEY_FREE."""
        if index == KEY_FREE:
            return None
        return self.keys[index]

    def key_names(self) -> list:
        """Returns key names plus a trailing 'None (Free Access)' entry."""
        return [k.name for k in self.keys] + ["None (Free Access)"]

    def key_index_to_nibble(self, index: int) -> int:
        """
        Convert combo index to DESFire access nibble.
        Combo indices 0-4 → DESFire key numbers 0-4.
        Combo index  5   → 0xE (free access).
        """
        if index == 6:
            return KEY_FREE   # 0xE
        return index