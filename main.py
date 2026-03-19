import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QSplitter,
                               QTextEdit, QLabel, QVBoxLayout, QHBoxLayout, QWidget,
                               QGroupBox, QGridLayout, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from viewmodels.card_viewmodel import CardViewModel
from views.access_key_view import AccessKeyView
from views.card_view import CardView
from views.card_maintenance_view import CardMaintenanceView
from views.card_database_view import CardDatabaseView


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication):
        super().__init__()
        self.setWindowTitle("MI DES Fire EV1 Card Manager")
        self.resize(1200, 900)

        self.vm     = CardViewModel()
        self.db_tab = CardDatabaseView(self.vm)

        # ── Central splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Tabs ─────────────────────────────────────────────────────────
        #tabs = QTabWidget()
        self.tabs = QTabWidget()

        self.card_view = CardView(self.vm, self.db_tab)  # tab 0
        self.maintenance = CardMaintenanceView(self.vm)  # tab 1

        self.tabs.addTab(self.card_view, "Card Manager")
        self.tabs.addTab(self.maintenance, "Card Maintenance")
        self.tabs.addTab(self.db_tab, "Card Database")
        self.tabs.addTab(AccessKeyView(self.vm, self.db_tab), "Card Access Keys Generation")

        # ── AID selected in Maintenance → sync Write + Provision tabs ────
        self.maintenance.aidSelected.connect(self.card_view.set_app_id)

        self.maintenance.aidSelected.connect(
            lambda _: self.tabs.setCurrentWidget(self.card_view)
        )

        self.tabs.setMinimumWidth(800)
        splitter.addWidget(self.tabs)

        # ── Right panel (NFC Reader + Log) ────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # ── NFC Reader Group Box ──────────────────────────────────────────
        nfc_group = QGroupBox("NFC Reader")
        nfc_layout = QGridLayout(nfc_group)
        nfc_layout.setContentsMargins(8, 12, 8, 8)
        nfc_layout.setSpacing(6)

        self.btn_refresh_readers = QPushButton("🔄 NFC Reader Scan")
        nfc_layout.addWidget(self.btn_refresh_readers, 0, 1)

        nfc_layout.addWidget(QLabel("Reader Description:"), 1, 0)
        self.lbl_reader_description = QLabel("No reader detected")
        self.lbl_reader_description.setStyleSheet("color: gray; font-style: italic;")
        nfc_layout.addWidget(self.lbl_reader_description, 1, 1, 1, 2)

        nfc_layout.addWidget(QLabel("Card Status:"), 2, 0)
        self.lbl_card_status = QLabel("No card detected")
        self.lbl_card_status.setStyleSheet("color: gray; font-style: italic;")
        nfc_layout.addWidget(self.lbl_card_status, 2, 1, 1, 2)

        nfc_layout.addWidget(QLabel("Card Type:"), 3, 0)
        self.lbl_card_type = QLabel("Unknown card type")
        self.lbl_card_type.setFont(QFont("Courier New", 9))
        nfc_layout.addWidget(self.lbl_card_type, 3, 1, 1, 2)

        right_layout.addWidget(nfc_group)

        # ── Log panel ────────────────────────────────────────────────────
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(8, 8, 8, 8)

        # ── Log header row (label + clear button) ─────────────────────────
        log_header_row = QHBoxLayout()
        log_header = QLabel("Application Log")
        log_header.setStyleSheet("font-weight: bold; padding-bottom: 4px;")
        self.btn_clear_log = QPushButton("🗑 Clear")
        self.btn_clear_log.setFixedWidth(70)
        self.btn_clear_log.setStyleSheet("font-size: 11px;")
        log_header_row.addWidget(log_header)
        log_header_row.addStretch()
        log_header_row.addWidget(self.btn_clear_log)
        log_layout.addLayout(log_header_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log_text)

        right_layout.addWidget(log_widget)

        right_widget.setMinimumWidth(350)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

        # ── NFC signal wiring ─────────────────────────────────────────────
        self.btn_refresh_readers.clicked.connect(self._find_reader)
        self.btn_clear_log.clicked.connect(self.log_text.clear)
        self.vm.cardInserted.connect(self._on_card_inserted)
        self.vm.cardRemoved.connect(self._on_card_removed)
        self.vm.readerFound.connect(self._on_reader_found)

        # ── VM log wiring ─────────────────────────────────────────────────
        self.vm.logMessage.connect(self.log_text.append)
        self.vm.statusChanged.connect(self._on_status_changed)
        self.vm.errorOccurred.connect(lambda m: self.log_text.append(f"❌ ERROR: {m}"))

        # Graceful shutdown
        app.aboutToQuit.connect(self.vm.stop)

        # Populate readers on startup
        self.vm.find_reader()

    # ── NFC Reader slots ──────────────────────────────────────────────────
    def _find_reader(self):
        self.vm.find_reader()

    def _disconnect_reader(self):
        self.vm.disconnect_reader()
        self.lbl_card_status.setText("No card detected")
        self.lbl_card_status.setStyleSheet("color: gray; font-style: italic;")

    def _on_card_inserted(self, atr: str):
        self.lbl_card_status.setText("✅ Card present")
        self.lbl_card_status.setStyleSheet("color: green; font-weight: bold;")
        DESFIRE_ATR_PREFIX = "3B8180"
        if atr.replace(" ", "").upper().startswith(DESFIRE_ATR_PREFIX):
            self.lbl_card_type.setText("DESFire EV1 card detected")
            self.vm.connect_reader()
        else:
            self.lbl_card_type.setText("⚠ Unknown card type")

    def _on_card_removed(self):
        self.lbl_card_status.setText("⚠️ Card removed")
        self.lbl_card_status.setStyleSheet("color: orange; font-style: italic;")
        self.lbl_card_type.setText("—")
        self.vm.disconnect_reader()

    def _on_reader_found(self):
        self.vm.connect_reader()

    def _on_status_changed(self, status: str):
        if "Reader found" in status:
            self.lbl_reader_description.setText("uTrust 3720 (Found)")
        elif "Connected to uTrust 3720F HF" in status:
            self.lbl_reader_description.setText("uTrust 3720 (Connected)")
        elif "Disconnected" in status:
            self.lbl_reader_description.setText("uTrust 3720 (Disconnected)")
        elif "Card removed." in status:
            self.lbl_reader_description.setText("uTrust 3720 (Card removed)")
        self.log_text.append(status)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MC3 License Card Application")
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
