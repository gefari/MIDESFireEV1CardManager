from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QMessageBox, QComboBox, QFrame
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QGuiApplication
from viewmodels.card_viewmodel import CardViewModel
from views.card_database_view import CardDatabaseView
from models.license_model import KeyType, KEY_TYPE_NAMES

class AccessKeyView(QWidget):
    def __init__(self, viewmodel: CardViewModel, db_view: "CardDatabaseView", parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self.db_view = db_view
        self._key_edits = []   # list of QLineEdit, one per key
        self.setWindowTitle("Access Keys")
        self._build_ui()
        self._connect_signals()
        self._refresh_keys()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Global actions ─────────────────────────────────────────────────
        top_row = QHBoxLayout()
        self.btn_gen_all = QPushButton("⟳  Generate All Keys")
        self.btn_gen_all.setStyleSheet("font-weight: bold;")
        top_row.addWidget(self.btn_gen_all)

        self.btn_copy_to_db = QPushButton("📋  Copy Keys to Database")
        top_row.addWidget(self.btn_copy_to_db)

        top_row.addStretch()
        root.addLayout(top_row)

        # ── Per-key rows ───────────────────────────────────────────────────
        keys_box = QGroupBox("Application Keys")
        keys_layout = QVBoxLayout(keys_box)

        for i, key in enumerate(self.vm.key_store.keys):
            row_box = QGroupBox(key.name)
            row_form = QFormLayout(row_box)

            key_edit = QLineEdit()
            key_edit.setPlaceholderText("16 hex characters  e.g. 0011223344556677")
            key_edit.setMaxLength(32)   # allow spaces
            key_edit.setFont(self._mono_font())
            key_edit.editingFinished.connect(
                lambda idx=i, edit=key_edit: self.vm.set_key_hex(idx, edit.text())
            )
            self._key_edits.append(key_edit)

            btn_gen  = QPushButton("Generate")
            btn_copy = QPushButton("Copy")
            btn_gen.setFixedWidth(80)
            btn_copy.setFixedWidth(60)

            btn_gen.clicked.connect(lambda checked=False, idx=i: self.vm.generate_key(idx))
            btn_copy.clicked.connect(lambda checked=False, edit=key_edit: self._copy(edit.text()))

            btn_row = QHBoxLayout()
            btn_row.addWidget(key_edit)
            btn_row.addWidget(btn_gen)
            btn_row.addWidget(btn_copy)
            row_form.addRow(f"Key {i+1} value:", btn_row)

            type_combo = QComboBox()
            for kt, label in KEY_TYPE_NAMES.items():
                type_combo.addItem(label, kt)
            type_combo.setCurrentIndex(1)  # default: 2K3DES

            type_combo.currentIndexChanged.connect(
                lambda _, idx=i, tc=type_combo: self._on_type_changed(idx, tc.currentData())
            )
            row_form.addRow("Key type:", type_combo)

            keys_layout.addWidget(row_box)

            # Add a visual separator after Key 0 (PICC) to distinguish it from app keys
            if i == 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("color: #aaaaaa;")
                keys_layout.addWidget(sep)

        root.addWidget(keys_box)

        # ── Status ─────────────────────────────────────────────────────────
        self.status_label = QLabel("Ready.")
        root.addWidget(self.status_label)
        root.addStretch()

    def _mono_font(self):
        from PySide6.QtGui import QFont
        f = QFont("Courier New", 10)
        f.setFixedPitch(True)
        return f

    def _connect_signals(self):
        self.btn_gen_all.clicked.connect(self.vm.generate_all_keys)
        self.vm.keyStoreChanged.connect(self._refresh_keys)
        self.vm.statusChanged.connect(self.status_label.setText)
        self.vm.errorOccurred.connect(
            lambda m: QMessageBox.critical(self, "Key Error", m)
        )
        self.btn_copy_to_db.clicked.connect(self._on_copy_to_db)

    @Slot()
    def _on_copy_to_db(self):
        self.db_view.copy_keys_to_new_row(picc_key_hex="")
        self.status_label.setText("Keys copied to database.")

    @Slot()
    def _refresh_keys(self):
        for i, edit in enumerate(self._key_edits):
            edit.setText(self.vm.key_store.get(i).hex())

    def _copy(self, text: str):
        QGuiApplication.clipboard().setText(text)

    def _on_type_changed(self, index: int, key_type: KeyType):
        key = self.vm.key_store.get(index)
        key.key_type = key_type
        # Update placeholder hint on the hex edit
        edit = self._key_edits[index]
        edit.setMaxLength(int(key_type) * 2)
        edit.setPlaceholderText(f"{int(key_type) * 2} hex characters")
        self.vm.keyStoreChanged.emit()
