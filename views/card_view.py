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
    def set_file_id_read_access(self, fid: int, access: str):
        """Populate read-key hint labels in Read/Write tabs from the Maintenance tree.

        The access value ("Key 2", "Free", etc.) is an access descriptor, not a
        hex key string, so we clear the hex override fields — the KeyStore fallback
        then picks the right key automatically.
        """
        _MAP = {
            1: (self.read_tab.serial_read_key_edit,   self.write_tab.serial_r_key_edit),
            2: (self.read_tab.lic_type_read_key_edit, self.write_tab.lic_type_r_key_edit),
            3: (self.read_tab.params_read_key_edit,   self.write_tab.params_r_key_edit),
            4: (self.read_tab.test_read_key_edit,     self.write_tab.test_r_key_edit),
            5: (self.read_tab.chksum_read_key_edit,   self.write_tab.chksum_r_key_edit),
        }
        for edit in _MAP.get(fid, ()):
            edit.clear()

    @Slot(str)
    def set_file_id_write_access(self, fid: int, access: str):
        """Populate write-key hint labels in the Write tab from the Maintenance tree."""
        _MAP = {
            1: self.write_tab.serial_w_key_edit,
            2: self.write_tab.lic_type_w_key_edit,
            3: self.write_tab.params_w_key_edit,
            4: self.write_tab.test_w_key_edit,
            5: self.write_tab.chksum_w_key_edit,
        }
        edit = _MAP.get(fid)
        if edit:
            edit.clear()

