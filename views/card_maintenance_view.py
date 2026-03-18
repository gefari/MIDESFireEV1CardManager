from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox,
    QTextEdit, QMessageBox, QTreeWidget, QTreeWidgetItem, QComboBox,
)
from PySide6.QtCore import Slot
from viewmodels.card_viewmodel import CardViewModel
from PySide6.QtGui import QFont, QColor

def mono_font() -> QFont:
    f = QFont("Courier New", 10)
    f.setFixedPitch(True)
    return f

class CardMaintenanceView(QWidget):
    def __init__(self, viewmodel: CardViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self.setWindowTitle("MC3 License Card – Test Panel")
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        root = QVBoxLayout(self)

        '''
        # ── Reader Discovery ───────────────────────────────────────────
        rd_box = QGroupBox("Reader")
        rd_layout = QVBoxLayout(rd_box)

        rd_row = QHBoxLayout()

        self.btn_find = QPushButton("Find uTrust 3720F HF")
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.reader_label = QLabel("—")
        rd_row.addWidget(self.btn_find)
        rd_row.addWidget(self.btn_connect)
        rd_row.addWidget(self.btn_disconnect)
        rd_row.addWidget(self.reader_label)
        rd_row.addStretch()
        rd_layout.addLayout(rd_row)

        # Card presence indicator
        card_row = QHBoxLayout()
        self.card_status_label = QLabel("⬜  No card present")
        self.card_status_label.setStyleSheet("font-weight: bold; color: gray;")
        self.atr_edit = QLineEdit()
        self.atr_edit.setReadOnly(True)
        self.atr_edit.setPlaceholderText("ATR")
        card_row.addWidget(self.card_status_label)
        card_row.addWidget(self.atr_edit)
        rd_layout.addLayout(card_row)

        root.addWidget(rd_box)
        '''
        # ── Card UID ───────────────────────────────────────────────
        uid_box = QGroupBox("Card UID")
        uid_row = QHBoxLayout(uid_box)
        self.btn_uid   = QPushButton("Read UID")
        self.uid_edit  = QLineEdit()
        self.uid_edit.setReadOnly(True)
        uid_row.addWidget(self.btn_uid)
        uid_row.addWidget(self.uid_edit)
        root.addWidget(uid_box)

        # ── Applications ───────────────────────────────────────────────────
        app_box = QGroupBox("Card Applications")
        app_layout = QVBoxLayout(app_box)

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

        from PySide6.QtGui import QRegularExpressionValidator
        from PySide6.QtCore import QRegularExpression
        self.picc_key_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]{0,48}"))
        )

        picc_row.addWidget(picc_label)
        picc_row.addWidget(self.picc_key_type_combo)
        picc_row.addWidget(self.picc_key_edit)
        picc_row.addStretch()
        app_layout.addLayout(picc_row)

        auth_btn_row = QHBoxLayout()
        self.btn_auth_picc = QPushButton("🔑  Authenticate PICC Master Key")
        self.btn_auth_picc.setFixedWidth(220)
        auth_btn_row.addWidget(self.btn_auth_picc)
        auth_btn_row.addStretch()
        app_layout.addLayout(auth_btn_row)

        app_btn_row = QHBoxLayout()
        self.btn_read_apps = QPushButton("Read All Applications")
        app_btn_row.addWidget(self.btn_read_apps)
        app_btn_row.addStretch()
        app_layout.addLayout(app_btn_row)

        self.apps_tree = QTreeWidget()
        self.apps_tree.setHeaderLabels(["AID", "Files", ""])
        self.apps_tree.setColumnWidth(0, 180)
        self.apps_tree.setColumnWidth(1, 200)
        self.apps_tree.setColumnWidth(2, 80)
        self.apps_tree.setMinimumHeight(150)
        self.apps_tree.setAlternatingRowColors(True)
        app_layout.addWidget(self.apps_tree)

        root.addWidget(app_box)

        # ── Erase ──────────────────────────────────────────────────
        erase_box = QGroupBox("Card Erase")
        erase_row = QHBoxLayout(erase_box)
        self.btn_erase = QPushButton("⚠  Erase Card (FormatPICC)")
        self.btn_erase.setStyleSheet("color: red; font-weight: bold;")
        erase_row.addWidget(self.btn_erase)
        erase_row.addStretch()
        root.addWidget(erase_box)

        '''
        # ── Log ────────────────────────────────────────────────────
        log_header_row = QHBoxLayout()
        log_label = QLabel("Log:")
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setFixedWidth(80)
        log_header_row.addWidget(log_label)
        log_header_row.addStretch()
        log_header_row.addWidget(self.btn_clear_log)
        root.addLayout(log_header_row)
        '''
        self.log_box = QTextEdit()
        #self.log_box.setReadOnly(True)
        #root.addWidget(self.log_box)


    def _connect_signals(self):
        #self.btn_find.clicked.connect(self.vm.find_reader)
        #self.btn_connect.clicked.connect(self.vm.connect_reader)
        #self.btn_disconnect.clicked.connect(self.vm.disconnect_reader)
        self.btn_uid.clicked.connect(self.vm.read_uid)
        self.btn_erase.clicked.connect(self._on_erase)

        #self.vm.readerFound.connect(self.reader_label.setText)
        self.vm.uidRead.connect(self.uid_edit.setText)
        self.vm.statusChanged.connect(self._log)
        self.vm.errorOccurred.connect(lambda m: self._log(f"ERROR: {m}"))

        # Card presence
        #self.vm.cardInserted.connect(self._on_card_inserted)
        #self.vm.cardRemoved.connect(self._on_card_removed)

        self.btn_read_apps.clicked.connect(self._on_read_apps)
        self.vm.appsRead.connect(self._populate_apps)

        self.btn_read_apps.clicked.connect(self._on_read_apps)
        self.vm.appsRead.connect(self._populate_apps)
        self.vm.appDeleted.connect(self._on_app_deleted)
        self.vm.logMessage.connect(self._log)

        self.btn_auth_picc.clicked.connect(self._on_auth_picc)
        self.vm.authResult.connect(self._on_auth_result)

        self.picc_key_type_combo.currentIndexChanged.connect(self._on_picc_key_type_changed)

        #self.btn_clear_log.clicked.connect(self.log_box.clear)
    '''
    @Slot(str)
    def _on_card_inserted(self, atr: str):
        self.card_status_label.setText("🟢  Card present")
        self.card_status_label.setStyleSheet("font-weight: bold; color: green;")
        self.atr_edit.setText(atr)
        self._log(f"Card inserted — ATR: {atr}")

    @Slot()
    def _on_card_removed(self):
        self.card_status_label.setText("⬜  No card present")
        self.card_status_label.setStyleSheet("font-weight: bold; color: gray;")
        self.atr_edit.clear()
        self.uid_edit.clear()
        self._log("Card removed.")
    '''
    @Slot()
    def _on_erase(self):
        confirm = QMessageBox.question(
            self, "Confirm Erase",
            "This will permanently delete ALL applications and files.\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            picc_key_hex = self.picc_key_edit.text().replace(" ", "")
            self._log(f"Erase Card, PICC key:{self.picc_key_edit.text()}")
            self.vm.erase_card(picc_key_hex)

    @Slot(str)
    def _log(self, msg: str):
        self.log_box.append(msg)


    @Slot()
    def _on_read_apps(self):
        self.vm.connect_reader()
        self.vm.read_applications()

    @Slot(list)
    def _populate_apps(self, apps: list):
        self.apps_tree.clear()
        self.apps_tree.setHeaderLabels([
            "AID / File", "Type", "Comm Mode",
            "Size", "Read", "Write", "R/W", "Change", ""
        ])
        self.apps_tree.setColumnWidth(0, 160)
        self.apps_tree.setColumnWidth(1, 70)
        self.apps_tree.setColumnWidth(2, 80)
        self.apps_tree.setColumnWidth(3, 50)
        self.apps_tree.setColumnWidth(4, 55)
        self.apps_tree.setColumnWidth(5, 55)
        self.apps_tree.setColumnWidth(6, 45)
        self.apps_tree.setColumnWidth(7, 55)
        self.apps_tree.setColumnWidth(8, 75)

        if not apps:
            self.apps_tree.addTopLevelItem(
                QTreeWidgetItem(["No applications found"])
            )
            return

        for entry in apps:
            aid = entry["aid"]
            label = aid + ("  ← MC3" if aid.upper() == "010203" else "")

            # Top-level AID row
            app_item = QTreeWidgetItem([label, "", "", "", "", "", "", "", ""])
            if aid.upper() == "010203":
                for col in range(8):
                    app_item.setForeground(col, QColor("darkgreen"))
            app_item.setExpanded(True)
            self.apps_tree.addTopLevelItem(app_item)

            # Delete button on AID row
            btn_delete = QPushButton("🗑 Delete")
            btn_delete.setFixedWidth(75)
            btn_delete.setStyleSheet("color: red;")
            btn_delete.clicked.connect(
                lambda checked=False, a=aid: self._on_delete_app(a)
            )
            self.apps_tree.setItemWidget(app_item, 8, btn_delete)

            # Child rows — one per file
            for fs in entry["files"]:
                if fs.get("error"):
                    child = QTreeWidgetItem([
                        f"  File 0x{fs['file_id']:02X}",
                        "Error", "", "", "", "", "", "", ""
                    ])
                else:
                    child = QTreeWidgetItem([
                        f"  File 0x{fs['file_id']:02X}",
                        fs["type"],
                        fs["comm_mode"],
                        f"{fs['size']} B",
                        fs["read"],
                        fs["write"],
                        fs["rw"],
                        fs["change"],
                        "",
                    ])
                app_item.addChild(child)

        self.apps_tree.expandAll()
        #self._log(f"Applications loaded: {[e['aid'] for e in apps]}")

    @Slot(str)
    def _on_delete_app(self, aid: str):
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete application {aid} and all its files?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            picc_key_hex = self.picc_key_edit.text().replace(" ", "")
            self._log(f"Delete App - aid:{aid}, PICC key:{self.picc_key_edit.text()}")
            self.vm.delete_application(aid, picc_key_hex)

    @Slot(str)
    def _on_app_deleted(self, aid: str):
        self._log(f"Application {aid} deleted.")
        # Refresh the list automatically
        self.vm.connect_reader()
        self.vm.read_applications()

    @Slot()
    def _on_auth_picc(self):
        picc_key_hex = self.picc_key_edit.text().replace(" ", "")
        key_type = self.picc_key_type_combo.currentText()
        self._log(f"Authenticating PICC ({key_type}): {picc_key_hex}")
        self.vm.test_authentication_picc(picc_key_hex)

    @Slot(bool, str)
    def _on_auth_result(self, success: bool, msg: str):
        if success:
            self._log(f"✅ {msg}")
        else:
            self._log(f"❌ {msg}")

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
