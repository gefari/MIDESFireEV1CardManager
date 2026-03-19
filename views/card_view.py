from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget
)
from PySide6.QtCore import Slot

from viewmodels.card_viewmodel import CardViewModel
from views.provision_tab import ProvisionTab
from views.write_tab import WriteTab
from views.read_tab import ReadTab


class CardView(QWidget):
    """
    Top-level view composed of three tabs:
      ⚙ Provision  — create DESFire application + files
      ✎ Write      — write license data to card
      ⟳ Read       — read and verify card contents
    """
    def __init__(self, vm: CardViewModel, db_view, parent=None):
        super().__init__(parent)
        self.vm = vm                                      # ← was missing

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        self.provision_tab = ProvisionTab(vm, db_view)
        self.write_tab     = WriteTab(vm)
        self.read_tab      = ReadTab(vm)

        self.tabs.addTab(self.provision_tab, "⚙  Provision")
        self.tabs.addTab(self.write_tab,     "✎  Write")
        self.tabs.addTab(self.read_tab,      "⟳  Read")

        layout.addWidget(self.tabs)                       # ← was missing

        # ── License type → File 3 size + label ───────────────────────────
        self.write_tab.license_type_combo.currentIndexChanged.connect(
            self.vm.set_license_type
        )
        self.write_tab.license_type_combo.currentIndexChanged.connect(
            self.provision_tab.on_license_type_changed
        )

        # Set initial state from WriteTab's default (index 0 = Perpetual)
        initial_idx = self.write_tab.license_type_combo.currentIndex()
        self.vm.set_license_type(initial_idx)
        self.provision_tab.on_license_type_changed(initial_idx)

    @Slot(str)
    def set_app_id(self, aid: str):
        """Sync app ID across Write and Provision tabs."""
        self.write_tab.app_id_edit.setText(aid)
        self.read_tab.app_id_edit.setText(aid)
        self.provision_tab.app_id_edit.setText(aid)

    @Slot(str)
    def set_file_id_read_access(self, fid: str, access: str):
        """Sync file ID across Write and Provision tabs."""
        #print(f"file id:{fid} -> read access: {access}")
        if fid == 1:
            self.read_tab.serial_read_key_edit.setText(access)
        elif fid == 2:
            self.read_tab.lic_type_read_key_edit.setText(access)
        elif fid == 3:
            self.read_tab.params_read_key_edit.setText(access)
        elif fid == 4:
            self.read_tab.chksum_read_key_edit.setText(access)
        else:
            print(f"Unknown Error!")

    @Slot(str)
    def set_file_id_write_access(self, fid: str, access: str):
        """Sync file ID across Write and Provision tabs."""
        # print(f"file id:{fid} -> read access: {access}")
        if fid == 1:
            self.write_tab.serial_write_key_edit.setText(access)
        elif fid == 2:
            self.write_tab.lic_type_write_key_edit.setText(access)
        elif fid == 3:
            self.write_tab.params_write_key_edit.setText(access)
        elif fid == 4:
            self.write_tab.chksum_write_key_edit.setText(access)
        else:
            print(f"Unknown Error!")

