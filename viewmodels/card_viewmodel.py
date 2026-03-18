from PySide6.QtCore import QObject, Signal, Slot
from models.license_model import (
    LicenseCard, CommMode,  KeyStore,
    FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM
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
    logMessage      = Signal(str)  # add to signals block
    keyChanged      = Signal(bool, str)  # add to signals block

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
        """Return a list of available PC/SC reader names."""
        try:
            return [str(r) for r in list_readers()]
        except Exception as e:
            self.errorOccurred.emit(f"Could not enumerate readers: {e}")
            return []

    def _get_app_master_key(self) -> bytes:
        key = self._key_store.get(self._app_master_key_index + 1)
        return key.key_bytes if key else None

    def stop(self):
        """Public shutdown hook — stops the card monitor thread."""
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

    def _read_key(self, file_id: int, role: str):
        idx = self._file_key_map[file_id][role]
        if idx == 5:
            return None
        return self._key_store.get(idx).key_bytes

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
            self._service.provision(
                app_id       = bytes.fromhex(self._app_id),
                key_settings = self._app_key_settings,
                comm_mode    = self._comm_mode,
                access_rights = {
                    FILE_SERIAL:   (self._nibble(FILE_SERIAL,   "read"), self._nibble(FILE_SERIAL,   "write")),
                    FILE_TYPE:     (self._nibble(FILE_TYPE,     "read"), self._nibble(FILE_TYPE,     "write")),
                    FILE_PARAMS:   (self._nibble(FILE_PARAMS,   "read"), self._nibble(FILE_PARAMS,   "write")),
                    FILE_CHECKSUM: (self._nibble(FILE_CHECKSUM, "read"), self._nibble(FILE_CHECKSUM, "write")),
                },
                log = self.provisionLog.emit,
            )
            self.statusChanged.emit("Provision complete.")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    # ── Write ─────────────────────────────────────────────────────────────
    @Slot()
    def write_card(self):
        try:
            self._service.select_app()
            self._service.write_license_keyed(
                self._card,
                write_data_key   = self._read_key(FILE_SERIAL,   "write"),
                write_params_key = self._read_key(FILE_PARAMS,   "write"),
                write_chksum_key = self._read_key(FILE_CHECKSUM, "write"),
                key_no_data      = self._file_key_map[FILE_SERIAL]["write"],
                key_no_params    = self._file_key_map[FILE_PARAMS]["write"],
                key_no_chksum    = self._file_key_map[FILE_CHECKSUM]["write"],
            )
            self.cardWritten.emit()
            self.statusChanged.emit("Card written successfully.")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    # ── Read ──────────────────────────────────────────────────────────────
    @Slot()
    def read_card(self):
        try:
            self._service.select_app()
            card = self._service.read_license_keyed(
                read_data_key   = self._read_key(FILE_SERIAL, "read"),
                read_params_key = self._read_key(FILE_PARAMS, "read"),
                key_no_data     = self._file_key_map[FILE_SERIAL]["read"],
                key_no_params   = self._file_key_map[FILE_PARAMS]["read"],
            )
            self._card = card
            self.cardRead.emit(card)
            valid = card.checksum_valid()
            self.statusChanged.emit(
                f"Read OK | {card.serial} | "
                f"{card.license_type.name} | "
                f"Checksum: {'✔ Valid' if valid else '✘ INVALID'}"
            )
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    # ── Auth ──────────────────────────────────────────────────────────────
    @Slot(str)
    def test_authentication_picc(self, picc_key_hex: str = "0000000000000000"):
        try:
            picc_master_key = bytes.fromhex(picc_key_hex.replace(" ", ""))
            self._service.connect()
            self._service.select_app(bytes([0x00, 0x00, 0x00]))  # select PICC master
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

    @Slot()
    def read_applications(self):
        try:
            aids = self._service.get_application_ids()
            result = []
            for entry in aids:
                # Guard: handle both dict and legacy string format
                if isinstance(entry, dict):
                    aid_bytes = entry["aid_bytes"]
                    aid_display = entry["aid_display"]
                else:
                    # Legacy fallback — entry is a plain hex string
                    aid_display = entry
                    aid_bytes = bytes.fromhex(entry)[::-1]

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

                result.append({
                    "aid": aid_display,
                    "files": file_details,
                })

            self.appsRead.emit(result)
            self.statusChanged.emit(f"Found {len(result)} application(s) on card.")
        except CardServiceError as e:
            self.errorOccurred.emit(str(e))

    @Slot(str, str)
    def delete_application(self, aid_hex: str, picc_key_hex: str = "0000000000000000"):
        try:
            aid_bytes = bytes.fromhex(aid_hex)  # MSB→LSB wire order
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






