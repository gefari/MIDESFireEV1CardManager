import csv
import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QLineEdit, QAbstractItemView,
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QFont, QColor
from viewmodels.card_viewmodel import CardViewModel
from datetime import datetime, timezone

_CSV_COLUMNS = [
    "uid",
    "key0 - picc_master",
    "key1 - app_master",
    "key2 - File access",
    "key3 - File access",
    "key4 - File access",
    "key5 - File access",
    "timestamp",
    "notes",
]

def _mono_font() -> QFont:
    f = QFont("Courier New", 9)
    f.setFixedPitch(True)
    return f


class CardDatabaseView(QWidget):
    """
    Tab view for the card provisioning database.

    Each row stores:
      - Card UID (7-byte hex)
      - PICC master key (hex)
      - Key 1-5 from the KeyStore (hex)
      - Timestamp (UTC ISO-8601)
      - Free-text notes

    Persistence: CSV via append-to-file / load-from-file.
    """

    COL = {name: i for i, name in enumerate(_CSV_COLUMNS)}

    #def __init__(self, vm: CardViewModel, db_view, parent=None):
    def __init__(self, vm: CardViewModel, parent=None):
        super().__init__(parent)
        self.vm = vm
        #self.db_view = db_view
        self._csv_path: str = ""
        self._build_ui()
        self._connect_signals()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── File bar ──────────────────────────────────────────────────────
        file_box = QGroupBox("Database File")
        file_row = QHBoxLayout(file_box)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("No file selected — records exist in memory only")
        self.path_edit.setFont(_mono_font())
        self.btn_new    = QPushButton("New…")
        self.btn_open   = QPushButton("Open…")
        self.btn_append = QPushButton("⬇  Append Current Row to File")
        self.btn_save_all = QPushButton("💾  Save All to File")
        self.btn_new.setFixedWidth(60)
        self.btn_open.setFixedWidth(60)
        self.btn_append.setFixedWidth(200)
        self.btn_save_all.setFixedWidth(160)
        file_row.addWidget(self.path_edit)
        file_row.addWidget(self.btn_new)
        file_row.addWidget(self.btn_open)
        file_row.addWidget(self.btn_append)
        file_row.addWidget(self.btn_save_all)
        root.addWidget(file_box)

        # ── Action bar ────────────────────────────────────────────────────
        action_row = QHBoxLayout()
        self.btn_add_row  = QPushButton("＋  Add Row from Card")
        self.btn_del_row  = QPushButton("🗑  Delete Selected Row")
        self.btn_clear    = QPushButton("Clear All")
        self.btn_add_row.setFixedWidth(180)
        self.btn_del_row.setFixedWidth(180)
        self.btn_clear.setFixedWidth(100)
        self.btn_clear.setStyleSheet("color: red;")
        action_row.addWidget(self.btn_add_row)
        action_row.addWidget(self.btn_del_row)
        action_row.addStretch()
        action_row.addWidget(self.btn_clear)
        root.addLayout(action_row)

        # ── Table ─────────────────────────────────────────────────────────
        self.table = QTableWidget(0, len(_CSV_COLUMNS))
        self.table.setHorizontalHeaderLabels([
            "UID", "PICC Master Key",
            "Key 1 – App Master", "Key 2 – Read",
            "Key 3 – Write Chksum", "Key 4 – Write Data",
            "Key 5 – R/W Params",
            "Timestamp (UTC)", "Notes",
        ])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(True)
        self.table.setFont(_mono_font())
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked
        )
        # Sensible default column widths
        widths = [140, 180, 180, 180, 180, 180, 180, 160, 120]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
        root.addWidget(self.table)

        # ── Status bar ────────────────────────────────────────────────────
        self.status_label = QLabel("No records.")
        root.addWidget(self.status_label)

    # ── Signals ───────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.btn_new.clicked.connect(self._on_new_file)
        self.btn_open.clicked.connect(self._on_open_file)
        self.btn_append.clicked.connect(self._on_append_selected_to_file)
        self.btn_save_all.clicked.connect(self._on_save_all)
        self.btn_add_row.clicked.connect(self._on_add_row)
        self.btn_del_row.clicked.connect(self._on_delete_selected)
        self.btn_clear.clicked.connect(self._on_clear)

        # UID is read from the card when a new row is added
        self.vm.uidRead.connect(self._on_uid_read)



    # ── File operations ───────────────────────────────────────────────────
    @Slot()
    def _on_new_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "New Database File", "", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        if not path.endswith(".csv"):
            path += ".csv"
        # Write header only
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(_CSV_COLUMNS)
        self._csv_path = path
        self.path_edit.setText(path)
        self._update_status()

    @Slot()
    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Database File", "", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        self._csv_path = path
        self.path_edit.setText(path)
        self._load_from_file(path)

    def _load_from_file(self, path: str):
        """Load all rows from a CSV file, replacing the current table contents."""
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"Cannot open: {path}")
            return
        self.table.setRowCount(0)
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._append_row_data([
                        row.get(col, "") for col in _CSV_COLUMNS
                    ])
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            return
        self._update_status(f"Loaded {self.table.rowCount()} record(s) from {path}")

    @Slot()
    def _on_append_selected_to_file(self):
        """Append only the currently selected row(s) to the CSV file."""
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "Nothing Selected", "Select a row to append.")
            return
        if not self._csv_path:
            QMessageBox.warning(self, "No File", "Select or create a database file first.")
            return
        try:
            write_header = not os.path.exists(self._csv_path) or os.path.getsize(self._csv_path) == 0
            with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(_CSV_COLUMNS)
                for r in rows:
                    writer.writerow(self._row_data(r))
            self._update_status(f"Appended {len(rows)} row(s) to {self._csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Write Error", str(e))

    @Slot()
    def _on_save_all(self):
        """Overwrite the CSV file with all current table rows."""
        if not self._csv_path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Database As", "", "CSV files (*.csv);;All files (*)"
            )
            if not path:
                return
            if not path.endswith(".csv"):
                path += ".csv"
            self._csv_path = path
            self.path_edit.setText(path)
        try:
            with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(_CSV_COLUMNS)
                for r in range(self.table.rowCount()):
                    writer.writerow(self._row_data(r))
            self._update_status(f"Saved {self.table.rowCount()} record(s) to {self._csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    # ── Row operations ────────────────────────────────────────────────────
    @Slot()
    def _on_add_row(self):
        keys = self.vm.key_store.keys
        data = [
            "",
            keys[0].hex(),  # Key 0 – PICC Master Key
            keys[1].hex(),  # Key 1 – Application Master Key
            keys[2].hex(),  # Key 2 – Read
            keys[3].hex(),  # Key 3 – Write Checksum
            keys[4].hex(),  # Key 4 – Write Serial/Type
            keys[5].hex(),  # Key 5 – R/W Parameters
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "",
        ]
        row = self._append_row_data(data)
        self.table.selectRow(row)
        self.table.scrollToItem(self.table.item(row, 0))
        self._update_status()

    @Slot(str)
    def _on_uid_read(self, uid: str):
        """
        When a UID is read from the card, write it into the selected row's UID cell.
        If no row is selected, writes to the last row.
        """
        selected = self.table.selectedItems()
        if selected:
            row = self.table.currentRow()
        elif self.table.rowCount() > 0:
            row = self.table.rowCount() - 1
        else:
            return
        uid_clean = uid.replace(" ", "")
        item = QTableWidgetItem(uid_clean)
        item.setFont(_mono_font())
        self.table.setItem(row, self.COL["uid"], item)

    @Slot()
    def _on_delete_selected(self):
        rows = sorted(
            {idx.row() for idx in self.table.selectedIndexes()}, reverse=True
        )
        if not rows:
            return
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(rows)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            for r in rows:
                self.table.removeRow(r)
            self._update_status()

    @Slot()
    def _on_clear(self):
        if self.table.rowCount() == 0:
            return
        confirm = QMessageBox.question(
            self, "Confirm Clear",
            "Remove all rows from the table? (File is not modified.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)
            self._update_status()



    # ── Public API (called from AccessKeyView) ────────────────────────────
    def copy_keys_to_new_row(self, picc_key_hex: str = ""):
        """
        Called by AccessKeyView's 'Copy to Database' button.
        Creates a new row with the current KeyStore keys.
        Accepts an optional PICC master key hex string.
        """
        keys = self.vm.key_store.keys

        # If no explicit PICC key passed, read from KeyStore index 0
        if not picc_key_hex:
            picc_key_hex = keys[0].hex()

        data = [
            "", # UID — fill after Read UID
            picc_key_hex,
            keys[0].hex(),
            keys[1].hex(),
            keys[2].hex(),
            keys[3].hex(),
            keys[4].hex(),
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "", # notes
        ]
        row = self._append_row_data(data)
        self.table.selectRow(row)
        self.table.scrollToItem(self.table.item(row, 0))
        self._update_status()

    # ── Helpers ───────────────────────────────────────────────────────────
    def _append_row_data(self, values: list) -> int:
        """Insert a new row at the bottom. Returns the new row index."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setFont(_mono_font())
            # Highlight key columns
            if 1 <= col <= 6:
                item.setForeground(QColor("#005500"))
            self.table.setItem(row, col, item)
        return row

    def _row_data(self, row: int) -> list:
        return [
            (self.table.item(row, col).text() if self.table.item(row, col) else "")
            for col in range(len(_CSV_COLUMNS))
        ]

    def _update_status(self, msg: str = ""):
        n = self.table.rowCount()
        base = f"{n} record(s) in memory"
        if self._csv_path:
            base += f"  |  {self._csv_path}"
        self.status_label.setText(f"{base}  —  {msg}" if msg else base)