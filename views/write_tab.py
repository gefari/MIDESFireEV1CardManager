# views/write_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QGroupBox, QSpinBox, QDateTimeEdit, QMessageBox,
)
from PySide6.QtCore import QDateTime, Slot
from PySide6.QtGui import QFont

from models.license_model import (
    LicenseCard, LicenseType, LicenseParams, SerialNumber, CommMode,
)
from viewmodels.card_viewmodel import CardViewModel

import datetime


# ── Shared helper (local copy; move to views/utils.py if shared across tabs) ──
def mono_font() -> QFont:
    f = QFont("Courier New", 10)
    f.setFixedPitch(True)
    return f


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Write
# ══════════════════════════════════════════════════════════════════════════════
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
        root.addWidget(lt_box)

        # ── File 3 – Parameters ────────────────────────────────────
        self.params_box = QGroupBox("File 3 – License Parameters")
        p_form = QFormLayout(self.params_box)

        self.exp_label     = QLabel("Expiration:")
        self.exp_date_edit = QDateTimeEdit(QDateTime.currentDateTimeUtc())
        self.exp_date_edit.setDisplayFormat("yyyy/MM/dd HH:mm:ss")   # ← 4-digit year fix
        self.exp_date_edit.setCalendarPopup(True)

        self.num_uses_label = QLabel("Number of uses:")
        self.num_uses_spin  = QSpinBox()
        self.num_uses_spin.setRange(0, 65535)

        self.hours_label = QLabel("Hours per use:")
        self.hours_spin  = QSpinBox()
        self.hours_spin.setRange(0, 65535)

        p_form.addRow(self.exp_label,      self.exp_date_edit)
        p_form.addRow(self.num_uses_label, self.num_uses_spin)
        p_form.addRow(self.hours_label,    self.hours_spin)
        root.addWidget(self.params_box)

        # ── File 4 – Checksum ──────────────────────────────────────
        chk_box = QGroupBox("File 4 – Checksum")
        chk_form = QFormLayout(chk_box)
        self.checksum_edit = QLineEdit()
        self.checksum_edit.setReadOnly(True)
        self.checksum_edit.setFont(mono_font())
        chk_form.addRow("CRC-32:", self.checksum_edit)
        root.addWidget(chk_box)

        # ── Write button ───────────────────────────────────────────
        self.btn_write = QPushButton("✎  Write Card")
        self.btn_write.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.btn_write)

        self.status_label = QLabel("Ready.")
        root.addWidget(self.status_label)
        root.addStretch()

    # ── Signal wiring ──────────────────────────────────────────────────────────

    def _connect_signals(self):
        # btn_now: stamp then recompute checksum — single connection each
        self.btn_now.clicked.connect(self._on_stamp_now)

        self.serial_edit.textChanged.connect(self._update_checksum)    # ← manual edits also trigger
        self.license_type_combo.currentIndexChanged.connect(self._refresh_param_visibility)
        self.license_type_combo.currentIndexChanged.connect(self._update_checksum)
        self.exp_date_edit.dateTimeChanged.connect(self._update_checksum)
        self.num_uses_spin.valueChanged.connect(self._update_checksum)
        self.hours_spin.valueChanged.connect(self._update_checksum)

        self.btn_write.clicked.connect(self._on_write)

        # ViewModel signals
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
        """Show only the parameter widgets relevant to the selected license type."""
        self.exp_label.setVisible(idx == LicenseType.TIME_LIMITED)
        self.exp_date_edit.setVisible(idx == LicenseType.TIME_LIMITED)
        self.num_uses_label.setVisible(idx == LicenseType.PER_USE)
        self.num_uses_spin.setVisible(idx == LicenseType.PER_USE)
        self.hours_label.setVisible(idx == LicenseType.PER_USE)
        self.hours_spin.setVisible(idx == LicenseType.PER_USE)

    @Slot()
    def _update_checksum(self):
        """Recompute and display the CRC-32 checksum from current UI state."""
        card = self._build_card_from_ui()
        self.checksum_edit.setText(f"{card.compute_checksum():08X}")

    # ── Card construction ──────────────────────────────────────────────────────

    def _build_card_from_ui(self) -> LicenseCard:
        """
        Build a LicenseCard from the current UI state.
        Falls back to utcnow() if the serial field cannot be parsed,
        and sets the checksum on the returned card.
        """
        raw_serial = self.serial_edit.text().strip()
        try:
            dt = datetime.datetime.strptime(raw_serial, "%y%m%d%H%M%S")
        except ValueError:
            dt = datetime.datetime.utcnow()

        serial = SerialNumber(dt=dt)
        lt     = LicenseType(self.license_type_combo.currentIndex())

        if lt == LicenseType.PERPETUAL:
            params = LicenseParams(license_type=lt)
        elif lt == LicenseType.TIME_LIMITED:
            qdt    = self.exp_date_edit.dateTime().toPython()
            params = LicenseParams(license_type=lt, expiration=qdt)
        else:  # PER_USE
            params = LicenseParams(
                license_type=lt,
                num_uses=self.num_uses_spin.value(),
                hours_per_use=self.hours_spin.value(),
            )

        card          = LicenseCard(serial=serial, license_type=lt,
                                    params=params, comm_mode=CommMode.PLAIN)
        card.checksum = card.compute_checksum()
        return card

    @Slot()
    def _on_write(self):
        """Validate, build card, connect to reader, and write."""
        raw_serial = self.serial_edit.text().strip()
        if len(raw_serial) != 12 or not raw_serial.isdigit():
            QMessageBox.warning(
                self, "Invalid Serial",
                f"Serial must be exactly 12 digits (YYMMDDHHMMSS).\nGot: '{raw_serial}'"
            )
            return

        card = self._build_card_from_ui()
        self.vm.update_card(card)

        if not self.vm.connect_reader():
            return   # ViewModel emits errorOccurred; _on_write stops here

        self.vm.write_card()
