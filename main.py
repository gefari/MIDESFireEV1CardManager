# _main.py — full replacement
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QSplitter,
                               QTextEdit, QLabel, QVBoxLayout, QWidget,
                               QGroupBox, QGridLayout, QPushButton, QComboBox,
                               QHBoxLayout)
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
        self.setWindowTitle("MC3 License Card Application")
        self.resize(1200, 900)

        self.vm     = CardViewModel()
        self.db_tab = CardDatabaseView(self.vm)

        # ── Central splitter ─────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Tabs ─────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.addTab(CardView(self.vm, self.db_tab), "Card Manager")
        tabs.addTab(CardMaintenanceView(self.vm), "Card Maintenance")
        tabs.addTab(self.db_tab, "Card Database")
        tabs.addTab(AccessKeyView(self.vm, self.db_tab), "Card Access Keys Generation")

        tabs.setMinimumWidth(800)
        splitter.addWidget(tabs)

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

        # Reader selector
        self.btn_refresh_readers = QPushButton("🔄 NFC Reader Scan")
        nfc_layout.addWidget(self.btn_refresh_readers, 0, 1)

        # Reader Description
        nfc_layout.addWidget(QLabel("Reader Description:"), 1, 0)
        self.lbl_reader_description = QLabel("No reader detected")
        self.lbl_reader_description.setStyleSheet("color: gray; font-style: italic;")
        nfc_layout.addWidget(self.lbl_reader_description, 1, 1, 1, 2)

        # Card status
        nfc_layout.addWidget(QLabel("Card Status:"), 2, 0)
        self.lbl_card_status = QLabel("No card detected")
        self.lbl_card_status.setStyleSheet("color: gray; font-style: italic;")
        nfc_layout.addWidget(self.lbl_card_status, 2, 1, 1, 2)

        # Card Type
        nfc_layout.addWidget(QLabel("Card Type:"), 3, 0)
        self.lbl_card_type = QLabel("Unknown card type")
        self.lbl_card_type.setFont(QFont("Courier New", 9))
        nfc_layout.addWidget(self.lbl_card_type, 3, 1, 1, 2)

        right_layout.addWidget(nfc_group)

        # ── Log panel ────────────────────────────────────────────────────
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(8, 8, 8, 8)

        log_header = QLabel("Application Log")
        log_header.setStyleSheet("font-weight: bold; padding-bottom: 4px;")
        log_layout.addWidget(log_header)

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
        #self.btn_connect.clicked.connect(self._connect_reader)
        #self.btn_disconnect.clicked.connect(self._disconnect_reader)
        self.vm.cardInserted.connect(self._on_card_inserted)
        self.vm.cardRemoved.connect(self._on_card_removed)
        self.vm.readerFound.connect(self._on_reader_found)

        # ── VM log wiring ─────────────────────────────────────────────────
        self.vm.logMessage.connect(self.log_text.append)
        self.vm.statusChanged.connect(self._on_status_changed)
        self.vm.errorOccurred.connect(lambda m: self.log_text.append(f"❌ ERROR: {m}"))

        # Graceful shutdown
        #app.aboutToQuit.connect(self.vm._service.stop_monitor)

        # Populate readers on startup
        self.vm.find_reader()

    # ── NFC Reader slots ──────────────────────────────────────────────────
    def _find_reader(self):
        self.vm.find_reader()

    def _disconnect_reader(self):
        self.vm.disconnect_reader()              # expected VM method
        #self.btn_connect.setEnabled(True)
        #self.btn_disconnect.setEnabled(False)
        self.lbl_card_status.setText("No card detected")
        self.lbl_card_status.setStyleSheet("color: gray; font-style: italic;")
        #self.lbl_card_atr.setText("—")

    def _on_card_inserted(self, atr: str):
        self.lbl_card_status.setText("✅ Card present")
        self.lbl_card_status.setStyleSheet("color: green; font-weight: bold;")
        DESFIRE_ATR = "3B 81 80 01 80 80"
        if atr.upper() == DESFIRE_ATR:
            self.lbl_card_type.setText(f"DESFire EV1 card detected")
            self.vm.connect_reader()
        else:
            self.lbl_card_type.setText(f"⚠ Unknown card type")

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
