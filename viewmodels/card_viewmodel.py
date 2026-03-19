import struct
from PySide6.QtCore import QObject, Signal, Slot
from models.license_model import (
    LicenseCard, CommMode, KeyStore, KEY_FREE,
    FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM,
    LicenseType, FILE_PARAMS_SIZE,
    SerialNumber,   # ← add this
    LicenseParams
)
from services.card_service import CardService, CardServiceError
from smartcard.System import readers as list_readers


class CardViewModel(QObject):

    _APP_KEY_SETTINGS = [0x0F, 0x09, 0x01, 0x00]

    # ── Signals ───────────────────────────────────────────────────────────
    statusChanged   = Signal(str)
    errorOccurred   = Signal(str)
    cardRead        = Signal(LicenseCard)
    cardWritten     = Signal()
    uidRead         = Signal(str)
    readerFound     = Signal(str)
    authResult      = Signal(bool, str)
    keyStoreChanged = Signal()
    cardInserted    = Signal(str)
    cardRemoved     = Signal()
    provisionLog    = Signal(str)
    appsRead        = Signal(list)
    appDeleted      = Signal(str)
    logMessage      = Signal(str)
    keyChanged      = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._service   = CardService()
        self._service.set_logger(self.logMessage.emit)

        self._card      = LicenseCard()
        self._comm_mode = CommMode.PLAIN
        self._key_store = KeyStore()
        self._app_id              = "010203"
        self._app_key_settings    = 0x0F
        self._app_master_key_index = 0
        self._license_type = LicenseType.PERPETUAL

        self._file_key_map = {
            FILE_SERIAL:   {"read": 2, "write": 4},
            FILE_TYPE:     {"read": 2, "write": 4},
            FILE_PARAMS:   {"read": 5, "write": 5},
            FILE_CHECKSUM: {"read": 2, "write": 3},
        }

        self._service.event_bridge.cardInserted.connect(self._on_inserted)
        self._service.event_bridge.cardRemoved.connect(self._on_removed)
        self._service.start_monitor()

    # ── Card events ───────────────────────────────────────────────────────
    @Slot(str)
    def _on_inserted(self, atr: str):
        DESFIRE_ATR = "3B 81 80 01 80 80"
        self.cardInserted.emit(atr)
        if atr.upper() == DESFIRE_ATR:
            self.statusChanged.emit(f"DESFire card detected — ATR: {atr}")
        else:
            self.statusChanged.emit(f"⚠ Unknown card type — ATR: {atr}")

    @Slot()
    def _on_removed(self):
        self.cardRemoved.emit()
        self.statusChanged.emit("Card removed.")

    def __del__(self):
        self._service.stop_monitor()

    # ── App settings ──────────────────────────────────────────────────────
    @Slot(int)
    def set_license_type(self, index: int):
        self._license_type = LicenseType(index)
        self.statusChanged.emit(
            f"License type set to {self._license_type.name} "
            f"(File 3 size: {FILE_PARAMS_SIZE[self._license_type]} bytes)"
        )
    @Slot(str)
    def set_app_id(self, hex_str: str):
        try:
            b = bytes.fromhex(hex_str.strip())
            if len(b) != 3:
                raise ValueError("Application ID must be exactly 3 bytes (6 hex chars).")
            self._app_id = hex_str.strip()
        except ValueError as e:
            self.errorOccurred.emit(str(e))

    def set_app_key_settings_index(self, index: int):
        self._app_key_settings = self._APP_KEY_SETTINGS[index]

    def set_app_master_key(self, key_index: int):
        self._app_master_key_index = key_index

    def get_readers(self) -> list[str]:
        try:
            return [str(r) for r in list_readers()]
        except Exception as e:
            self.errorOccurred.emit(f"Could not enumerate readers: {e}")
            return []

    def _get_app_master_key(self) -> bytes:
        key = self._key_store.get(self._app_master_key_index + 1)
        return key.key_bytes if key else None

    def stop(self):
        self._service.stop_monitor()

    # ── Key store ─────────────────────────────────────────────────────────
    @property
    def key_store(self) -> KeyStore:
        return self._key_store

    @Slot(int)
    def generate_key(self, index: int):
        self._key_store.get(index).generate()
        self.keyStoreChanged.emit()
        self.statusChanged.emit(
            f"{self._key_store.get(index).name} generated: "
            f"{self._key_store.get(index).hex()}"
        )

    @Slot()
    def generate_all_keys(self):
        for i in range(6):
            self._key_store.get(i).generate()
        self.keyStoreChanged.emit()
        self.statusChanged.emit("All 6 keys generated.")

    @Slot(int, str)
    def set_key_hex(self, index: int, hex_str: str):
        try:
            b = bytes.fromhex(hex_str.replace(" ", ""))
            key = self._key_store.get(index)
            expected = int(key.key_type)
            if len(b) != expected:
                raise ValueError(
                    f"{key.name}: expected {expected * 2} hex chars "
                    f"for {key.key_type.name}, got {len(b) * 2}."
                )
            key.key_bytes = b
            self.keyStoreChanged.emit()
        except ValueError as e:
            self.errorOccurred.emit(str(e))

    # ── File key assignments ──────────────────────────────────────────────
    def set_file_key(self, file_id: int, role: str, key_index: int):
        self._file_key_map[file_id][role] = key_index

    def get_file_key(self, file_id: int, role: str) -> int:
        return self._file_key_map[file_id][role]

    def _read_key(self, file_id: int, role: str) -> bytes | None:
        idx    = self._file_key_map[file_id][role]
        nibble = self._key_store.key_index_to_nibble(idx)
        if nibble == KEY_FREE:
            return None            # free access — no key bytes needed
        return self._key_store.get(idx).key_bytes

    def _key_no(self, file_id: int, role: str) -> int | None:
        idx = self._file_key_map[file_id][role]
        nibble = self._key_store.key_index_to_nibble(idx)
        if nibble == KEY_FREE:
            return None  # free access — no key number needed
        return idx

    def _nibble(self, file_id: int, role: str) -> int:
        idx = self._file_key_map[file_id][role]
        return self._key_store.key_index_to_nibble(idx)

    # ── Comm mode ─────────────────────────────────────────────────────────
    def set_comm_mode(self, mode: CommMode):
        self._comm_mode = mode
        self._card.comm_mode = mode

    def update_card(self, card: LicenseCard):
        self._card = card

    # ── Reader ────────────────────────────────────────────────────────────
    @Slot()
    def find_reader(self):
        try:
            name = self._service.find_reader()
            self.readerFound.emit(name)
            self.statusChanged.emit(f"Reader found: {name}")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    @Slot()
    def connect_reader(self):
        try:
            self._service.connect()
            self.statusChanged.emit("Connected to uTrust 3720F HF.")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    @Slot()
    def disconnect_reader(self):
        self._service.disconnect()
        self.statusChanged.emit("Disconnected.")

    # ── UID ───────────────────────────────────────────────────────────────
    @Slot()
    def read_uid(self):
        try:
            uid = self._service.get_uid()
            self.uidRead.emit(uid)
            self.statusChanged.emit(f"UID: {uid}")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    # ── Provision ─────────────────────────────────────────────────────────
    @Slot()
    def provision_app(self):
        try:
            params_size = FILE_PARAMS_SIZE[self._license_type]
            self._service.provision(
                app_id=bytes.fromhex(self._app_id),
                key_settings=self._app_key_settings,
                comm_mode=self._comm_mode,
                params_size=params_size,  # ← new
                access_rights={
                    FILE_SERIAL: (self._nibble(FILE_SERIAL, "read"), self._nibble(FILE_SERIAL, "write")),
                    FILE_TYPE: (self._nibble(FILE_TYPE, "read"), self._nibble(FILE_TYPE, "write")),
                    FILE_PARAMS: (self._nibble(FILE_PARAMS, "read"), self._nibble(FILE_PARAMS, "write")),
                    FILE_CHECKSUM: (self._nibble(FILE_CHECKSUM, "read"), self._nibble(FILE_CHECKSUM, "write")),
                },
                log=self.provisionLog.emit,
            )
            self.statusChanged.emit(
                f"Provision complete — "
                f"License: {self._license_type.name}, "
                f"File 3 size: {params_size} bytes."
            )
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    # ── Write ─────────────────────────────────────────────────────────────
    @Slot(str)
    def write_card(self, app_id_hex: str = None):
        try:
            app_id = bytes.fromhex(app_id_hex or self._app_id)
            self._service.select_app(app_id)
            self._service.write_license_keyed(
                self._card,
                write_serial_key=self._read_key(FILE_SERIAL, "write"),
                write_type_key=self._read_key(FILE_TYPE, "write"),
                write_params_key=self._read_key(FILE_PARAMS, "write"),
                write_chksum_key=self._read_key(FILE_CHECKSUM, "write"),
                key_number_serial=self._key_no(FILE_SERIAL, "write"),
                key_number_type=self._key_no(FILE_TYPE, "write"),
                key_number_params=self._key_no(FILE_PARAMS, "write"),
                key_number_chksum=self._key_no(FILE_CHECKSUM, "write"),
            )
            self.cardWritten.emit()
            self.statusChanged.emit(
                f"✅ Card written to app {app_id.hex().upper()}."
            )
        except (CardServiceError, ValueError) as e:
            self.errorOccurred.emit(str(e))

    # ── Read ──────────────────────────────────────────────────────────────

    # ── Auth ──────────────────────────────────────────────────────────────
    @Slot(str)
    def test_authentication_picc(self, picc_key_hex: str = "0000000000000000"):
        try:
            picc_master_key = bytes.fromhex(picc_key_hex.replace(" ", ""))
            self._service.connect()
            self._service.select_app(bytes([0x00, 0x00, 0x00]))
            self._service.authenticate_plain(key_no=0x00, key=picc_master_key)
            self.authResult.emit(True, f"PICC master key auth OK (key: {picc_key_hex})")
        except (CardServiceError, ValueError) as e:
            self.authResult.emit(False, str(e))

    # ── Erase ─────────────────────────────────────────────────────────────
    @Slot()
    def erase_card(self, picc_key_hex: str = "0000000000000000"):
        try:
            picc_master_key = bytes.fromhex(picc_key_hex.replace(" ", ""))
            self._service.erase_card(picc_master_key)
            self.statusChanged.emit("Card erased — all applications deleted.")
        except (CardServiceError, ValueError) as e:
            self.errorOccurred.emit(str(e))

    # ── File value decoder ────────────────────────────────────────────────
    def _decode_file_value(self, file_id: int, raw: bytes) -> str:
        def hex_dash(b: bytes) -> str:
            return "-".join(f"{x:02X}" for x in b)

        try:
            if file_id == FILE_SERIAL:
                return f"{hex_dash(raw)}"

            if file_id == FILE_TYPE:
                return f"{hex_dash(raw)}"

            if file_id == FILE_PARAMS:
                return f"{hex_dash(raw)}"

            if file_id == FILE_CHECKSUM:
                return f"{hex_dash(raw)}"

        except Exception:
            return f"{hex_dash(raw)}"

    # ── Read Application via AID (with file values) ──────────────────────────────
    @Slot()
    def read_card(self, app_id_hex: str = None, read_keys: dict = None):
        """
        read_keys: optional dict mapping file_id -> hex key string.
                   If None, falls back to self._key_store (existing behaviour).
        """
        self.statusChanged.emit(f"Reading Card..., AID: {app_id_hex.upper()}")
        try:
            aid_bytes = bytes.fromhex(app_id_hex or self._app_id)
            self._service.select_app(aid_bytes)

            def _resolve_key(fid: int, nibble: int) -> tuple[int | None, bytes | None]:
                """Returns (key_no, key_bytes) honouring UI overrides."""
                if nibble == 0xF:
                    return None, None  # KEY_NONE — handled upstream
                if nibble == 0xE:
                    return None, None  # KEY_FREE — no auth needed

                # UI override takes priority
                if read_keys and fid in read_keys:
                    raw = read_keys[fid].replace(" ", "")
                    if raw:
                        return nibble, bytes.fromhex(raw)

                # Fall back to KeyStore
                return nibble, self._key_store.get(nibble).key_bytes

            def _read_file(fid: int) -> bytes:
                settings = self._service.get_file_settings(fid)
                read_nibble = int(settings.get("read_nibble", 0xE))
                size = settings["size"]

                if read_nibble == 0xF:
                    raise CardServiceError(f"File {fid}: no read access (KEY_NONE)")

                key_no, key_bytes = _resolve_key(fid, read_nibble)
                return self._service.read_file_keyed(
                    file_id=fid,
                    length=size,
                    key_no=key_no,
                    key=key_bytes,
                )

            # ── File 1 – Serial ───────────────────────────────────────
            raw_serial = _read_file(FILE_SERIAL)
            serial = SerialNumber.decode(raw_serial)

            # ── File 2 – License Type ─────────────────────────────────
            raw_type = _read_file(FILE_TYPE)
            license_type = LicenseType(raw_type[0])

            # ── File 3 – Parameters ───────────────────────────────────
            raw_params = _read_file(FILE_PARAMS)
            params = LicenseParams.decode(license_type, raw_params)

            # ── File 4 – Checksum ─────────────────────────────────────
            raw_chksum = _read_file(FILE_CHECKSUM)
            #checksum = struct.unpack_from("<I", raw_chksum)[0]
            checksum = struct.unpack_from(">I", raw_chksum)[0]

            card = LicenseCard(
                serial=serial,
                license_type=license_type,
                params=params,
                checksum=checksum,
            )
            self._card = card
            self.cardRead.emit(card)
            self.statusChanged.emit(
                f"✅ Card read — Serial: {serial}, "
                f"Type: {license_type.name}, "
                f"Params: {params.valid}, "
                f"CRC: {'OK' if card.checksum_valid() else 'INVALID'}"
            )

        except (CardServiceError, ValueError, IndexError) as e:
            self.errorOccurred.emit(str(e))

    '''
    @Slot()
    def read_card(self, app_id_hex: str = None):
        msg = f"Reading Card..., AID: {app_id_hex.upper()}"
        print(msg)
        try:
            aid_bytes = bytes.fromhex(app_id_hex)
            file_ids = self._service.get_file_ids(aid_bytes)
            serial = None
            license_type = None
            params = None

            for fid in file_ids:
                try:
                    settings = self._service.get_file_settings(fid)
                    decoded_value = ""

                    try:
                        read_nibble = settings.get("read_nibble", 0xE)  # raw nibble from card
                        if int(read_nibble) == 0xF:
                            # KEY_NONE — nobody can read this file
                            decoded_value = "<no read access>"
                            print(f"{fid}: {decoded_value}")
                        elif int(read_nibble) == 0xE:
                            # KEY_FREE — free access, no auth needed
                            raw_value = self._service.read_file_keyed(
                                file_id=fid,
                                length=settings["size"],
                                key_no=None,
                                key=None,
                            )
                            if fid == 1:
                                serial = int.from_bytes(raw_value, "little")
                            elif fid == 2:
                                license_type = LicenseType(raw_value[0])
                            elif fid == 3:
                                params = LicenseCard.decode_params(license_type, raw_value)
                            elif fid == 4:
                                chksum = struct.unpack_from("<I", raw_value)[0]
                                card = LicenseCard(
                                    serial=serial,
                                    license_type=license_type,
                                    params=params,
                                    checksum=chksum,
                                )
                                self._card = card
                                self.cardRead.emit(card)
                                self.statusChanged.emit(
                                    f"✅ Card read — Serial: {serial}, "
                                    f"Type: {license_type.name}, "
                                    f"CRC: {'OK' if card.checksum_valid() else 'INVALID'}"
                                )
                            else:
                                self.errorOccurred.emit(str(""))

                            print(f"KEY_FREE: {fid}: {raw_value}")
                        else:
                            # Key-protected — authenticate with the key from KeyStore
                            key_no = int(read_nibble)
                            try:
                                read_key = self._key_store.get(key_no).key_bytes
                                raw_value = self._service.read_file_keyed(
                                    file_id=fid,
                                    length=settings["size"],
                                    key_no=key_no,
                                    key=read_key,
                                )
                                print(f"{fid}: {raw_value}")
                            except IndexError:
                                decoded_value = f"<Key {key_no} not in KeyStore>"
                            except CardServiceError as e:
                                decoded_value = f"<auth failed Key {key_no}: {e}>"


                    except CardServiceError as e:
                        decoded_value = "<read failed>"
                except CardServiceError as e:
                    self.errorOccurred.emit(str(e))

        except CardServiceError as e:
            self.errorOccurred.emit(str(e))
    '''

    # ── Read Applications (with file values) ──────────────────────────────
    @Slot()
    def read_applications(self):
        try:
            # Retrieves all application present on the card
            aids = self._service.get_application_ids()
            result = []
            for entry in aids:
                if isinstance(entry, dict):
                    aid_bytes = entry["aid_bytes"]
                    aid_display = entry["aid_display"]
                else:
                    aid_display = entry
                    aid_bytes = bytes.fromhex(entry)[::-1]

                file_details = []
                try:
                    file_ids = self._service.get_file_ids(aid_bytes)
                    for fid in file_ids:
                        try:
                            settings = self._service.get_file_settings(fid)

                            decoded_value = ""
                            raw_value = b""
                            try:
                                read_nibble = settings.get("read_nibble", 0xE)  # raw nibble from card
                                comm_mode = settings.get("comm_mode", "Plain")

                                if int(read_nibble) == 0xF:
                                    # KEY_NONE — nobody can read this file
                                    decoded_value = "<no read access>"

                                elif int(read_nibble) == 0xE:
                                    # KEY_FREE — free access, no auth needed
                                    raw_value = self._service.read_file_keyed(
                                        file_id=fid,
                                        length=settings["size"],
                                        key_no=None,
                                        key=None,
                                    )
                                    decoded_value = self._decode_file_value(fid, raw_value)

                                else:
                                    # Key-protected — authenticate with the key from KeyStore
                                    key_no = int(read_nibble)
                                    try:
                                        read_key = self._key_store.get(key_no).key_bytes
                                        raw_value = self._service.read_file_keyed(
                                            file_id=fid,
                                            length=settings["size"],
                                            key_no=key_no,
                                            key=read_key,
                                        )
                                        decoded_value = self._decode_file_value(fid, raw_value)
                                    except IndexError:
                                        decoded_value = f"<Key {key_no} not in KeyStore>"
                                    except CardServiceError as e:
                                        decoded_value = f"<auth failed Key {key_no}: {e}>"

                            except CardServiceError:
                                decoded_value = "<read failed>"

                            settings["value"] = decoded_value
                            settings["raw_hex"] = raw_value.hex().upper()
                            file_details.append(settings)

                        except CardServiceError:
                            file_details.append({"file_id": fid, "error": True})

                except CardServiceError:
                    pass

                result.append({
                    "aid": aid_display,
                    "files": file_details,
                })

            self.appsRead.emit(result)
            self.statusChanged.emit(f"Found {len(result)} application(s) on card.")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    @Slot()
    def read_applications_meta_only(self):
        """Original read_applications without file value reading — kept for compatibility."""
        try:
            aids = self._service.get_application_ids()
            result = []
            for entry in aids:
                if isinstance(entry, dict):
                    aid_bytes   = entry["aid_bytes"]
                    aid_display = entry["aid_display"]
                else:
                    aid_display = entry
                    aid_bytes   = bytes.fromhex(entry)[::-1]

                file_details = []
                try:
                    file_ids = self._service.get_file_ids(aid_bytes)
                    for fid in file_ids:
                        try:
                            settings = self._service.get_file_settings(fid)
                            file_details.append(settings)
                        except CardServiceError:
                            file_details.append({"file_id": fid, "error": True})
                except CardServiceError:
                    pass

                result.append({"aid": aid_display, "files": file_details})

            self.appsRead.emit(result)
            self.statusChanged.emit(f"Found {len(result)} application(s) on card.")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    @Slot(str)
    def delete_application(self, aid_hex: str, picc_key_hex: str = "0000000000000000"):
        try:
            aid_bytes = bytes.fromhex(aid_hex)
            picc_master_key = bytes.fromhex(picc_key_hex.replace(" ", ""))
            self._service.delete_application(aid_bytes, picc_master_key)
            self.appDeleted.emit(aid_hex)
            self.statusChanged.emit(f"Application {aid_hex} deleted.")
        except (CardServiceError, ValueError) as e:
            self.errorOccurred.emit(str(e))

    @Slot(str, str)
    def change_master_key(self, old_key_hex: str, new_key_hex: str):
        try:
            old_key = bytes.fromhex(old_key_hex.replace(" ", ""))
            new_key = bytes.fromhex(new_key_hex.replace(" ", ""))
            if len(old_key) != len(new_key):
                raise ValueError("Old and new key must have the same length.")
            app_id = bytes.fromhex(self._app_id)
            self._service.select_app(app_id)
            self._service.authenticate_plain(key_no=0x00, key=old_key)
            self._service.change_key(key_no=0x00, old_key=old_key, new_key=new_key)
            self.keyChanged.emit(True, "Application master key changed successfully.")
            self.statusChanged.emit("Master key changed.")
        except (CardServiceError, ValueError) as e:
            self.keyChanged.emit(False, str(e))
            self.errorOccurred.emit(str(e))
