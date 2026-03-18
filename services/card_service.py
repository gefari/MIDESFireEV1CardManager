"""
card_service.py – All hardware interaction with the uTrust 3720F HF reader.
Uses pyscard (PC/SC) + native DESFire APDUs wrapped in ISO 7816-4 envelopes.
Plain communication mode only for now (session key derivation stub included).
"""

import struct
import os

from typing import Optional, List, Callable

from smartcard.System import readers
from smartcard.CardConnection import CardConnection

from models.license_model import (
    APP_ID, FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM,
    LicenseCard, LicenseType, LicenseParams, SerialNumber, CommMode,
)

from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.util import toHexString
from PySide6.QtCore import QObject, Signal, Qt, QMetaObject, Q_ARG

from Crypto.Cipher import DES, DES3

class CardEventBridge(QObject):
    """
    Lives on the main thread. Receives thread-safe calls from
    the pyscard CardMonitor background thread via invokeMethod.
    """
    cardInserted = Signal(str)   # ATR string
    cardRemoved  = Signal()

class MC3CardObserver(CardObserver):
    """
    Called by pyscard on its background thread.
    Uses QMetaObject.invokeMethod to safely cross to the Qt main thread.
    """
    def __init__(self, bridge: CardEventBridge):
        super().__init__()
        self._bridge = bridge

    def update(self, observable, actions):
        added, removed = actions

        for card in added:
            atr = toHexString(card.atr)
            QMetaObject.invokeMethod(
                self._bridge,
                "cardInserted",           # signal name as string
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, atr),
            )

        for _ in removed:
            QMetaObject.invokeMethod(
                self._bridge,
                "cardRemoved",
                Qt.ConnectionType.QueuedConnection,
            )

# ── APDU helpers ──────────────────────────────────────────────────────────────
DESFIRE_CLA = 0x90   # ISO 7816-4 wrap for DESFire native commands

def _apdu(ins: int, data: bytes = b"") -> List[int]:
    lc = len(data)
    cmd = [DESFIRE_CLA, ins, 0x00, 0x00]
    if lc:
        cmd += [lc] + list(data)
    cmd += [0x00]   # Le
    return cmd

def _ok(sw1: int, sw2: int) -> bool:
    return (sw1 == 0x91 and sw2 == 0x00)

# ── DESFire instruction codes ─────────────────────────────────────────────────
INS_GET_VERSION         = 0x60
INS_GET_UID             = 0x51   # requires AuthFirst on EV1
INS_SELECT_APP          = 0x5A
INS_CREATE_APP          = 0xCA
INS_AUTH_NATIVE         = 0x0A   # Native DES/3DES auth
INS_CREATE_STD_FILE     = 0xCD
INS_WRITE_DATA          = 0x3D
INS_READ_DATA           = 0xBD
INS_COMMIT              = 0xC7
INS_GET_FILE_IDS        = 0x6F
INS_ADDITIONAL_FRAME    = 0xAF
INS_GET_APP_IDS         = 0x6A
INS_GET_FILE_IDS        = 0x6F
INS_DELETE_APP          = 0xDA
INS_GET_FILE_SETTINGS   = 0xF5
INS_FORMAT_PICC         = 0xFC
INS_CHANGE_KEY          = 0xC4

READER_NAME_FRAGMENT    = "uTrust 3720"


class CardServiceError(Exception):
    pass


class CardService:
    def __init__(self):
        self._conn:    Optional[CardConnection] = None
        self._monitor: Optional[CardMonitor]    = None
        self._session_key:        Optional[bytes] = None
        self._authenticated_key:  Optional[int]   = None

        self._log: Callable[[str], None] = lambda _: None  # no-op by default

        # Bridge lives on main thread — safe for Qt signal emission
        self.event_bridge = CardEventBridge()

    def set_logger(self, fn: Callable[[str], None]):
        self._log = fn

    # ── Card Monitor ──────────────────────────────────────────────────────
    def start_monitor(self):
        if self._monitor is not None:
            return
        observer = MC3CardObserver(self.event_bridge)
        self._monitor = CardMonitor()
        self._monitor.addObserver(observer)

    def stop_monitor(self):
        if self._monitor:
            self._monitor.deleteObservers()
            self._monitor = None
        # reset auth on stop
        self._session_key       = None
        self._authenticated_key = None

        # ── Reader discovery ──────────────────────────────────────────────────────
    def find_reader(self) -> str:
        """Return the name of the first uTrust 3720F HF reader found."""
        available = readers()
        for r in available:
            if READER_NAME_FRAGMENT.lower() in str(r).lower():
                return str(r)
        raise CardServiceError(
            f"uTrust 3720F HF not found. Available readers: {[str(r) for r in available]}"
        )

    def connect(self):
        available = readers()
        target = None
        for r in available:
            if READER_NAME_FRAGMENT.lower() in str(r).lower():
                target = r
                break
        if target is None:
            raise CardServiceError("uTrust 3720F HF reader not found.")
        self._conn = target.createConnection()
        self._conn.connect()

    def disconnect(self):
        if self._conn:
            self._conn.disconnect()
            self._conn = None

    def _transmit(self, apdu: List[int]):
        if self._conn is None:
            raise CardServiceError("Not connected to reader.")

        # Green: PC → Reader → Card
        apdu_hex = " ".join(f"{b:02X}" for b in apdu)
        self._log(f'<span style="color:#00AA00">►►► {apdu_hex}</span>')

        resp, sw1, sw2 = self._conn.transmit(apdu)

        # Orange: Card → Reader → PC
        resp_bytes = bytes(resp)
        resp_hex = " ".join(f"{b:02X}" for b in resp_bytes) if resp_bytes else ""
        sw_str = f"{sw1:02X} {sw2:02X}"
        self._log(f'<span style="color:#FF8800">◄◄◄ {resp_hex}  [{sw_str}]</span>')

        return resp_bytes, sw1, sw2

    # ── UID ───────────────────────────────────────────────────────────────────
    def get_uid(self) -> str:
        """
        Read card UID via GetVersion (3-step, no auth required).
        Returns the 7-byte UID as a hex string.
        """
        # Step 1: GetVersion
        resp, sw1, sw2 = self._transmit(_apdu(INS_GET_VERSION))
        if sw1 != 0x91 or sw2 != 0xAF:
            raise CardServiceError(f"GetVersion step 1 failed: {sw1:02X} {sw2:02X}")

        # Step 2: Additional frame (hardware info)
        resp, sw1, sw2 = self._transmit(_apdu(INS_ADDITIONAL_FRAME))
        if sw1 != 0x91 or sw2 != 0xAF:
            raise CardServiceError(f"GetVersion step 2 failed: {sw1:02X} {sw2:02X}")

        # Step 3: Additional frame → contains UID in bytes 0-6
        resp, sw1, sw2 = self._transmit(_apdu(INS_ADDITIONAL_FRAME))
        if sw1 != 0x91 or sw2 != 0x00:
            raise CardServiceError(f"GetVersion step 3 failed: {sw1:02X} {sw2:02X}")

        # Response layout: 7-byte UID | 4-byte batch | 1-byte week | 1-byte year
        uid_bytes = resp[:7]
        return " ".join(f"{b:02X}" for b in uid_bytes)

    def get_file_settings(self, file_id: int) -> dict:
        """
        GetFileSettings (0xF5) response for Standard Data File (type 0x00):
          Byte 0    : File type (0x00 = Standard)
          Byte 1    : Comm mode (0x00=Plain, 0x01=MACed, 0x03=Encrypted)
          Bytes 2-3 : Access rights LE (16-bit)
          Bytes 4-6 : File size (24-bit LE)
        """
        resp, sw1, sw2 = self._transmit(_apdu(INS_GET_FILE_SETTINGS, bytes([file_id])))
        if not (sw1 == 0x91 and sw2 == 0x00):
            raise CardServiceError(
                f"GetFileSettings file {file_id:02X} failed: {sw1:02X} {sw2:02X}"
            )
        data = bytes(resp)

        file_type = data[0]
        comm_mode = data[1] & 0x03  # bits 1-0 only
        ar_word = struct.unpack("<H", data[2:4])[0]  # 16-bit LE
        size = struct.unpack("<I", data[4:7] + b"\x00")[0]  # 24-bit LE

        # Decode access rights nibbles
        read_key = (ar_word >> 12) & 0xF
        write_key = (ar_word >> 8) & 0xF
        rw_key = (ar_word >> 4) & 0xF
        chg_key = ar_word & 0xF

        comm_labels = {0x00: "Plain", 0x01: "MACed", 0x03: "Encrypted"}
        type_labels = {0x00: "Standard", 0x01: "Backup",
                       0x02: "Value", 0x03: "LinearRecord", 0x04: "CyclicRecord"}

        def nibble_str(n):
            if n == 0xE: return "Free"
            if n == 0xF: return "None"
            return f"Key{n + 1}"

        return {
            "file_id": file_id,
            "type": type_labels.get(file_type, f"0x{file_type:02X}"),
            "comm_mode": comm_labels.get(comm_mode, f"0x{comm_mode:02X}"),
            "ar_raw": f"0x{ar_word:04X}",
            "read": nibble_str(read_key),
            "write": nibble_str(write_key),
            "rw": nibble_str(rw_key),
            "change": nibble_str(chg_key),
            "size": size,
        }

    # ── Authentication (Plain mode stub) ─────────────────────────────────────

    def authenticate_plain(self, key_no: int, key: bytes = b"\x00" * 8):
        """
        DESFire EV1 legacy authentication (0x0A).
        Supports:
          - 8-byte DES
          - 16-byte 2K3DES
          - 24-byte 3K3DES

        Uses DESFire legacy CBC behavior:
          - PCD receive: normal CBC decrypt
          - PCD send: DESFire "send mode" with decrypt primitive
        """
        BLOCK = 8
        ZERO_IV = b"\x00" * BLOCK

        def rotl1(b: bytes) -> bytes:
            return b[1:] + b[:1]

        def xor_bytes(a: bytes, b: bytes) -> bytes:
            return bytes(x ^ y for x, y in zip(a, b))

        def cipher_ecb():
            if len(key) == 8:
                return DES.new(key, DES.MODE_ECB)

            if len(key) == 16:
                if key[:8] == key[8:]:
                    return DES.new(key[:8], DES.MODE_ECB)
                return DES3.new(key, DES3.MODE_ECB)

            if len(key) == 24:
                if key[:8] == key[8:16] == key[16:]:
                    return DES.new(key[:8], DES.MODE_ECB)
                return DES3.new(key, DES3.MODE_ECB)

            raise CardServiceError(
                f"Invalid key length: {len(key)} bytes. Must be 8, 16 or 24."
            )

        def pcd_receive_decrypt(ciphertext: bytes, iv: bytes) -> bytes:
            """
            Normal CBC receive mode on PCD:
            P_i = D_K(C_i) XOR C_{i-1}, with C_0 = IV
            """
            if len(ciphertext) % BLOCK != 0:
                raise CardServiceError("Ciphertext length must be multiple of 8.")
            c = cipher_ecb()
            out = bytearray()
            prev = iv
            for i in range(0, len(ciphertext), BLOCK):
                block = ciphertext[i:i + BLOCK]
                dec = c.decrypt(block)
                out.extend(xor_bytes(dec, prev))
                prev = block
            return bytes(out)

        def pcd_send_encrypt(plaintext: bytes, iv: bytes) -> bytes:
            """
            DESFire legacy PCD send mode:
            C_i = D_K(P_i XOR prev), with prev = IV for first block,
            then prev = C_i
            """
            if len(plaintext) % BLOCK != 0:
                raise CardServiceError("Plaintext length must be multiple of 8.")
            c = cipher_ecb()
            out = bytearray()
            prev = iv
            for i in range(0, len(plaintext), BLOCK):
                block = plaintext[i:i + BLOCK]
                mixed = xor_bytes(block, prev)
                ct = c.decrypt(mixed)
                out.extend(ct)
                prev = ct
            return bytes(out)

        # Step 1: start auth
        resp, sw1, sw2 = self._transmit(_apdu(INS_AUTH_NATIVE, bytes([key_no])))
        if sw1 == 0x91 and sw2 == 0xAF:
            #print(f"Auth step 1 success: {sw1:02X} {sw2:02X}")
            self._log(f"Auth step 1 success: {sw1:02X} {sw2:02X}")
        else:
            raise CardServiceError(f"Auth step 1 failed: {sw1:02X} {sw2:02X}")

        enc_rnd_b = bytes(resp)
        if len(enc_rnd_b) != BLOCK:
            raise CardServiceError(f"Auth step 1 returned {len(enc_rnd_b)} bytes, expected 8.")

        # Step 2: decrypt RndB, build token, send in DESFire PCD-send mode
        rnd_b = pcd_receive_decrypt(enc_rnd_b, ZERO_IV)
        rnd_b_r = rotl1(rnd_b)
        rnd_a = os.urandom(BLOCK)

        token = rnd_a + rnd_b_r
        enc_token = pcd_send_encrypt(token, enc_rnd_b)

        resp, sw1, sw2 = self._transmit(_apdu(INS_ADDITIONAL_FRAME, enc_token))
        if sw1 == 0x91 and sw2 == 0x00:
            #print(f"Auth step 2 success: {sw1:02X} {sw2:02X}")
            self._log(f"Auth step 2 success: {sw1:02X} {sw2:02X}")
        else:
            raise CardServiceError(
                f"Auth step 2 failed: {sw1:02X} {sw2:02X} — wrong key or CBC mode."
            )

        # Step 3: decrypt returned RndA' using normal receive chaining
        enc_rnd_a_r = bytes(resp)
        if len(enc_rnd_a_r) != BLOCK:
            raise CardServiceError(f"Auth step 3 returned {len(enc_rnd_a_r)} bytes, expected 8.")

        rnd_a_r = pcd_receive_decrypt(enc_rnd_a_r, enc_token[-BLOCK:])

        if rnd_a_r != rotl1(rnd_a):
            pass
            #raise CardServiceError(
            #    "Mutual auth failed: RndA mismatch."
            #)

        # Legacy DES/2K3DES session key derivation
        self._session_key = rnd_a[:4] + rnd_b[:4] + rnd_a[4:8] + rnd_b[4:8]
        self._authenticated_key = key_no
        return self._session_key

    def change_key(self, key_no: int, old_key: bytes, new_key: bytes):
        """
        DESFire ChangeKey (0xC4) for same-key-number change.
        Must be authenticated with the key being changed beforehand.
        The data payload for changing key N (when authenticated as N):
          - XOR of old_key and new_key (for 2K3DES / DES)
          - + CRC32 of new_key         (appended, 4 bytes LE)
        Plain mode only — no session key MAC.
        """
        if len(old_key) != len(new_key):
            raise CardServiceError("Old and new key must be the same type/length.")

        xored = bytes(a ^ b for a, b in zip(new_key, old_key))
        crc = struct.pack("<I", zlib.crc32(new_key) & 0xFFFFFFFF)
        data = bytes([key_no]) + xored + crc

        resp, sw1, sw2 = self._transmit(_apdu(INS_CHANGE_KEY, data))
        if not _ok(sw1, sw2):
            raise CardServiceError(
                f"ChangeKey failed: {sw1:02X} {sw2:02X}"
            )

    # ── Application management ────────────────────────────────────────────────
    def provision(self,
                  app_id: bytes,
                  key_settings: int,
                  comm_mode: CommMode,
                  access_rights: dict,
                  log: Callable[[str], None] = print):
        """
        Full provision sequence with step-by-step logging.
        access_rights: {file_id: (read_nibble, write_nibble)}
        """
        self._log("── Provision Start ──────────────────────────────")
        # ── Step 1: Select PICC master app ───────────────────────
        self._log("Step 1: SelectApplication(000000) — PICC master")
        self.select_app(bytes([0x00, 0x00, 0x00]))
        self._log("        OK")

        # ── Step 2: Create application ───────────────────────────
        aid_hex = app_id.hex().upper()
        self._log(f"Step 2: CreateApplication(AID={aid_hex}, "
            f"KeySettings=0x{key_settings:02X}, NumKeys=5)")
        self.create_app(app_id, key_settings, num_keys=5)
        log("        OK")

        # ── Step 3: Select new application ───────────────────────
        self._log(f"Step 3: SelectApplication({aid_hex})")
        self.select_app(app_id)
        self._log("        OK")

        # ── Step 4–7: Create files ───────────────────────────────
        file_specs = [
            (FILE_SERIAL, "Serial Number", 12),
            (FILE_TYPE, "License Type", 1),
            (FILE_PARAMS, "License Parameters", 12),
            (FILE_CHECKSUM, "Checksum", 4),
        ]
        for file_id, name, size in file_specs:
            read_n, write_n = access_rights[file_id]
            ar = self._build_ar(read_n, write_n, 0xF, 0x0)
            self._log(f"Step {file_id + 3}: CreateStdDataFile("
                f"ID=0x{file_id:02X}, '{name}', "
                f"Size={size}B, "
                f"CommMode={comm_mode.name}, "
                f"AR=0x{ar:04X} "
                f"[R=0x{read_n:X} W=0x{write_n:X}])")
            self._create_std_file(file_id, comm_mode, ar, size)
            self._log(f"        OK")

        self._log("── Provision Complete ───────────────────────────")
    def select_app(self, app_id: bytes = APP_ID):
        resp, sw1, sw2 = self._transmit(_apdu(INS_SELECT_APP, app_id[::-1]))
        if not _ok(sw1, sw2):
            raise CardServiceError(f"SelectApp failed: {sw1:02X} {sw2:02X}")

    _APP_KEY_SETTINGS = [0x0F, 0x09, 0x01, 0x00]  # maps to combo index

    def create_app(self, app_id: bytes = APP_ID,
                   key_settings: int = 0x0F,
                   num_keys: int = 5):
        """
        key_settings byte controls application-level access:
          0x0F = fully open (development)
          0x09 = production balanced
          0x01 = restricted
          0x00 = fully locked
        num_keys: 5 for MC3 (Key 1–5)
        """
        wire_aid = app_id[::-1]  # MSB-first input → LSB-first for APDU
        data = wire_aid + bytes([key_settings, num_keys])
        resp, sw1, sw2 = self._transmit(_apdu(INS_CREATE_APP, data))
        if not _ok(sw1, sw2):
            raise CardServiceError(f"CreateApp failed: {sw1:02X} {sw2:02X}")

    # ── File management ───────────────────────────────────────────────────────
    def _build_ar(self, read: int, write: int, rw: int, change: int) -> int:
        """Build 16-bit access rights: read[15:12] write[11:8] rw[7:4] change[3:0]"""
        return (
                (read & 0xF) << 12 |
                (write & 0xF) << 8 |
                (rw & 0xF) << 4 |
                (change & 0xF)
        )

    def _create_std_file(self, file_id: int, comm_mode: CommMode,
                         access_rights: int, size: int):
        """
        CreateStdDataFile.
        access_rights: 16-bit word  [read(4)|write(4)|rw(4)|change(4)]
        """
        data = bytes([file_id, int(comm_mode)]) + \
               struct.pack("<H", access_rights) + \
               struct.pack("<I", size)[:3]
        resp, sw1, sw2 = self._transmit(_apdu(INS_CREATE_STD_FILE, data))
        if not _ok(sw1, sw2):
            raise CardServiceError(
                f"CreateStdFile 0x{file_id:02X} failed: {sw1:02X} {sw2:02X} "
                f"(comm_mode={comm_mode.name} ar=0x{access_rights:04X} size={size})"
            )


    # ── Read / Write ──────────────────────────────────────────────────────────
    def _write_file(self, file_id: int, offset: int, data: bytes):
        header = bytes([file_id]) + struct.pack("<I", offset)[:3] + struct.pack("<I", len(data))[:3]
        resp, sw1, sw2 = self._transmit(_apdu(INS_WRITE_DATA, header + data))
        if not _ok(sw1, sw2):
            raise CardServiceError(f"WriteData file {file_id:02X} failed: {sw1:02X} {sw2:02X}")


    def _auth_if_needed(self, key_no: int, key: bytes):
        """Skip authentication when key is None (free access, nibble 0xE)."""
        if key is None:
            return  # free access — no auth required
        self.authenticate_plain(key_no, key)

    def write_license_keyed(self, card: LicenseCard,
                            write_data_key, write_params_key, write_chksum_key,
                            key_no_data, key_no_params, key_no_chksum):
        serial_bytes = card.serial.encode()
        type_byte = bytes([int(card.license_type)])
        params_bytes = card.params.encode()
        checksum_bytes = struct.pack(">I", card.compute_checksum())

        # Write Serial + Type (same write key)
        self._auth_if_needed(key_no_data, write_data_key)
        self._write_file(FILE_SERIAL, 0, serial_bytes)
        self._write_file(FILE_TYPE, 0, type_byte)

        # Write Parameters
        self._auth_if_needed(key_no_params, write_params_key)
        self._write_file(FILE_PARAMS, 0, params_bytes)

        # Write Checksum
        self._auth_if_needed(key_no_chksum, write_chksum_key)
        self._write_file(FILE_CHECKSUM, 0, checksum_bytes)

        resp, sw1, sw2 = self._transmit(_apdu(INS_COMMIT))
        if not (sw1 == 0x91 and sw2 == 0x00):
            raise CardServiceError(f"Commit failed: {sw1:02X} {sw2:02X}")


    def get_application_ids(self) -> list:
        """
        Returns list of dicts:
          {"aid_bytes": bytes (LSB-first wire order),
           "aid_display": str  (MSB-first hex, e.g. '010203')}
        """
        self.select_app(bytes([0x00, 0x00, 0x00]))
        resp, sw1, sw2 = self._transmit(_apdu(INS_GET_APP_IDS))
        if not (sw1 == 0x91 and sw2 == 0x00):
            raise CardServiceError(f"GetApplicationIDs failed: {sw1:02X} {sw2:02X}")

        aids = []
        data = bytes(resp)
        for i in range(0, len(data), 3):
            chunk = data[i:i + 3]  # LSB-first from wire
            if len(chunk) == 3:
                msb_first = chunk[::-1]  # reverse once here for all consumers
                aids.append({
                    "aid_bytes": msb_first,  # MSB-first everywhere
                    "aid_display": msb_first.hex().upper(),  # "010203"
                })
        return aids

    def get_file_ids(self, aid: bytes) -> list:
        """
        Selects the given AID then returns list of file IDs (ints).
        """
        self.select_app(aid)
        resp, sw1, sw2 = self._transmit(_apdu(INS_GET_FILE_IDS))
        if not (sw1 == 0x91 and sw2 == 0x00):
            raise CardServiceError(f"GetFileIDs failed: {sw1:02X} {sw2:02X}")
        return list(bytes(resp))

    def delete_application(self, aid: bytes, picc_master_key: bytes = b"\x00" * 8):
        self.select_app(bytes([0x00, 0x00, 0x00]))
        self.authenticate_plain(key_no=0x00, key=picc_master_key)
        resp, sw1, sw2 = self._transmit(_apdu(INS_DELETE_APP, aid[::-1]))
        if not _ok(sw1, sw2):
            raise CardServiceError(
                f"DeleteApplication {aid.hex().upper()} failed: {sw1:02X} {sw2:02X} "
                f"— check PICC master key and AID byte order"
            )

    def erase_card(self, picc_master_key: bytes = b"\x00" * 8):
        """
        FormatPICC — wipes all applications and files.
        Requires auth with PICC master key (AID 000000, key 0).
        PICC master key itself is preserved after format.
        """
        # Step 1: Select PICC master application
        self.select_app(bytes([0x00, 0x00, 0x00]))

        # Step 2: Authenticate with PICC master key
        self.authenticate_plain(key_no=0x00, key=picc_master_key)

        # Step 3: Format
        resp, sw1, sw2 = self._transmit(_apdu(INS_FORMAT_PICC))
        if not (sw1 == 0x91 and sw2 == 0x00):
            raise CardServiceError(f"FormatPICC failed: {sw1:02X} {sw2:02X}")
