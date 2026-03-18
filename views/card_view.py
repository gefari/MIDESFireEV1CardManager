from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget
)

from viewmodels.card_viewmodel import CardViewModel
from views.provision_tab import ProvisionTab
from views.write_tab import WriteTab
from views.read_tab import ReadTab

# ══════════════════════════════════════════════════════════════════════════════
# LicenseView — outer container with inner tab widget
# ══════════════════════════════════════════════════════════════════════════════
class CardView(QWidget):
    """
        Top-level view composed of three tabs:
          ⚙ Provision  — create DESFire application + files
          ✎ Write      — write license data to card
          ⟳ Read       — read and verify card contents
        """
    def __init__(self, vm: CardViewModel, db_view, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.db_view = db_view
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(ProvisionTab(vm=self.vm, db_view=self.db_view), "⚙ Provision")
        tabs.addTab(WriteTab(vm=self.vm), "✎ Write")
        tabs.addTab(ReadTab(vm=self.vm), "⟳ Read")
        root.addWidget(tabs)
