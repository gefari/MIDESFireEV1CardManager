from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QGroupBox, QSpinBox, QDateTimeEdit, QMessageBox, QCheckBox
)
from PySide6.QtCore import QDateTime, Slot
from PySide6.QtGui import QFont

from models.license_model import (
    LicenseCard, LicenseType, LicenseParams, SerialNumber, CommMode,
    FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM,
)

from viewmodels.card_viewmodel import CardViewModel
from datetime import datetime, timezone

# ── Shared helper (local copy; move to views/utils.py if shared across tabs) ──
def mono_font() -> QFont:
    f = QFont("Courier New", 10)
    f.setFixedPitch(True)
    return f


class WriteTab(QWidget):
    """Builds a LicenseCard from UI inputs and writes it to the card."""

    def __init__(self, vm: CardViewModel, parent=None):
        super().__init__(parent)
        self.vm = vm
        self._build_ui()
        self._connect_signals()
        self._refresh_param_visibility(0)
        self._update_checksum()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Application ID ─────────────────────────────────────────
        app_box = QGroupBox("Application")
        app_form = QFormLayout(app_box)
        self.app_id_edit = QLineEdit("010203")
        self.app_id_edit.setMaxLength(6)
        self.app_id_edit.setFont(mono_font())
        self.app_id_edit.setPlaceholderText("6 hex chars  e.g. 010203")
        app_form.addRow("Application ID (hex):", self.app_id_edit)

        app_keys = QHBoxLayout()
        app_keys.addWidget(QLabel("Write key:"))
        self.aid_w_key_edit = QLineEdit()
        app_keys.addWidget(self.aid_w_key_edit)
        app_keys.addSpacing(16)
        app_keys.addWidget(QLabel("Read key:"))
        self.aid_r_key_edit = QLineEdit()
        app_keys.addWidget(self.aid_r_key_edit)
        app_keys.addStretch()
        app_form.addRow(app_keys)

        root.addWidget(app_box)

        # ── Global invalidate flag ────────────────────────────────────────────
        self.chk_invalidate = QCheckBox("⚠  Invalidate card (write all-zero parameters)")
        self.chk_invalidate.setStyleSheet("color: orange; font-weight: bold;")
        root.addWidget(self.chk_invalidate)

        # ── File 1 – Serial ────────────────────────────────────────
        sn_box = QGroupBox("File 1 – License Serial Number")
        sn_form = QFormLayout(sn_box)

        self.serial_edit = QLineEdit()
        self.serial_edit.setFont(mono_font())
        self.serial_edit.setPlaceholderText("YYMMDDHHMMSS")
        self.serial_edit.setMaxLength(12)
        self.serial_edit.setText(
            datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
        )

        self.btn_now = QPushButton("Now")
        self.btn_now.setFixedWidth(50)
        self.btn_now.setToolTip("Stamp current UTC time as serial number")

        serial_row = QHBoxLayout()
        serial_row.addWidget(self.serial_edit)
        serial_row.addWidget(self.btn_now)
        sn_form.addRow("Serial (YYMMDDHHMMSS):", serial_row)

        sn_keys = QHBoxLayout()
        sn_keys.addWidget(QLabel("Write key:"))
        self.serial_w_key_edit = QLineEdit()
        sn_keys.addWidget(self.serial_w_key_edit)
        sn_keys.addSpacing(16)
        sn_keys.addWidget(QLabel("Read key:"))
        self.serial_r_key_edit = QLineEdit()
        sn_keys.addWidget(self.serial_r_key_edit)
        sn_keys.addStretch()
        sn_form.addRow(sn_keys)

        root.addWidget(sn_box)

        # ── File 2 – License Type ──────────────────────────────────
        lt_box = QGroupBox("File 2 – License Type")
        lt_form = QFormLayout(lt_box)
        self.license_type_combo = QComboBox()
        self.license_type_combo.addItems([
            "0 – Perpetual",
            "1 – Time Limited",
            "2 – Per Use",
        ])
        lt_form.addRow("Type:", self.license_type_combo)

        lic_keys = QHBoxLayout()
        lic_keys.addWidget(QLabel("Write key:"))
        self.lic_type_w_key_edit = QLineEdit()
        lic_keys.addWidget(self.lic_type_w_key_edit)
        lic_keys.addSpacing(16)
        lic_keys.addWidget(QLabel("Read key:"))
        self.lic_type_r_key_edit = QLineEdit()
        lic_keys.addWidget(self.lic_type_r_key_edit)
        lic_keys.addStretch()
        lt_form.addRow(lic_keys)

        root.addWidget(lt_box)

        # ── File 3 – Parameters ────────────────────────────────────
        self.params_box = QGroupBox("File 3 – License Parameters")
        p_form = QFormLayout(self.params_box)

        # Perpetual — validity flag
        self.valid_label = QLabel("Valid:")
        self.valid_combo = QComboBox()
        self.valid_combo.addItems(["1 – Valid", "0 – Invalid"])
        self.valid_combo.setCurrentIndex(0)
        self.valid_combo.currentIndexChanged.connect(self._update_checksum)

        # Time Limited — expiration date
        self.exp_label = QLabel("Expiration:")
        self.exp_date_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        self.exp_date_edit.setDisplayFormat("yyyy/MM/dd HH:mm:ss")
        self.exp_date_edit.setCalendarPopup(True)

        # Per Use — use count + hours
        self.num_uses_label = QLabel("Number of uses:")
        self.num_uses_spin = QSpinBox()
        self.num_uses_spin.setRange(0, 65535)

        self.hours_label = QLabel("Hours per use:")
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 65535)

        p_form.addRow(self.valid_label, self.valid_combo)
        p_form.addRow(self.exp_label, self.exp_date_edit)
        p_form.addRow(self.num_uses_label, self.num_uses_spin)
        p_form.addRow(self.hours_label, self.hours_spin)

        params_keys = QHBoxLayout()
        params_keys.addWidget(QLabel("Write key:"))
        self.params_w_key_edit = QLineEdit()
        params_keys.addWidget(self.params_w_key_edit)
        params_keys.addSpacing(16)
        params_keys.addWidget(QLabel("Read key:"))
        self.params_r_key_edit = QLineEdit()
        params_keys.addWidget(self.params_r_key_edit)
        params_keys.addStretch()
        p_form.addRow(params_keys)

        root.addWidget(self.params_box)

        # ── File 4 – Checksum ──────────────────────────────────────
        chk_box = QGroupBox("File 4 – Checksum")
        chk_form = QFormLayout(chk_box)
        self.checksum_edit = QLineEdit()
        self.checksum_edit.setReadOnly(True)
        self.checksum_edit.setFont(mono_font())
        chk_form.addRow("CRC-32:", self.checksum_edit)

        chksum_keys = QHBoxLayout()
        chksum_keys.addWidget(QLabel("Write key:"))
        self.chksum_w_key_edit = QLineEdit()
        chksum_keys.addWidget(self.chksum_w_key_edit)
        chksum_keys.addSpacing(16)
        chksum_keys.addWidget(QLabel("Read key:"))
        self.chksum_r_key_edit = QLineEdit()
        chksum_keys.addWidget(self.chksum_r_key_edit)
        chksum_keys.addStretch()
        chk_form.addRow(chksum_keys)

        root.addWidget(chk_box)

        # ── Read button ────────────────────────────────────────────
        self.btn_read = QPushButton("⟳  Read Card")
        self.btn_read.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.btn_read)

        # ── Write button ───────────────────────────────────────────
        self.btn_write = QPushButton("✎  Write Card")
        self.btn_write.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.btn_write)

        # ── Status Label ───────────────────────────────────────────
        self.status_label = QLabel("Ready.")
        root.addWidget(self.status_label)
        root.addStretch()

    # ── Key combo helper ───────────────────────────────────────────────────────
    def _make_write_key_combo(self, default: int = 4) -> QComboBox:
        combo = QComboBox()
        combo.addItems(self.vm.key_store.key_names())
        combo.setCurrentIndex(default)
        return combo

    # ── Signal wiring ──────────────────────────────────────────────────────────
    def _connect_signals(self):
        # --- Button
        self.btn_now.clicked.connect(self._on_stamp_now)
        self.btn_write.clicked.connect(self._on_write)
        self.btn_read.clicked.connect(self._on_read)

        self.serial_edit.textChanged.connect(self._update_checksum)
        self.exp_date_edit.dateTimeChanged.connect(self._update_checksum)

        # --- Spin
        self.num_uses_spin.valueChanged.connect(self._update_checksum)
        self.hours_spin.valueChanged.connect(self._update_checksum)

        # --- Combo Box
        self.valid_combo.currentIndexChanged.connect(self._update_checksum)
        self.license_type_combo.currentIndexChanged.connect(self._refresh_param_visibility)
        self.license_type_combo.currentIndexChanged.connect(self._update_checksum)
        self.license_type_combo.currentIndexChanged.connect(self.vm.set_license_type)

        # --- View Model
        self.vm.statusChanged.connect(self.status_label.setText)
        self.vm.errorOccurred.connect(lambda m: QMessageBox.critical(self, "Error", m))
        self.vm.cardWritten.connect(lambda: self.status_label.setText("Card written successfully."))
        self.vm.cardRead.connect(self._populate)

        # --- Check Box
        self.chk_invalidate.stateChanged.connect(self._on_invalidate_toggled)

    # ── Slots ──────────────────────────────────────────────────────────────────

    @Slot()
    def _on_stamp_now(self):
        """Stamp current UTC time into serial field and refresh checksum."""
        self.serial_edit.setText(
            datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
        )
        # _update_checksum fires automatically via serial_edit.textChanged

    @Slot(int)
    def _refresh_param_visibility(self, idx: int):
        is_perpetual = idx == LicenseType.PERPETUAL
        is_time_limited = idx == LicenseType.TIME_LIMITED
        is_per_use = idx == LicenseType.PER_USE

        self.params_box.setVisible(True)  # always show File 3

        self.valid_label.setVisible(is_perpetual)
        self.valid_combo.setVisible(is_perpetual)

        self.exp_label.setVisible(is_time_limited)
        self.exp_date_edit.setVisible(is_time_limited)

        self.num_uses_label.setVisible(is_per_use)
        self.num_uses_spin.setVisible(is_per_use)
        self.hours_label.setVisible(is_per_use)
        self.hours_spin.setVisible(is_per_use)

    @Slot()
    def _update_checksum(self):
        """Recompute and display the CRC-32 checksum from current UI state."""
        card = self._build_card_from_ui()
        self.checksum_edit.setText(f"{card.compute_checksum():08X}")

    # ── Card construction ──────────────────────────────────────────────────────

    def _build_card_from_ui(self) -> LicenseCard:
        raw_serial = self.serial_edit.text().strip()
        try:
            dt = datetime.strptime(raw_serial, "%y%m%d%H%M%S")
        except ValueError:
            dt = datetime.now(timezone.utc)

        serial = SerialNumber(dt=dt)
        lt = LicenseType(self.license_type_combo.currentIndex())

        if lt == LicenseType.PERPETUAL:
            # valid_combo index 0 = Valid (1), index 1 = Invalid (0)
            is_valid = self.valid_combo.currentIndex() == 0
            params = LicenseParams(license_type=lt, valid=is_valid)
        elif lt == LicenseType.TIME_LIMITED:
            qdt = self.exp_date_edit.dateTime().toPython()
            params = LicenseParams(license_type=lt, expiration=qdt)
        else:  # PER_USE
            params = LicenseParams(
                license_type=lt,
                num_uses=self.num_uses_spin.value(),
                hours_per_use=self.hours_spin.value(),
            )

        card = LicenseCard(serial=serial, license_type=lt,
                           params=params, comm_mode=CommMode.PLAIN)
        card.checksum = card.compute_checksum()
        return card

    # ── Key index parser ───────────────────────────────────────────────────────
    def _key_index_from_edit(self, edit: QLineEdit) -> int:
        """
        Parse a key index from a read-only key label field.
        Accepts:  'Key 2'  → 2
                  'Free'   → 6  (free-access combo index)
                  'None'   → 6  (treat as free)
        Falls back to 0 on parse failure.
        """
        text = edit.text().strip()
        if text.lower() in ("free", "none", "—", ""):
            return 6  # free-access index in key_store.key_names()
        if text.lower().startswith("key"):
            try:
                return int(text.split()[-1])
            except ValueError:
                pass
        return 0

    # ── Read slot ─────────────────────────────────────────────────────────────
    def _on_read(self):
        app_id = self.app_id_edit.text().strip()
        if len(app_id) != 6:
            QMessageBox.warning(
                self, "Invalid App ID",
                f"Application ID must be exactly 6 hex chars.\nGot: '{app_id}'"
            )
            return

        keys = {
            "app": self.aid_r_key_edit.text().strip(),
            FILE_SERIAL: self.serial_r_key_edit.text().strip(),
            FILE_TYPE: self.lic_type_r_key_edit.text().strip(),
            FILE_PARAMS: self.params_r_key_edit.text().strip(),
            FILE_CHECKSUM: self.chksum_r_key_edit.text().strip(),
        }
        self.vm.read_card(app_id, keys)

    # ── Write slot ─────────────────────────────────────────────────────────────
    @Slot()
    def _on_write(self):
        raw_serial = self.serial_edit.text().strip()
        if len(raw_serial) != 12 or not raw_serial.isdigit():
            QMessageBox.warning(
                self, "Invalid Serial",
                f"Serial must be exactly 12 digits (YYMMDDHHMMSS).\nGot: '{raw_serial}'"
            )
            return

        app_id = self.app_id_edit.text().strip()
        try:
            b = bytes.fromhex(app_id)
            if len(b) != 3:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "Invalid App ID",
                "Application ID must be exactly 6 valid hex characters."
            )
            return

        # Push per-file write keys into the ViewModel before writing
        #self.vm.set_file_key(FILE_SERIAL, "write", self._key_index_from_edit(self.serial_write_key_edit))
        self.vm.set_file_key(FILE_SERIAL, "write", self._key_index_from_edit(self.serial_w_key_edit))
        #self.vm.set_file_key(FILE_TYPE, "write", self._key_index_from_edit(self.lic_type_write_key_edit))
        self.vm.set_file_key(FILE_TYPE, "write", self._key_index_from_edit(self.lic_type_w_key_edit))
        #self.vm.set_file_key(FILE_PARAMS, "write", self._key_index_from_edit(self.params_write_key_edit))
        self.vm.set_file_key(FILE_PARAMS, "write", self._key_index_from_edit(self.params_w_key_edit))
        #self.vm.set_file_key(FILE_CHECKSUM, "write", self._key_index_from_edit(self.chksum_write_key_edit))
        self.vm.set_file_key(FILE_CHECKSUM, "write", self._key_index_from_edit(self.chksum_w_key_edit))

        card = self._build_card_from_ui()
        self.vm.update_card(card)
        #self.vm.connect_reader()
        self.vm.write_card(app_id)

    @Slot(int)
    def _on_invalidate_toggled(self, state: int):
        checked = bool(state)
        license_type = LicenseType(self.license_type_combo.currentIndex())

        # ── Lock/unlock the params UI fields ─────────────────────────────
        self.valid_combo.setEnabled(not checked)  # PERPETUAL
        self.exp_date_edit.setEnabled(not checked)  # TIME_LIMITED
        self.num_uses_spin.setEnabled(not checked)  # PER_USE
        self.hours_spin.setEnabled(not checked)  # PER_USE

        if checked:
            # ── Force UI to zeros ─────────────────────────────────────────
            if license_type == LicenseType.PERPETUAL:
                self.valid_combo.setCurrentIndex(1)  # 0 – Invalid

            elif license_type == LicenseType.TIME_LIMITED:
                self.exp_date_edit.setDateTime(QDateTime(2000, 1, 1, 0, 0, 0))

            elif license_type == LicenseType.PER_USE:
                self.num_uses_spin.setValue(0)
                self.hours_spin.setValue(0)

        # ── Rebuild card, invalidate params, update CRC display ──────────
        card = self._build_card_from_ui()
        if checked:
            card.params.invalidate()
            card.checksum = card.compute_checksum()
        self.vm.update_card(card)
        self.checksum_edit.setText(f"{card.compute_checksum():08X}")

    @Slot(LicenseCard)
    def _populate(self, card: LicenseCard):
        # Populate Serial
        self.serial_edit.setText(str(card.serial))

        if card.license_type == LicenseType.PERPETUAL:
            # Select License Combo Box
            self.license_type_combo.setCurrentIndex(0)
            if card.params.valid:
                # Select Valid Combo Box (Index for Valid: 0)
                self.valid_combo.setCurrentIndex(0)
                pass
            else:
                # Select InValid Combo Box (Index for InValid: 1)
                self.valid_combo.setCurrentIndex(1)
                pass
            self._refresh_param_visibility(0)
        elif card.license_type == LicenseType.TIME_LIMITED:
            # Select License Combo Box
            self.license_type_combo.setCurrentIndex(1)
            dt = card.params.expiration
            q_dt = QDateTime(
                dt.year, dt.month, dt.day,
                dt.hour, dt.minute, dt.second
            )
            self.exp_date_edit.setDateTime(q_dt)
            self._refresh_param_visibility(1)
        elif card.license_type == LicenseType.PER_USE:
            # Select License Combo Box
            self.license_type_combo.setCurrentIndex(2)
            self.num_uses_spin.setValue(card.params.num_uses)
            self.hours_spin.setValue(card.params.hours_per_use)

            self._refresh_param_visibility(2)
        else:
            pass



        self.checksum_edit.setText(f"{card.checksum:08X}")
        valid = card.checksum_valid()

        #self.checksum_valid_label.setText("✔ Valid" if valid else "✘ INVALID")
        #self.checksum_valid_label.setStyleSheet(
        #    "color: green; font-weight: bold;" if valid
        #    else "color: red; font-weight: bold;")




