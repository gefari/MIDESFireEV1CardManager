from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QGroupBox, QSpinBox, QDateTimeEdit, QMessageBox,
)
from PySide6.QtCore import QDateTime, Slot
from PySide6.QtGui import QFont

from models.license_model import (
    LicenseCard, LicenseType, LicenseParams, SerialNumber, CommMode,
    FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM,
)

from viewmodels.card_viewmodel import CardViewModel

import datetime


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
        root.addWidget(app_box)

        # ── File 1 – Serial ────────────────────────────────────────
        sn_box = QGroupBox("File 1 – License Serial Number")
        sn_form = QFormLayout(sn_box)

        self.serial_edit = QLineEdit()
        self.serial_edit.setFont(mono_font())
        self.serial_edit.setPlaceholderText("YYMMDDHHMMSS")
        self.serial_edit.setMaxLength(12)
        self.serial_edit.setText(
            datetime.datetime.utcnow().strftime("%y%m%d%H%M%S")
        )

        self.btn_now = QPushButton("Now")
        self.btn_now.setFixedWidth(50)
        self.btn_now.setToolTip("Stamp current UTC time as serial number")

        serial_row = QHBoxLayout()
        serial_row.addWidget(self.serial_edit)
        serial_row.addWidget(self.btn_now)
        sn_form.addRow("Serial (YYMMDDHHMMSS):", serial_row)


        self.serial_write_key_edit = QLineEdit()
        sn_form.addRow("Write key:", self.serial_write_key_edit)

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

        self.lic_type_write_key_edit = QLineEdit()
        lt_form.addRow("Write key:", self.lic_type_write_key_edit)

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

        self.params_write_key_edit = QLineEdit()
        p_form.addRow("Write key:", self.params_write_key_edit)

        root.addWidget(self.params_box)

        # ── File 4 – Checksum ──────────────────────────────────────
        chk_box = QGroupBox("File 4 – Checksum")
        chk_form = QFormLayout(chk_box)
        self.checksum_edit = QLineEdit()
        self.checksum_edit.setReadOnly(True)
        self.checksum_edit.setFont(mono_font())
        chk_form.addRow("CRC-32:", self.checksum_edit)

        self.chksum_write_key_edit = QLineEdit()
        chk_form.addRow("Write key:", self.chksum_write_key_edit)

        root.addWidget(chk_box)

        # ── Write button ───────────────────────────────────────────
        self.btn_write = QPushButton("✎  Write Card")
        self.btn_write.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.btn_write)

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
        self.btn_now.clicked.connect(self._on_stamp_now)
        self.btn_write.clicked.connect(self._on_write)

        self.serial_edit.textChanged.connect(self._update_checksum)
        self.valid_combo.currentIndexChanged.connect(self._update_checksum)
        self.exp_date_edit.dateTimeChanged.connect(self._update_checksum)
        self.num_uses_spin.valueChanged.connect(self._update_checksum)
        self.hours_spin.valueChanged.connect(self._update_checksum)

        self.license_type_combo.currentIndexChanged.connect(self._refresh_param_visibility)
        self.license_type_combo.currentIndexChanged.connect(self._update_checksum)

        self.vm.statusChanged.connect(self.status_label.setText)
        self.vm.errorOccurred.connect(
            lambda m: QMessageBox.critical(self, "Error", m)
        )
        self.vm.cardWritten.connect(
            lambda: self.status_label.setText("Card written successfully.")
        )

    # ── Slots ──────────────────────────────────────────────────────────────────

    @Slot()
    def _on_stamp_now(self):
        """Stamp current UTC time into serial field and refresh checksum."""
        self.serial_edit.setText(
            datetime.datetime.utcnow().strftime("%y%m%d%H%M%S")
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
            dt = datetime.datetime.strptime(raw_serial, "%y%m%d%H%M%S")
        except ValueError:
            dt = datetime.datetime.utcnow()

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
        self.vm.set_file_key(FILE_SERIAL, "write", self._key_index_from_edit(self.serial_write_key_edit))
        self.vm.set_file_key(FILE_TYPE, "write", self._key_index_from_edit(self.lic_type_write_key_edit))
        self.vm.set_file_key(FILE_PARAMS, "write", self._key_index_from_edit(self.params_write_key_edit))
        self.vm.set_file_key(FILE_CHECKSUM, "write", self._key_index_from_edit(self.chksum_write_key_edit))

        card = self._build_card_from_ui()
        self.vm.update_card(card)
        #self.vm.connect_reader()
        self.vm.write_card(app_id)

