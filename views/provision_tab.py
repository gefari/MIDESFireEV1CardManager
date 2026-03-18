from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox,
    QTextEdit, QMessageBox, QComboBox, QTreeWidgetItem, QScrollArea, QTreeWidget
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QFont, QColor
from models.license_model import (
    FILE_SERIAL, FILE_TYPE, FILE_PARAMS, FILE_CHECKSUM
)
from viewmodels.card_viewmodel import CardViewModel


def mono_font() -> QFont:
    f = QFont("Courier New", 10)
    f.setFixedPitch(True)
    return f


class ProvisionTab(QWidget):

    _APP_KEY_SETTINGS = [0x0F, 0x09, 0x01, 0x00]

    _DEFAULT_KEY_MAP = {
        (FILE_SERIAL,   "read"):  2,
        (FILE_SERIAL,   "write"): 4,
        (FILE_TYPE,     "read"):  2,
        (FILE_TYPE,     "write"): 4,
        (FILE_PARAMS,   "read"):  5,
        (FILE_PARAMS,   "write"): 5,
        (FILE_CHECKSUM, "read"):  2,
        (FILE_CHECKSUM, "write"): 3,
    }
    _FREE_INDEX = 6   # combo index that maps to KEY_FREE (0xE)

    def __init__(self, vm: CardViewModel, db_view, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.db_view = db_view
        self._key_combos = {}
        self._build_ui()
        self._connect_signals()
        self._on_app_key_settings_changed(0)

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Outer scroll so the tab stays usable at small heights
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        '''
        # ══════════════════════════════════════════════════════════════════
        # SECTION 1 — Reader
        # ══════════════════════════════════════════════════════════════════
        rd_box = QGroupBox("Reader")
        rd_layout = QVBoxLayout(rd_box)

        rd_row = QHBoxLayout()
        self.btn_connect    = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.reader_label   = QLabel("—")
        rd_row.addWidget(self.btn_connect)
        rd_row.addWidget(self.btn_disconnect)
        rd_row.addWidget(self.reader_label)
        rd_row.addStretch()
        rd_layout.addLayout(rd_row)

        card_row = QHBoxLayout()
        self.card_status_label = QLabel("⬜  No card present")
        self.card_status_label.setStyleSheet("font-weight: bold; color: gray;")
        self.atr_edit = QLineEdit()
        self.atr_edit.setReadOnly(True)
        self.atr_edit.setPlaceholderText("ATR")
        self.atr_edit.setFont(mono_font())
        card_row.addWidget(self.card_status_label)
        card_row.addWidget(self.atr_edit)
        rd_layout.addLayout(card_row)

        root.addWidget(rd_box)
        '''

        # ══════════════════════════════════════════════════════════════════
        # SECTION 2 — Card UID
        # ══════════════════════════════════════════════════════════════════
        uid_box = QGroupBox("Card UID")
        uid_row = QHBoxLayout(uid_box)
        self.btn_uid  = QPushButton("Read UID")
        self.uid_edit = QLineEdit()
        self.uid_edit.setReadOnly(True)
        self.uid_edit.setFont(mono_font())
        uid_row.addWidget(self.btn_uid)
        uid_row.addWidget(self.uid_edit)

        root.addWidget(uid_box)

        # ══════════════════════════════════════════════════════════════════
        # SECTION 3 — PICC MAster Key
        # ══════════════════════════════════════════════════════════════════
        picc_master_key_box = QGroupBox("PICC Master Key")
        master_key_layout = QVBoxLayout(picc_master_key_box)

        # ── PICC Master Key input ──────────────────────────────────────────
        picc_row = QHBoxLayout()
        picc_label = QLabel("PICC Master Key:")

        self.picc_key_type_combo = QComboBox()
        self.picc_key_type_combo.addItem("DES (8B)", 8)
        self.picc_key_type_combo.addItem("2K3DES (16B)", 16)
        self.picc_key_type_combo.addItem("3K3DES (24B)", 24)
        self.picc_key_type_combo.addItem("AES-128 (16B)", 16)
        self.picc_key_type_combo.setFixedWidth(130)

        self.picc_key_edit = QLineEdit("0000000000000000")
        self.picc_key_edit.setMaxLength(16)  # DES default
        self.picc_key_edit.setFont(mono_font())
        self.picc_key_edit.setFixedWidth(260)
        self.picc_key_edit.setPlaceholderText("16 hex chars (DES)")

        self.btn_copy_picc_to_db = QPushButton("Copy Master Key to DB")
        self.btn_copy_picc_to_db.setFixedWidth(180)

        from PySide6.QtGui import QRegularExpressionValidator
        from PySide6.QtCore import QRegularExpression
        self.picc_key_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]{0,48}"))
        )

        picc_row.addWidget(picc_label)
        picc_row.addWidget(self.picc_key_type_combo)
        picc_row.addWidget(self.picc_key_edit)
        picc_row.addWidget(self.btn_copy_picc_to_db)

        picc_row.addStretch()

        master_key_layout.addLayout(picc_row)

        auth_btn_row = QHBoxLayout()
        self.btn_auth_picc = QPushButton("🔑  Card Authentication with PICC Master Key")
        self.btn_auth_picc.setFixedWidth(280)
        auth_btn_row.addWidget(self.btn_auth_picc)
        auth_btn_row.addStretch()
        master_key_layout.addLayout(auth_btn_row)

        root.addWidget(picc_master_key_box)

        # ── Change Master Key group ───────────────────────────────────────────
        chg_box = QGroupBox("Change Application Master Key")
        chg_form = QFormLayout(chg_box)

        old_row = QHBoxLayout()
        self.old_key_edit = QLineEdit()
        self.old_key_edit.setFont(mono_font())
        self.old_key_edit.setPlaceholderText("Current master key (hex)")
        self.old_key_edit.setMaxLength(48)
        old_row.addWidget(self.old_key_edit)
        chg_form.addRow("Current key:", old_row)

        new_row = QHBoxLayout()
        self.new_key_edit = QLineEdit()
        self.new_key_edit.setFont(mono_font())
        self.new_key_edit.setPlaceholderText("New master key (hex)")
        self.new_key_edit.setMaxLength(48)
        self.btn_fill_new_key = QPushButton("Fill from Key 1")
        self.btn_fill_new_key.setFixedWidth(120)
        self.btn_fill_new_key.setToolTip("Fill with Key 1 from the Access Keys tab")
        new_row.addWidget(self.new_key_edit)
        new_row.addWidget(self.btn_fill_new_key)
        chg_form.addRow("New key:", new_row)

        self.btn_change_key = QPushButton("Change Master Key")
        self.btn_change_key.setStyleSheet("font-weight: bold;")
        chg_form.addRow("", self.btn_change_key)

        root.addWidget(chg_box)

        # ══════════════════════════════════════════════════════════════════
        # SECTION 4 — Provision settings  (unchanged from original)
        # ══════════════════════════════════════════════════════════════════
        access_box = QGroupBox("Access Mode")
        access_form = QFormLayout(access_box)

        self.app_id_edit = QLineEdit("010203")
        self.app_id_edit.setMaxLength(6)
        self.app_id_edit.setFont(mono_font())
        self.app_id_edit.setPlaceholderText("6 hex chars  e.g. 010203")
        access_form.addRow("Application ID (hex):", self.app_id_edit)

        self.app_key_settings_combo = QComboBox()
        self.app_key_settings_combo.addItems([
            "0x0F  – Open (dev/test): free create/delete/list, keys changeable",
            "0x09  – Balanced (production): auth required, keys changeable",
            "0x01  – Restricted: auth required, master key changeable only",
            "0x00  – Locked: everything frozen",
        ])
        self.app_key_settings_combo.setCurrentIndex(0)
        access_form.addRow("App key settings:", self.app_key_settings_combo)

        self.app_master_key_label = QLabel("Application Master Key:")
        self.app_master_key_combo = QComboBox()
        self.app_master_key_combo.addItems(self.vm.key_store.key_names())
        self.app_master_key_combo.setCurrentIndex(0)
        access_form.addRow(self.app_master_key_label, self.app_master_key_combo)

        self.access_mode_combo = QComboBox()
        self.access_mode_combo.addItems(["Key Protected", "None (Free Access)"])
        self.access_mode_combo.setCurrentIndex(0)
        access_form.addRow("File access:", self.access_mode_combo)

        root.addWidget(access_box)

        # ── Per-file key assignments ───────────────────────────────────────
        f1_box = QGroupBox("File 1 – License Serial Number")
        f1_form = QFormLayout(f1_box)
        f1_form.addRow("Read key:",  self._make_key_combo(FILE_SERIAL,   "read",  default=1))
        f1_form.addRow("Write key:", self._make_key_combo(FILE_SERIAL,   "write", default=3))
        root.addWidget(f1_box)

        f2_box = QGroupBox("File 2 – License Type")
        f2_form = QFormLayout(f2_box)
        f2_form.addRow("Read key:",  self._make_key_combo(FILE_TYPE,     "read",  default=1))
        f2_form.addRow("Write key:", self._make_key_combo(FILE_TYPE,     "write", default=3))
        root.addWidget(f2_box)

        f3_box = QGroupBox("File 3 – License Parameters")
        f3_form = QFormLayout(f3_box)
        f3_form.addRow("Read key:",  self._make_key_combo(FILE_PARAMS,   "read",  default=4))
        f3_form.addRow("Write key:", self._make_key_combo(FILE_PARAMS,   "write", default=4))
        root.addWidget(f3_box)

        f4_box = QGroupBox("File 4 – Checksum")
        f4_form = QFormLayout(f4_box)
        f4_form.addRow("Read key:",  self._make_key_combo(FILE_CHECKSUM, "read",  default=1))
        f4_form.addRow("Write key:", self._make_key_combo(FILE_CHECKSUM, "write", default=2))
        root.addWidget(f4_box)

        # ── Provision button + log ─────────────────────────────────────────
        self.btn_provision = QPushButton("⚙  Provision Card (Create App + Files)")
        self.btn_provision.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self.btn_provision)

        self.status_label = QLabel("Ready.")
        root.addWidget(self.status_label)

        log_header_row = QHBoxLayout()
        log_label = QLabel("Provision log:")
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setFixedWidth(80)
        log_header_row.addWidget(log_label)
        log_header_row.addStretch()
        log_header_row.addWidget(self.btn_clear_log)
        self.provision_log = QTextEdit()

        root.addLayout(log_header_row)  # replaces root.addWidget(log_label)
        root.addWidget(self.provision_log)

        root.addStretch()

        self.apps_tree = QTreeWidget()

    def _make_key_combo(self, file_id: int, role: str, default: int) -> QComboBox:
        combo = QComboBox()
        combo.addItems(self.vm.key_store.key_names())
        combo.setCurrentIndex(default)
        self.vm.set_file_key(file_id, role, default)
        combo.currentIndexChanged.connect(
            lambda idx, fid=file_id, r=role: self.vm.set_file_key(fid, r, idx)
        )
        self._key_combos[(file_id, role)] = combo
        return combo

    # ── Signals ───────────────────────────────────────────────────────────
    def _connect_signals(self):

        # Action on combo index changed
        self.app_master_key_combo.currentIndexChanged.connect(
            self.vm.set_app_master_key)
        self.app_key_settings_combo.currentIndexChanged.connect(
            self._on_app_key_settings_changed)
        self.access_mode_combo.currentIndexChanged.connect(
            self._on_access_mode_changed)
        self.picc_key_type_combo.currentIndexChanged.connect(
            self._on_picc_key_type_changed)

        # Actions on button clicked in provision tab
        #self.btn_connect.clicked.connect(self.vm.connect_reader)
        #self.btn_disconnect.clicked.connect(self.vm.disconnect_reader)
        self.btn_uid.clicked.connect(self.vm.read_uid)
        self.btn_provision.clicked.connect(self._on_provision)
        self.btn_auth_picc.clicked.connect(self._on_auth_picc)
        self.btn_copy_picc_to_db.clicked.connect(self._on_copy_picc_to_db)
        self.btn_fill_new_key.clicked.connect(self._on_fill_new_key)
        self.btn_change_key.clicked.connect(self._on_change_key)
        self.btn_clear_log.clicked.connect(self.provision_log.clear)

        # Connect provision to view model signal
        self.vm.uidRead.connect(self.uid_edit.setText)
        self.vm.keyStoreChanged.connect(self._refresh_key_combos)
        self.vm.appsRead.connect(self._populate_apps)
        self.vm.provisionLog.connect(self.provision_log.append)
        self.vm.authResult.connect(self._on_auth_result)
        self.vm.keyChanged.connect(self._on_key_changed)
        self.vm.keyStoreChanged.connect(self._on_keys_changed)
        self.vm.statusChanged.connect(self.status_label.setText)
        self.vm.errorOccurred.connect(
            lambda m: QMessageBox.critical(self, "Error", m))
        #self.vm.readerFound.connect(self.reader_label.setText)
        #self.vm.cardInserted.connect(self._on_card_inserted)
        #self.vm.cardRemoved.connect(self._on_card_removed)
    '''
    # ── Card presence ─────────────────────────────────────────────────────
    @Slot(str)
    def _on_card_inserted(self, atr: str):
        self.card_status_label.setText("🟢  Card present")
        self.card_status_label.setStyleSheet("font-weight: bold; color: green;")
        self.atr_edit.setText(atr)

    @Slot()
    def _on_card_removed(self):
        self.card_status_label.setText("⬜  No card present")
        self.card_status_label.setStyleSheet("font-weight: bold; color: gray;")
        self.atr_edit.clear()
        self.uid_edit.clear()
        self.apps_tree.clear()
    '''

    # ── Applications tree ─────────────────────────────────────────────────
    @Slot(list)
    def _populate_apps(self, apps: list):
        self.apps_tree.clear()
        if not apps:
            self.apps_tree.addTopLevelItem(
                QTreeWidgetItem(["No applications found"])
            )
            return
        for entry in apps:
            aid = entry["aid"]
            label = aid + ("  ← MC3" if aid.upper() == "010203" else "")
            app_item = QTreeWidgetItem([label, "", "", "", "", "", "", ""])
            if aid.upper() == "010203":
                for col in range(8):
                    app_item.setForeground(col, QColor("darkgreen"))
            app_item.setExpanded(True)
            self.apps_tree.addTopLevelItem(app_item)
            for fs in entry["files"]:
                if fs.get("error"):
                    child = QTreeWidgetItem([
                        f"  File 0x{fs['file_id']:02X}",
                        "Error", "", "", "", "", "", "",
                    ])
                else:
                    child = QTreeWidgetItem([
                        f"  File 0x{fs['file_id']:02X}",
                        fs["type"], fs["comm_mode"],
                        f"{fs['size']} B",
                        fs["read"], fs["write"], fs["rw"], fs["change"],
                    ])
                app_item.addChild(child)
        self.apps_tree.expandAll()

    # ── Key settings ──────────────────────────────────────────────────────
    @Slot(int)
    def _on_app_key_settings_changed(self, idx: int):
        visible = idx != 0
        self.app_master_key_label.setVisible(visible)
        self.app_master_key_combo.setVisible(visible)

    @Slot(int)
    def _on_access_mode_changed(self, idx: int):
        if idx == 1:
            for (fid, role), combo in self._key_combos.items():
                combo.blockSignals(True)
                combo.setCurrentIndex(self._FREE_INDEX)
                combo.blockSignals(False)
                self.vm.set_file_key(fid, role, self._FREE_INDEX)
        else:
            for (fid, role), combo in self._key_combos.items():
                default = self._DEFAULT_KEY_MAP.get((fid, role), 0)
                combo.blockSignals(True)
                combo.setCurrentIndex(default)
                combo.blockSignals(False)
                self.vm.set_file_key(fid, role, default)

    @Slot()
    def _refresh_key_combos(self):
        names = self.vm.key_store.key_names()
        for combo in self._key_combos.values():
            current = combo.currentIndex()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            combo.setCurrentIndex(current)
            combo.blockSignals(False)
        current = self.app_master_key_combo.currentIndex()
        self.app_master_key_combo.blockSignals(True)
        self.app_master_key_combo.clear()
        self.app_master_key_combo.addItems(names)
        self.app_master_key_combo.setCurrentIndex(current)
        self.app_master_key_combo.blockSignals(False)

    # ── Provision ─────────────────────────────────────────────────────────
    @Slot()
    def _on_provision(self):
        self.vm.set_app_id(self.app_id_edit.text())
        self.vm.provision_app()

    # ── Authentication ─────────────────────────────────────────────────────
    @Slot()
    def _on_auth_picc(self):
        picc_key_hex = self.picc_key_edit.text().replace(" ", "")
        key_type = self.picc_key_type_combo.currentText()
        self.provision_log.append(f"Authenticating PICC ({key_type}): {picc_key_hex}")
        self.vm.test_authentication_picc(picc_key_hex)

    @Slot(bool, str)
    def _on_auth_result(self, success: bool, msg: str):
        if success:
            self.provision_log.append(f"✅ {msg}")
        else:
            self.provision_log.append(f"❌ {msg}")

    @Slot(int)
    def _on_picc_key_type_changed(self, index: int):
        hex_len = self.picc_key_type_combo.currentData() * 2  # bytes → hex chars
        labels = {16: "16 hex chars (DES)",
                  32: "32 hex chars (2K3DES / AES)",
                  48: "48 hex chars (3K3DES)"}
        self.picc_key_edit.setMaxLength(hex_len)
        self.picc_key_edit.setPlaceholderText(labels.get(hex_len, f"{hex_len} hex chars"))
        # Pad or truncate current value to new length
        current = self.picc_key_edit.text().ljust(hex_len, '0')[:hex_len]
        self.picc_key_edit.setText(current)

    @Slot()
    def _on_copy_picc_to_db(self):
        picc_hex = self.picc_key_edit.text().replace(" ", "")
        selected = {idx.row() for idx in self.db_view.table.selectedIndexes()}
        if selected:
            # Write PICC key into the selected row's PICC column
            row = self.db_view.table.currentRow()
            from PySide6.QtWidgets import QTableWidgetItem
            item = QTableWidgetItem(picc_hex)
            item.setFont(mono_font())
            self.db_view.table.setItem(row, self.db_view.COL["picc_master_key"], item)
            self.status_label.setText("PICC master key written to selected DB row.")
        else:
            # No row selected — create a new row with just the PICC key filled
            self.db_view.copy_keys_to_new_row(picc_key_hex=picc_hex)
            self.status_label.setText("PICC master key copied to new DB row.")

    @Slot()
    def _on_fill_new_key(self):
        """Fill the new key field from Key 1 in the KeyStore."""
        key = self.vm.key_store.get(0)  # Key 1 = index 0
        self.new_key_edit.setText(key.hex())

    @Slot()
    def _on_change_key(self):
        old_hex = self.old_key_edit.text().replace(" ", "")
        new_hex = self.new_key_edit.text().replace(" ", "")
        if not old_hex or not new_hex:
            QMessageBox.warning(self, "Missing Key", "Enter both current and new key.")
            return
        confirm = QMessageBox.question(
            self, "Confirm Key Change",
            "This will permanently change the application master key.\n"
            "Make sure the new key is saved before proceeding.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.vm.change_master_key(old_hex, new_hex)

    @Slot(bool, str)
    def _on_key_changed(self, success: bool, msg: str):
        self.status_label.setText(msg)
        if success:
            # Move new key into the current key field for the next operation
            self.old_key_edit.setText(self.new_key_edit.text())
            self.new_key_edit.clear()

    @Slot()
    def _on_keys_changed(self):
        """Keep PICC key edit in sync with KeyStore index 0."""
        key = self.vm.key_store.get(0)
        self.picc_key_edit.setText(key.hex())