# _main.py — full replacement
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QSplitter,
                               QTextEdit, QLabel, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from viewmodels.card_viewmodel import CardViewModel
from views.access_key_view import AccessKeyView
from views.card_view import CardView
from views.card_maintenance_view import CardMaintenanceView
from views.card_database_view import CardDatabaseView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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

        log_widget.setMinimumWidth(350)
        splitter.addWidget(log_widget)
        splitter.setSizes([800, 350])  # default split ratio

        self.setCentralWidget(splitter)


        self.setWindowTitle("MC3 License Card Application")
        self.resize(1200, 900)

        # Connect VM log to central log
        self.vm.logMessage.connect(self.log_text.append)
        self.vm.statusChanged.connect(self.log_text.append)
        self.vm.errorOccurred.connect(lambda m: self.log_text.append(f"❌ ERROR: {m}"))

        # Graceful shutdown
        QApplication.instance().aboutToQuit.connect(self.vm._service.stop_monitor)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MC3 License Card Application")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
