from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton,
    QGroupBox, QMessageBox,
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QFont

from models.license_model import (
    LicenseCard, LicenseType,
    FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM,
)
from viewmodels.card_viewmodel import CardViewModel


def mono_font() -> QFont:
    f = QFont("Courier New", 10)
    f.setFixedPitch(True)
    return f


class ReadTab(QWidget):

    _TYPE_LABELS = {
        LicenseType.PERPETUAL:    "0 – Perpetual",
        LicenseType.TIME_LIMITED: "1 – Time Limited",
        LicenseType.PER_USE:      "2 – Per Use",
    }

    def __init__(self, vm: CardViewModel, parent=None):
        super().__init__(parent)
        self.vm = vm
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Application ────────────────────────────────────────────
        app_box = QGroupBox("Application")
        app_form = QFormLayout(app_box)
        self.app_id_edit = QLineEdit("010203")
        self.app_id_edit.setMaxLength(6)
        self.app_id_edit.setFont(mono_font())
        self.app_id_edit.setPlaceholderText("6 hex chars  e.g. 010203")
        app_form.addRow("Application ID (hex):", self.app_id_edit)

        self.app_read_key_edit = QLineEdit()
        app_form.addRow("Read key:", self.app_read_key_edit)

        root.addWidget(app_box)

        # ── File 1 – Serial ────────────────────────────────────────
        f1_box = QGroupBox("File 1 – License Serial Number")
        f1_form = QFormLayout(f1_box)
        self.serial_edit = QLineEdit()
        self.serial_edit.setReadOnly(True)
        self.serial_edit.setFont(mono_font())
        f1_form.addRow("Serial:", self.serial_edit)

        self.serial_read_key_edit = QLineEdit()
        f1_form.addRow("Read key:", self.serial_read_key_edit)

        root.addWidget(f1_box)

        # ── File 2 – License Type ──────────────────────────────────
        f2_box = QGroupBox("File 2 – License Type")
        f2_form = QFormLayout(f2_box)
        self.type_edit = QLineEdit()
        self.type_edit.setReadOnly(True)
        f2_form.addRow("Type:", self.type_edit)

        self.lic_type_read_key_edit = QLineEdit()
        f2_form.addRow("Read key:", self.lic_type_read_key_edit)

        root.addWidget(f2_box)

        # ── File 3 – Parameters ────────────────────────────────────
        f3_box = QGroupBox("File 3 – License Parameters")
        f3_form = QFormLayout(f3_box)
        self.params_edit = QLineEdit()
        self.params_edit.setReadOnly(True)
        f3_form.addRow("Parameters:", self.params_edit)

        self.params_read_key_edit = QLineEdit()
        f3_form.addRow("Read key:", self.params_read_key_edit)

        root.addWidget(f3_box)

        # ── File 4 – Checksum ──────────────────────────────────────
        f4_box = QGroupBox("File 4 – Checksum")
        f4_form = QFormLayout(f4_box)
        self.checksum_edit = QLineEdit()
        self.checksum_edit.setReadOnly(True)
        self.checksum_edit.setFont(mono_font())
        self.checksum_valid_label = QLabel("")
        f4_form.addRow("CRC-32:",   self.checksum_edit)
        f4_form.addRow("Validity:", self.checksum_valid_label)

        self.chksum_read_key_edit = QLineEdit()
        f4_form.addRow("Read key:", self.chksum_read_key_edit)

        root.addWidget(f4_box)

        # ── Read button ────────────────────────────────────────────
        self.btn_read = QPushButton("⟳  Read Card")
        self.btn_read.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.btn_read)

        self.status_label = QLabel("Ready.")
        root.addWidget(self.status_label)
        root.addStretch()

    def _connect_signals(self):
        self.btn_read.clicked.connect(self._on_read)
        self.vm.statusChanged.connect(self.status_label.setText)
        self.vm.errorOccurred.connect(
            lambda m: QMessageBox.critical(self, "Error", m))
        self.vm.cardRead.connect(self._populate)

    @Slot()
    def _on_read(self):
        app_id = self.app_id_edit.text().strip()
        if len(app_id) != 6:
            QMessageBox.warning(
                self, "Invalid App ID",
                f"Application ID must be exactly 6 hex chars.\nGot: '{app_id}'"
            )
            return

        keys = {
            "app": self.app_read_key_edit.text().strip(),
            FILE_SERIAL: self.serial_read_key_edit.text().strip(),
            FILE_TYPE: self.lic_type_read_key_edit.text().strip(),
            FILE_PARAMS: self.params_read_key_edit.text().strip(),
            FILE_CHECKSUM: self.chksum_read_key_edit.text().strip(),
        }
        self.vm.read_card(app_id, keys)

    @Slot(LicenseCard)
    def _populate(self, card: LicenseCard):
        self.serial_edit.setText(str(card.serial))
        self.type_edit.setText(self._TYPE_LABELS[card.license_type])

        if card.license_type == LicenseType.PERPETUAL:
            self.params_edit.setText("—")
        elif card.license_type == LicenseType.TIME_LIMITED:
            self.params_edit.setText(
                f"Expires: {card.params.expiration.strftime('%y/%m/%d %H:%M:%S')}"
                if card.params and card.params.expiration else "—")
        else:
            self.params_edit.setText(
                f"Uses: {card.params.num_uses}  |  "
                f"Hours/use: {card.params.hours_per_use}"
                if card.params else "—")

        self.checksum_edit.setText(f"{card.checksum:08X}")
        valid = card.checksum_valid()
        self.checksum_valid_label.setText("✔ Valid" if valid else "✘ INVALID")
        self.checksum_valid_label.setStyleSheet(
            "color: green; font-weight: bold;" if valid
            else "color: red; font-weight: bold;")
