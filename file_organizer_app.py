"""
file_organizer_app.py — PyQt6 desktop app for file_organizer.py
Run: python file_organizer_app.py
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QThread, QObject, pyqtSignal, QSettings, QSize, QTimer,
    QAbstractTableModel, QModelIndex, QEvent,
)
from PyQt6.QtGui import QColor, QFont, QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox,
    QRadioButton, QButtonGroup, QTabWidget,
    QTableView, QHeaderView, QProgressBar, QTextEdit, QFileDialog,
    QFrame, QSplitter, QStatusBar, QGroupBox, QSizePolicy,
    QAbstractItemView, QToolButton, QMenu, QStyle,
    QScrollArea, QDialog, QStyledItemDelegate,
)

from file_organizer import (
    FileOrganizer, OrganizerConfig, SortMode,
    FilterAction, FilterRule, RuleEngine, Condition,
    DEFAULT_SUBTYPE_MAP,
    FileCleaner, CleanerConfig,
)

_BATCH     = 300
_DEBUG_LOG = Path(__file__).with_name("file_organizer_debug.log")


def _resource_path(name: str) -> str:
    """Resolve a bundled-resource path.

    Works both when running from source (next to this file) and when
    frozen by PyInstaller (resources land in sys._MEIPASS).
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class _Cancelled(BaseException):
    pass


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QDialog { background-color: #24273a; }

QTabWidget::pane { border: none; background: #1e1e2e; }
QTabBar::tab {
    background-color: #181825;
    color: #6c7086;
    padding: 10px 26px;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 600;
    font-size: 13px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #cdd6f4;
    border-bottom-color: #89b4fa;
    background-color: #1e1e2e;
}
QTabBar::tab:hover:!selected { color: #a6adc8; background-color: #24273a; }
QTabBar#cleaner_tabs::tab:selected { border-bottom-color: #f38ba8; }

QGroupBox {
    border: 1px solid #313244; border-radius: 8px;
    margin-top: 10px; padding-top: 8px;
    font-weight: 600; color: #89b4fa;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; top: -1px; padding: 0 4px; }
QGroupBox#cleaner_group { color: #f38ba8; }

QLineEdit {
    background-color: #313244; border: 1px solid #45475a;
    border-radius: 6px; padding: 6px 10px; color: #cdd6f4;
    selection-background-color: #89b4fa;
}
QLineEdit:focus { border-color: #89b4fa; }
QLineEdit:disabled { color: #585b70; background-color: #1e1e2e; }
QLineEdit#field_error { border-color: #f38ba8; }

QPushButton {
    background-color: #313244; border: 1px solid #45475a;
    border-radius: 6px; padding: 7px 16px; color: #cdd6f4; font-weight: 500;
}
QPushButton:hover   { background-color: #45475a; border-color: #89b4fa; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { color: #585b70; border-color: #313244; }

QPushButton#btn_run {
    background-color: #89b4fa; color: #1e1e2e;
    font-weight: 700; border: none; padding: 9px 28px; font-size: 14px;
}
QPushButton#btn_run:hover    { background-color: #b4d0ff; }
QPushButton#btn_run:pressed  { background-color: #74a7f5; }
QPushButton#btn_run:disabled { background-color: #313244; color: #585b70; }

QPushButton#btn_delete {
    background-color: #f38ba8; color: #1e1e2e;
    font-weight: 700; border: none; padding: 9px 28px; font-size: 14px;
}
QPushButton#btn_delete:hover    { background-color: #f5a3bb; }
QPushButton#btn_delete:pressed  { background-color: #e07090; }
QPushButton#btn_delete:disabled { background-color: #3d1520; color: #7a4050; }

QPushButton#btn_cancel {
    background-color: #f38ba8; color: #1e1e2e;
    font-weight: 700; border: none; padding: 9px 28px; font-size: 14px;
}
QPushButton#btn_cancel:hover    { background-color: #f5a3bb; }
QPushButton#btn_cancel:pressed  { background-color: #e07090; }
QPushButton#btn_cancel:disabled { background-color: #6b3040; color: #c07080; }

QPushButton#btn_browse { background-color: #45475a; padding: 7px 12px; }
QPushButton#btn_add_rule_dialog {
    background-color: #89b4fa; color: #1e1e2e; font-weight: 700; border: none;
}
QPushButton#btn_add_rule_dialog:hover   { background-color: #b4d0ff; }
QPushButton#btn_update_rule {
    background-color: #a6e3a1; color: #1e1e2e; font-weight: 700; border: none;
}
QPushButton#btn_update_rule:hover { background-color: #c0f0bb; }

QComboBox {
    background-color: #313244; border: 1px solid #45475a;
    border-radius: 6px; padding: 6px 10px; color: #cdd6f4; min-width: 80px;
}
QComboBox:hover { border-color: #89b4fa; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 6px solid #89b4fa; margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #313244; border: 1px solid #45475a;
    selection-background-color: #45475a; outline: 0;
}

QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #45475a;
    border-radius: 4px; background-color: #313244;
}
QCheckBox::indicator:checked { background-color: #89b4fa; border-color: #89b4fa; }

QRadioButton { spacing: 8px; }
QRadioButton::indicator {
    width: 15px; height: 15px; border: 1px solid #45475a;
    border-radius: 8px; background-color: #313244;
}
QRadioButton::indicator:checked { background-color: #a6e3a1; border-color: #a6e3a1; }

QTableView {
    background-color: #181825; border: 1px solid #313244;
    border-radius: 6px; gridline-color: #313244;
    selection-background-color: #313244; outline: 0;
    alternate-background-color: #1e1e2e;
}
QTableView::item { padding: 4px 8px; }
QTableView::item:selected { background-color: #45475a; color: #cdd6f4; }
QHeaderView::section {
    background-color: #313244; color: #89b4fa; font-weight: 600;
    padding: 6px 10px; border: none;
    border-right: 1px solid #45475a; border-bottom: 1px solid #45475a;
}

QTextEdit {
    background-color: #11111b; border: 1px solid #313244;
    border-radius: 6px; font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 12px; color: #a6adc8;
}
QProgressBar {
    background-color: #313244; border: none; border-radius: 4px;
    height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }
QProgressBar#cleaner_progress::chunk { background-color: #f38ba8; }

QStatusBar { background-color: #181825; color: #6c7086; border-top: 1px solid #313244; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #1e1e2e; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #45475a; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #585b70; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #1e1e2e; height: 8px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #45475a; border-radius: 4px; min-width: 20px; }
QScrollBar::handle:horizontal:hover { background: #585b70; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle { background-color: #313244; }
QSplitter::handle:horizontal {
    width: 5px; border-left: 1px solid #45475a; border-right: 1px solid #45475a;
}
QSplitter::handle:vertical {
    height: 5px; border-top: 1px solid #45475a; border-bottom: 1px solid #45475a;
}
QSplitter::handle:hover { background-color: #45475a; }
QFrame#separator { background-color: #313244; max-height: 1px; }
QLabel#label_title    { font-size: 20px; font-weight: 700; color: #89b4fa; }
QLabel#label_subtitle { font-size: 12px; color: #6c7086; }
QLabel#dlg_section    { color: #89b4fa; font-weight: 700; font-size: 12px; }
QLabel#field_label    { color: #a6adc8; font-size: 12px; }
QToolButton { background: transparent; border: none; color: #6c7086; padding: 4px; border-radius: 4px; }
QToolButton:hover { color: #cdd6f4; background: #313244; }
QMenu { background-color: #313244; border: 1px solid #45475a; border-radius: 6px; padding: 4px; }
QMenu::item { padding: 6px 20px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: #45475a; }
"""


# ---------------------------------------------------------------------------
# Per-row delete delegate
# ---------------------------------------------------------------------------

class DeleteButtonDelegate(QStyledItemDelegate):
    delete_requested = pyqtSignal(int)

    def paint(self, painter, option, index):
        painter.save()
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        bg = QColor("#4a1020") if is_hover else QColor("#181825")
        painter.fillRect(option.rect, bg)
        painter.setPen(QColor("#f38ba8") if is_hover else QColor("#6c7086"))
        f = painter.font(); f.setPointSize(12); f.setBold(True); painter.setFont(f)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, "✕")
        painter.restore()

    def sizeHint(self, option, index): return QSize(36, 28)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            self.delete_requested.emit(index.row()); return True
        return False


# ---------------------------------------------------------------------------
# Preview models
# ---------------------------------------------------------------------------

class PreviewModel(QAbstractTableModel):
    HEADERS = ["File", "Action", "Destination Folder", "Status"]
    _ACTION_COLORS = {
        "delete": QColor("#f38ba8"), "skip": QColor("#6c7086"),
        "move": QColor("#cdd6f4"),   "copy": QColor("#a6e3a1"),
    }
    _ACTION_LABELS = {"delete": "Delete", "skip": "Skip", "move": "Move", "copy": "Copy"}

    def __init__(self):
        super().__init__(); self._rows: list[dict] = []; self._index: dict[str, int] = {}

    def load(self, plan):
        self.beginResetModel()
        self._rows = plan
        self._index = {Path(r["file"]).name: i for i, r in enumerate(plan)}
        self.endResetModel()

    def rowCount(self, parent=None):    return len(self._rows)
    def columnCount(self, parent=None): return 4

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        row = self._rows[index.row()]; col = index.column(); action = row.get("action", "move")
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return Path(row["file"]).name
            if col == 1: return self._ACTION_LABELS.get(action, action.capitalize())
            if col == 2:
                if action == "delete": return "(will be deleted)"
                if action == "skip":   return "(will be skipped)"
                dest = row.get("destination")
                return str(Path(dest).parent) if dest else "(no match)"
            if col == 3: return row.get("status", "Ready")
        if role == Qt.ItemDataRole.ForegroundRole:
            status = row.get("status", "")
            if status == "Moved":   return QColor("#a6e3a1")
            if status == "Copied":  return QColor("#a6e3a1")
            if status == "Deleted": return QColor("#f38ba8")
            if status in ("Skipped", "Skip"): return QColor("#f9e2af")
            if status == "Error":   return QColor("#f38ba8")
            return self._ACTION_COLORS.get(action, QColor("#cdd6f4"))
        if role == Qt.ItemDataRole.FontRole and col == 0:
            f = QFont(); f.setWeight(QFont.Weight.Medium); return f
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def apply_batch(self, updates):
        changed = False
        for filename, status in updates:
            i = self._index.get(filename)
            if i is not None: self._rows[i]["status"] = status; changed = True
        if changed and self._rows:
            self.dataChanged.emit(self.index(0, 3), self.index(len(self._rows) - 1, 3))


class CleanerPreviewModel(QAbstractTableModel):
    HEADERS = ["File", "Folder", "Action", "Status"]

    def __init__(self):
        super().__init__(); self._rows: list[dict] = []; self._index: dict[str, int] = {}

    def load(self, plan):
        self.beginResetModel()
        self._rows = plan
        self._index = {Path(r["file"]).name: i for i, r in enumerate(plan)}
        self.endResetModel()

    def rowCount(self, parent=None):    return len(self._rows)
    def columnCount(self, parent=None): return 4

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        row = self._rows[index.row()]; col = index.column()
        p = Path(row["file"]); action = row.get("action", "skip")
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return p.name
            if col == 1: return str(p.parent)
            if col == 2: return "Will Delete" if action == "delete" else "Keep"
            if col == 3: return row.get("status", "Pending")
        if role == Qt.ItemDataRole.ForegroundRole:
            status = row.get("status", "")
            if status == "Deleted": return QColor("#f38ba8")
            if status == "Error":   return QColor("#f38ba8")
            if action == "delete":  return QColor("#f38ba8")
            return QColor("#6c7086")
        if role == Qt.ItemDataRole.FontRole and col == 0:
            f = QFont(); f.setWeight(QFont.Weight.Medium); return f
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def apply_batch(self, updates):
        changed = False
        for filename, status in updates:
            i = self._index.get(filename)
            if i is not None: self._rows[i]["status"] = status; changed = True
        if changed and self._rows:
            self.dataChanged.emit(self.index(0, 3), self.index(len(self._rows) - 1, 3))


# ---------------------------------------------------------------------------
# Rules table model
# ---------------------------------------------------------------------------

CONDITION_TYPE_LABELS: dict[str, str] = {
    "name_starts_with": "Name starts with",
    "name_ends_with":   "Name ends with",
    "name_contains":    "Name contains",
    "extension_in":     "Extension is",
    "size_gt":          "Size greater than (bytes)",
    "size_lt":          "Size less than (bytes)",
    "matches_glob":     "Matches glob pattern",
    "matches_regex":    "Matches regex",
    "always":           "Always (all files)",
}
ACTION_COLORS = {"delete": "#f38ba8", "skip": "#f9e2af", "keep": "#a6e3a1"}


class RulesTableModel(QAbstractTableModel):
    HEADERS = ["Pri", "Condition", "Action", ""]

    def __init__(self):
        super().__init__(); self._specs: list[dict] = []

    def load(self, specs):
        self.beginResetModel(); self._specs = list(specs); self.endResetModel()

    def specs(self): return list(self._specs)
    def rowCount(self, parent=None):    return len(self._specs)
    def columnCount(self, parent=None): return 4

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        spec = self._specs[index.row()]; col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return str(spec.get("priority", 0))
            if col == 1:
                ctype = spec["condition"]["type"]; cvalue = spec["condition"].get("value", "")
                label = CONDITION_TYPE_LABELS.get(ctype, ctype)
                return f"{label}: {cvalue!r}" if cvalue else label
            if col == 2: return spec["action"].capitalize()
            if col == 3: return None
        if role == Qt.ItemDataRole.ForegroundRole and col == 2:
            return QColor(ACTION_COLORS.get(spec["action"], "#cdd6f4"))
        if role == Qt.ItemDataRole.FontRole and col == 1:
            f = QFont(); f.setWeight(QFont.Weight.Medium); return f
        if role == Qt.ItemDataRole.ToolTipRole and col == 1:
            return "Double-click to edit this rule"
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def add_spec(self, spec):
        row = len(self._specs)
        self.beginInsertRows(QModelIndex(), row, row)
        self._specs.append(spec); self.endInsertRows()

    def insert_spec(self, row, spec):
        row = max(0, min(row, len(self._specs)))
        self.beginInsertRows(QModelIndex(), row, row)
        self._specs.insert(row, spec); self.endInsertRows()

    def remove_row(self, row):
        if 0 <= row < len(self._specs):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._specs[row]; self.endRemoveRows()


# ---------------------------------------------------------------------------
# Rule dialog
# ---------------------------------------------------------------------------

class RuleDialog(QDialog):
    def __init__(self, parent=None, spec: dict | None = None, cleaner_mode: bool = False):
        super().__init__(parent, Qt.WindowType.Dialog)
        self._is_edit    = spec is not None
        self._cleaner    = cleaner_mode
        self._result_spec: dict | None = None
        self.setWindowTitle("Edit Rule" if self._is_edit else "Add Rule")
        self.setMinimumWidth(460); self.setModal(True)
        self._build_ui(spec)

    def _build_ui(self, spec):
        root = QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)
        accent = "#f38ba8" if self._cleaner else "#89b4fa"

        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #181825; border-bottom: 1px solid #313244;")
        title_bar.setFixedHeight(52)
        tb = QHBoxLayout(title_bar); tb.setContentsMargins(20, 0, 20, 0)
        icon_lbl  = QLabel("⚙" if self._is_edit else "＋")
        icon_lbl.setStyleSheet(f"font-size: 18px; color: {accent};")
        title_lbl = QLabel("Edit Rule" if self._is_edit else "Add New Rule")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #cdd6f4;")
        sub_lbl   = QLabel("Modify the rule below." if self._is_edit
                           else "Define a condition and choose what to do with matching files.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #6c7086;")
        text_col = QVBoxLayout(); text_col.setSpacing(1)
        text_col.addWidget(title_lbl); text_col.addWidget(sub_lbl)
        tb.addWidget(icon_lbl); tb.addSpacing(10); tb.addLayout(text_col); tb.addStretch()
        root.addWidget(title_bar)

        body = QWidget(); form = QVBoxLayout(body)
        form.setSpacing(12); form.setContentsMargins(20, 16, 20, 16)

        form.addWidget(self._slbl("1  ·  Condition  — what to match", accent))
        self.combo_cond = QComboBox()
        self.combo_cond.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for key, label in CONDITION_TYPE_LABELS.items():
            self.combo_cond.addItem(label, userData=key)
        form.addWidget(self.combo_cond)

        self._value_lbl = self._flbl("Value  — the text or pattern to match:")
        form.addWidget(self._value_lbl)
        self.edit_value = QLineEdit()
        self.edit_value.setPlaceholderText("e.g.  t   or   .tmp   or   *.bak")
        self.edit_value.returnPressed.connect(self._submit)
        form.addWidget(self.edit_value)

        sep = QFrame(); sep.setObjectName("separator"); sep.setFrameShape(QFrame.Shape.HLine)
        form.addWidget(sep)

        form.addWidget(self._slbl("2  ·  Action  — what to do with matching files", accent))
        self.combo_action = QComboBox()
        self.combo_action.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions = [("delete", "Delete  —  remove the file permanently"),
                   ("skip",   "Skip  —  leave the file exactly where it is"),
                   ("keep",   "Keep  —  organise it normally (apply sort)")]
        if self._cleaner:
            actions = [("delete", "Delete  —  remove the file"),
                       ("skip",   "Skip / Protect  —  do NOT delete this file")]
        for val, lbl in actions:
            self.combo_action.addItem(lbl, userData=val)
        form.addWidget(self.combo_action)

        sep2 = QFrame(); sep2.setObjectName("separator"); sep2.setFrameShape(QFrame.Shape.HLine)
        form.addWidget(sep2)

        pri_row = QHBoxLayout()
        pri_row.addWidget(self._slbl("3  ·  Priority", accent))
        ph = QLabel("Higher number = evaluated first when multiple rules match.")
        ph.setStyleSheet("color: #45475a; font-size: 11px; font-style: italic;")
        ph.setWordWrap(True); pri_row.addWidget(ph, 1)
        form.addLayout(pri_row)
        self.edit_priority = QLineEdit("0"); self.edit_priority.setFixedWidth(80)
        form.addWidget(self.edit_priority)
        root.addWidget(body, 1)

        btn_bar = QWidget()
        btn_bar.setStyleSheet("background-color: #181825; border-top: 1px solid #313244;")
        btn_bar.setFixedHeight(58)
        bb = QHBoxLayout(btn_bar); bb.setContentsMargins(20, 0, 20, 0); bb.setSpacing(10)
        btn_ok = QPushButton("Update Rule" if self._is_edit else "Add Rule")
        btn_ok.setObjectName("btn_update_rule" if self._is_edit else "btn_add_rule_dialog")
        btn_ok.setFixedHeight(36); btn_ok.clicked.connect(self._submit)
        btn_cancel = QPushButton("Cancel"); btn_cancel.setFixedHeight(36)
        btn_cancel.setFixedWidth(90); btn_cancel.clicked.connect(self.reject)
        bb.addStretch(); bb.addWidget(btn_cancel); bb.addWidget(btn_ok)
        root.addWidget(btn_bar)

        if spec:
            idx = self.combo_cond.findData(spec["condition"]["type"])
            if idx >= 0: self.combo_cond.setCurrentIndex(idx)
            self.edit_value.setText(spec["condition"].get("value", ""))
            idx2 = self.combo_action.findData(spec.get("action", "keep"))
            if idx2 >= 0: self.combo_action.setCurrentIndex(idx2)
            self.edit_priority.setText(str(spec.get("priority", 0)))

        self.combo_cond.currentIndexChanged.connect(self._update_value_visibility)
        self._update_value_visibility()

    @staticmethod
    def _slbl(text, accent="#89b4fa"):
        l = QLabel(text); l.setStyleSheet(f"color: {accent}; font-weight: 700; font-size: 12px;")
        return l

    @staticmethod
    def _flbl(text):
        l = QLabel(text); l.setObjectName("field_label"); return l

    def _update_value_visibility(self):
        is_always = self.combo_cond.currentData() == "always"
        self._value_lbl.setVisible(not is_always); self.edit_value.setVisible(not is_always)

    def _submit(self):
        ctype = self.combo_cond.currentData(); value = self.edit_value.text().strip()
        action = self.combo_action.currentData()
        try: priority = int(self.edit_priority.text().strip() or "0")
        except ValueError: priority = 0
        if ctype != "always" and not value:
            self.edit_value.setStyleSheet("border-color: #f38ba8;"); self.edit_value.setFocus()
            return
        self._result_spec = {
            "name": f"{ctype}:{value} -> {action}",
            "condition": {"type": ctype, "value": value},
            "action": action, "priority": priority,
        }
        self.accept()

    def result_spec(self): return self._result_spec


# ---------------------------------------------------------------------------
# Workers — Organizer
# ---------------------------------------------------------------------------

class PreviewWorker(QObject):
    preview_ready = pyqtSignal(list); error = pyqtSignal(str)

    def __init__(self, directory, config):
        super().__init__(); self.directory = directory; self.config = config; self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            plan = FileOrganizer(self.directory, self.config).preview()
            if not self._stop: self.preview_ready.emit(plan)
        except Exception as e:
            if not self._stop: self.error.emit(str(e))


class OrganizerWorker(QObject):
    batch_update = pyqtSignal(int, int, list); log_batch = pyqtSignal(str)
    finished = pyqtSignal(dict); error = pyqtSignal(str)

    def __init__(self, directory, config):
        super().__init__(); self.directory = directory; self.config = config; self._stop = False

    def stop(self): self._stop = True

    def run(self):
        fh = logging.FileHandler(_DEBUG_LOG, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                          datefmt="%Y-%m-%d %H:%M:%S"))
        try:
            org = FileOrganizer(self.directory, self.config)
            org.logger.addHandler(fh); org.logger.propagate = False
            status_buf: list[tuple[str, str]] = []; log_buf: list[str] = []
            self._prev_skipped = 0

            def flush(cur):
                if status_buf or log_buf:
                    self.batch_update.emit(cur, self._total, list(status_buf))
                    if log_buf: self.log_batch.emit("\n".join(log_buf))
                    status_buf.clear(); log_buf.clear()

            class Buf(logging.Handler):
                def emit(s, r): log_buf.append(s.format(r))
            b = Buf(); b.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                                        datefmt="%H:%M:%S"))
            org.logger.addHandler(b)
            orig_move = org._move_file; orig_del = org._delete_file
            is_copy   = self.config.copy_mode

            def _cur(): return org._moved + org._deleted + org._skipped + org._errors

            def pm(src, dest):
                if self._stop: raise _Cancelled()
                orig_move(src, dest)
                st = "Copied" if is_copy else "Moved"
                if org._skipped > self._prev_skipped: st = "Skipped"
                self._prev_skipped = org._skipped
                status_buf.append((src.name, st))
                if len(status_buf) >= _BATCH: flush(_cur())

            def pd(file):
                if self._stop: raise _Cancelled()
                orig_del(file); status_buf.append((file.name, "Deleted"))
                if len(status_buf) >= _BATCH: flush(_cur())

            org._move_file = pm; org._delete_file = pd
            org._validate_target(); self._total = len(org._collect_files())
            try:
                result = org.run()
            except _Cancelled:
                result = {"moved": org._moved, "deleted": org._deleted,
                          "skipped": org._skipped, "errors": org._errors, "cancelled": True}
            flush(_cur()); self.finished.emit(result)
        except Exception as e: self.error.emit(str(e))
        finally: fh.close()


# ---------------------------------------------------------------------------
# Workers — Cleaner
# ---------------------------------------------------------------------------

class CleanerPreviewWorker(QObject):
    preview_ready = pyqtSignal(list); error = pyqtSignal(str)

    def __init__(self, directory, config):
        super().__init__(); self.directory = directory; self.config = config; self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            plan = FileCleaner(self.directory, self.config).preview()
            if not self._stop: self.preview_ready.emit(plan)
        except Exception as e:
            if not self._stop: self.error.emit(str(e))


class CleanerWorker(QObject):
    batch_update = pyqtSignal(int, int, list); log_batch = pyqtSignal(str)
    finished = pyqtSignal(dict); error = pyqtSignal(str)

    def __init__(self, directory, config):
        super().__init__(); self.directory = directory; self.config = config; self._stop = False

    def stop(self): self._stop = True

    def run(self):
        fh = logging.FileHandler(_DEBUG_LOG, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                          datefmt="%Y-%m-%d %H:%M:%S"))
        try:
            cl = FileCleaner(self.directory, self.config)
            cl.logger.addHandler(fh); cl.logger.propagate = False
            status_buf: list[tuple[str, str]] = []; log_buf: list[str] = []

            def flush(cur):
                if status_buf or log_buf:
                    self.batch_update.emit(cur, self._total, list(status_buf))
                    if log_buf: self.log_batch.emit("\n".join(log_buf))
                    status_buf.clear(); log_buf.clear()

            class Buf(logging.Handler):
                def emit(s, r): log_buf.append(s.format(r))
            b = Buf(); b.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                                        datefmt="%H:%M:%S"))
            cl.logger.addHandler(b)
            orig_del = cl._delete_file

            def _cur(): return cl._deleted + cl._skipped + cl._errors

            def pd(file):
                if self._stop: raise _Cancelled()
                orig_del(file); status_buf.append((file.name, "Deleted"))
                if len(status_buf) >= _BATCH: flush(_cur())

            cl._delete_file = pd
            cl._validate_target(); self._total = len(cl._collect_files())
            try:
                result = cl.run()
            except _Cancelled:
                result = {"deleted": cl._deleted, "skipped": cl._skipped,
                          "errors": cl._errors, "cancelled": True}
            flush(_cur()); self.finished.emit(result)
        except Exception as e: self.error.emit(str(e))
        finally: fh.close()


# ---------------------------------------------------------------------------
# ViewModels
# ---------------------------------------------------------------------------

class OrganizerViewModel(QObject):
    preview_ready = pyqtSignal(list); batch_update = pyqtSignal(int, int, list)
    log_emitted = pyqtSignal(str); run_finished = pyqtSignal(dict)
    run_error = pyqtSignal(str); state_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__(); self._thread = None; self._worker = None
        self._settings = QSettings("FileOrganizerApp", "v1")

    def save_settings(self, _d, _o, sort_mode, dry_run, recursive,
                      use_subtypes, duplicate, copy_mode, rules):
        s = self._settings
        s.setValue("sort_mode",    sort_mode);  s.setValue("dry_run",      dry_run)
        s.setValue("recursive",    recursive);  s.setValue("use_subtypes", use_subtypes)
        s.setValue("duplicate",    duplicate);  s.setValue("copy_mode",    copy_mode)
        s.setValue("rules",        json.dumps(rules))

    def load_settings(self) -> dict:
        s = self._settings
        try: rules = json.loads(s.value("rules", "[]"))
        except: rules = []
        return {"directory": "", "output_dir": "",
                "sort_mode":    s.value("sort_mode",    "type"),
                "dry_run":      s.value("dry_run",      False, type=bool),
                "recursive":    s.value("recursive",    False, type=bool),
                "use_subtypes": s.value("use_subtypes", False, type=bool),
                "duplicate":    s.value("duplicate",    "rename"),
                "copy_mode":    s.value("copy_mode",    False, type=bool),
                "rules": rules}

    def save_cleaner_settings(self, recursive, dry_run, delete_all, rules):
        s = self._settings
        s.setValue("cl_recursive",  recursive); s.setValue("cl_dry_run",    dry_run)
        s.setValue("cl_delete_all", delete_all); s.setValue("cl_rules",     json.dumps(rules))

    def load_cleaner_settings(self) -> dict:
        s = self._settings
        try: rules = json.loads(s.value("cl_rules", "[]"))
        except: rules = []
        return {"recursive":   s.value("cl_recursive",  False, type=bool),
                "dry_run":     s.value("cl_dry_run",    False, type=bool),
                "delete_all":  s.value("cl_delete_all", False, type=bool),
                "rules": rules}

    def request_preview(self, directory, config):
        if self._thread and self._thread.isRunning(): return
        self.state_changed.emit("previewing")
        self._thread = QThread(); self._worker = PreviewWorker(directory, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.preview_ready.connect(self._on_preview_ready)
        self._worker.error.connect(self._on_error); self._thread.start()

    def _on_preview_ready(self, plan):
        self._cleanup(); self.preview_ready.emit(plan); self.state_changed.emit("idle")

    def start_run(self, directory, config):
        if self._thread and self._thread.isRunning(): return
        self.state_changed.emit("running")
        self._thread = QThread(); self._worker = OrganizerWorker(directory, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.batch_update.connect(self.batch_update)
        self._worker.log_batch.connect(self.log_emitted)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error); self._thread.start()

    def cancel(self):
        if hasattr(self._worker, "stop"): self._worker.stop()

    def _on_finished(self, s):
        self._cleanup(); self.run_finished.emit(s); self.state_changed.emit("idle")

    def _on_error(self, msg):
        self._cleanup(); self.run_error.emit(msg); self.state_changed.emit("idle")

    def _cleanup(self):
        if self._thread:
            self._thread.quit(); self._thread.wait()
            self._thread = None; self._worker = None


class CleanerViewModel(QObject):
    preview_ready = pyqtSignal(list); batch_update = pyqtSignal(int, int, list)
    log_emitted = pyqtSignal(str); run_finished = pyqtSignal(dict)
    run_error = pyqtSignal(str); state_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__(); self._thread = None; self._worker = None

    def request_preview(self, directory, config):
        if self._thread and self._thread.isRunning(): return
        self.state_changed.emit("previewing")
        self._thread = QThread(); self._worker = CleanerPreviewWorker(directory, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.preview_ready.connect(self._on_preview_ready)
        self._worker.error.connect(self._on_error); self._thread.start()

    def _on_preview_ready(self, plan):
        self._cleanup(); self.preview_ready.emit(plan); self.state_changed.emit("idle")

    def start_run(self, directory, config):
        if self._thread and self._thread.isRunning(): return
        self.state_changed.emit("running")
        self._thread = QThread(); self._worker = CleanerWorker(directory, config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.batch_update.connect(self.batch_update)
        self._worker.log_batch.connect(self.log_emitted)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error); self._thread.start()

    def cancel(self):
        if hasattr(self._worker, "stop"): self._worker.stop()

    def _on_finished(self, s):
        self._cleanup(); self.run_finished.emit(s); self.state_changed.emit("idle")

    def _on_error(self, msg):
        self._cleanup(); self.run_error.emit(msg); self.state_changed.emit("idle")

    def _cleanup(self):
        if self._thread:
            self._thread.quit(); self._thread.wait()
            self._thread = None; self._worker = None


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.vm              = OrganizerViewModel()
        self.cleaner_vm      = CleanerViewModel()
        self.model           = PreviewModel()
        self.cleaner_model   = CleanerPreviewModel()
        self.rules_model     = RulesTableModel()
        self.cl_rules_model  = RulesTableModel()
        self._run_start_time: float = 0.0
        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._restore_settings()

    def _setup_window(self):
        self.setWindowTitle("File Organizer")
        self.setMinimumSize(1100, 700); self.resize(1440, 860)

    # ── Top-level ────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(16, 14, 16, 10); root.setSpacing(0)
        root.addWidget(self._make_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._make_organizer_tab(), "📂   File Organizer")
        self.tabs.addTab(self._make_cleaner_tab(),   "🗑   File Cleaner")
        root.addWidget(self.tabs, 1)
        root.addWidget(self._make_progress_bar())
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — select a source directory to begin")

    # ── Header ───────────────────────────────────────────────────────

    def _make_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(54)
        h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
        title = QLabel("File Organizer"); title.setObjectName("label_title")
        sub   = QLabel("  —  Sort, filter, and move files automatically")
        sub.setObjectName("label_subtitle"); sub.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(title); h.addWidget(sub); h.addStretch()
        self.lbl_debug = QLabel(f"Debug log: {_DEBUG_LOG.name}")
        self.lbl_debug.setStyleSheet("color: #45475a; font-size: 11px;")
        h.addWidget(self.lbl_debug); return w

    # ==================================================================
    # TAB 1 — File Organizer
    # ==================================================================

    def _make_organizer_tab(self) -> QWidget:
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False); sp.setHandleWidth(6)
        sp.addWidget(self._make_org_left()); sp.addWidget(self._make_org_right())
        sp.setSizes([460, 980]); return sp

    def _make_org_left(self) -> QWidget:
        outer = QWidget(); outer.setMinimumWidth(400); outer.setMaximumWidth(540)
        ol = QVBoxLayout(outer); ol.setContentsMargins(0, 0, 0, 0); ol.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(); v = QVBoxLayout(content)
        v.setContentsMargins(0, 10, 8, 8); v.setSpacing(10)
        v.addWidget(self._make_src_dir())
        v.addWidget(self._make_out_dir())
        v.addWidget(self._make_options())
        v.addWidget(self._make_rules_group(self.rules_model, "_delete_delegate",
                                           self._open_add_rule_dlg, self._open_edit_rule_dlg,
                                           self._del_org_rule, self._clr_org_rules,
                                           self._org_ctx_menu, accent="#89b4fa"))
        v.addStretch()
        scroll.setWidget(content); ol.addWidget(scroll, 1)
        ol.addWidget(self._make_org_action_row()); return outer

    def _make_org_right(self) -> QWidget:
        panel = QWidget(); v = QVBoxLayout(panel)
        v.setContentsMargins(8, 10, 0, 0); v.setSpacing(0)
        sp = QSplitter(Qt.Orientation.Vertical)
        sp.setChildrenCollapsible(False); sp.setHandleWidth(5)
        sp.addWidget(self._make_preview_table(self.model, "File Preview"))
        sp.addWidget(self._make_log_panel("log_view")); sp.setSizes([620, 200])
        v.addWidget(sp, 1); return panel

    # ── Organizer: Directory rows ─────────────────────────────────────

    def _make_src_dir(self) -> QWidget:
        group = QGroupBox("Source Directory")
        h = QHBoxLayout(group); h.setContentsMargins(10, 8, 10, 10); h.setSpacing(6)
        self.edit_dir = QLineEdit(); self.edit_dir.setPlaceholderText("Folder to organize…")
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setObjectName("btn_browse"); self.btn_browse.setFixedWidth(72)
        h.addWidget(self.edit_dir, 1); h.addWidget(self.btn_browse); return group

    def _make_out_dir(self) -> QWidget:
        group = QGroupBox("Output Directory  (optional — leave blank to organise in-place)")
        h = QHBoxLayout(group); h.setContentsMargins(10, 8, 10, 10); h.setSpacing(6)
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Destination for organised files…")
        self.btn_browse_output = QPushButton("Browse")
        self.btn_browse_output.setObjectName("btn_browse"); self.btn_browse_output.setFixedWidth(72)
        self.btn_clear_output = QToolButton(); self.btn_clear_output.setText("✕")
        self.btn_clear_output.clicked.connect(self.edit_output.clear)
        h.addWidget(self.edit_output, 1); h.addWidget(self.btn_browse_output)
        h.addWidget(self.btn_clear_output); return group

    # ── Organizer: Options ────────────────────────────────────────────

    def _make_options(self) -> QWidget:
        group = QGroupBox("Options")
        grid = QGridLayout(group); grid.setContentsMargins(10, 8, 10, 10)
        grid.setHorizontalSpacing(10); grid.setVerticalSpacing(8)

        def rl(t):
            l = QLabel(t); l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return l

        grid.addWidget(rl("Sort by:"), 0, 0)
        self.combo_sort = QComboBox()
        for mode in SortMode:
            labels = {"type": "File Type  (Images, Documents…)",
                      "extension": "Extension  (JPG, PDF, PY…)",
                      "name": "Name  (A–Z alphabetical)",
                      "size": "Size  (Tiny / Small / Large…)",
                      "date": "Date Modified  (YYYY-MM)"}
            self.combo_sort.addItem(labels[mode.value], userData=mode.value)
        grid.addWidget(self.combo_sort, 0, 1)

        grid.addWidget(rl("Duplicates:"), 1, 0)
        self.combo_dup = QComboBox()
        for val, lbl in [("rename", "Auto-rename  (file (1).jpg)"),
                          ("skip",   "Skip  (keep original)"),
                          ("overwrite", "Overwrite")]:
            self.combo_dup.addItem(lbl, userData=val)
        grid.addWidget(self.combo_dup, 1, 1)

        # ── Move / Copy ──────────────────────────────────────────────
        grid.addWidget(rl("File action:"), 2, 0)
        mc_widget = QWidget(); mc_h = QHBoxLayout(mc_widget)
        mc_h.setContentsMargins(0, 0, 0, 0); mc_h.setSpacing(20)
        self.radio_move = QRadioButton("Move  (relocate files)")
        self.radio_copy = QRadioButton("Copy  (keep originals)")
        self.radio_move.setChecked(True)
        mc_h.addWidget(self.radio_move); mc_h.addWidget(self.radio_copy); mc_h.addStretch()
        grid.addWidget(mc_widget, 2, 1)

        self.chk_recursive = QCheckBox("Include sub-folders")
        self.chk_dryrun    = QCheckBox("Dry run  (preview only — no files moved or deleted)")
        self.chk_subtypes  = QCheckBox("Group by sub-type  (e.g. Documents/PDF, Images/JPEG)")
        self.chk_subtypes.setToolTip(
            "Only applies to 'File Type' sort mode.\n"
            "Creates a two-level hierarchy: Type → Sub-type → files.")
        grid.addWidget(self.chk_recursive, 3, 0, 1, 2)
        grid.addWidget(self.chk_dryrun,    4, 0, 1, 2)
        grid.addWidget(self.chk_subtypes,  5, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        self.combo_sort.currentIndexChanged.connect(self._update_subtype_state)
        return group

    # ── Shared: rules group factory ───────────────────────────────────

    def _make_rules_group(self, model: RulesTableModel, delegate_attr: str,
                          add_cb, edit_cb, del_cb, clear_cb, ctx_cb,
                          accent: str = "#89b4fa") -> QWidget:
        title_color = accent
        group = QGroupBox("Filter Rules")
        group.setStyleSheet(f"QGroupBox {{ color: {title_color}; }}")
        v = QVBoxLayout(group); v.setContentsMargins(10, 10, 10, 12); v.setSpacing(8)

        tbl = QTableView(); tbl.setModel(model)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setAlternatingRowColors(True); tbl.setShowGrid(False)
        tbl.setFrameShape(QFrame.Shape.NoFrame); tbl.verticalHeader().hide()
        tbl.setMouseTracking(True)
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); tbl.setColumnWidth(3, 38)
        delegate = DeleteButtonDelegate(self)
        delegate.delete_requested.connect(lambda row, d=del_cb: d(row))
        tbl.setItemDelegateForColumn(3, delegate)
        setattr(self, delegate_attr, delegate)
        tbl.setMinimumHeight(90); tbl.setMaximumHeight(220)
        tbl.doubleClicked.connect(lambda idx, ec=edit_cb: ec(idx))
        tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tbl.customContextMenuRequested.connect(lambda pos, t=tbl, ec=edit_cb, dc=del_cb: ctx_cb(pos, t, ec, dc))
        v.addWidget(tbl)

        # Store table ref by delegate_attr name convention
        if delegate_attr == "_delete_delegate": self.rules_table = tbl
        else:                                   self.cl_rules_table = tbl

        toolbar = QHBoxLayout(); toolbar.setSpacing(6)
        btn_clear = QPushButton("Clear All"); btn_clear.setFixedHeight(28)
        btn_clear.clicked.connect(clear_cb)
        hint = QLabel("  ✕ = delete   ·   double-click = edit")
        hint.setStyleSheet("color: #45475a; font-size: 11px; font-style: italic;")
        toolbar.addWidget(btn_clear); toolbar.addStretch(); toolbar.addWidget(hint)
        v.addLayout(toolbar)

        sep = QFrame(); sep.setObjectName("separator"); sep.setFrameShape(QFrame.Shape.HLine)
        v.addWidget(sep)

        btn_add = QPushButton("＋  Add New Rule…"); btn_add.setObjectName("btn_run")
        if accent != "#89b4fa": btn_add.setObjectName("btn_delete")
        btn_add.setFixedHeight(38); btn_add.clicked.connect(add_cb)
        v.addWidget(btn_add)

        if delegate_attr == "_delete_delegate": self.btn_add_rule     = btn_add
        else:                                   self.cl_btn_add_rule  = btn_add
        return group

    # ── Organizer: action row ─────────────────────────────────────────

    def _make_org_action_row(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border-top: 1px solid #313244; padding-top: 6px;")
        v = QVBoxLayout(w); v.setContentsMargins(0, 8, 8, 2); v.setSpacing(4)
        cr = QHBoxLayout()
        self.lbl_file_count = QLabel("")
        self.lbl_file_count.setStyleSheet("color: #6c7086; font-size: 12px;")
        self.lbl_action_breakdown = QLabel("")
        self.lbl_action_breakdown.setStyleSheet("font-size: 11px;")
        cr.addWidget(self.lbl_file_count); cr.addStretch(); cr.addWidget(self.lbl_action_breakdown)
        v.addLayout(cr)
        er = QHBoxLayout()
        self.lbl_eta = QLabel(""); self.lbl_eta.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        er.addWidget(self.lbl_eta); er.addStretch(); v.addLayout(er)
        br = QHBoxLayout(); br.setSpacing(8)
        self.btn_preview = QPushButton("Preview"); self.btn_preview.setFixedHeight(38)
        self.btn_run = QPushButton("Run"); self.btn_run.setObjectName("btn_run"); self.btn_run.setFixedHeight(38)
        self.btn_cancel = QPushButton("Cancel"); self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setFixedHeight(38); self.btn_cancel.setVisible(False)
        br.addWidget(self.btn_preview, 1); br.addWidget(self.btn_run, 1); br.addWidget(self.btn_cancel, 1)
        v.addLayout(br); return w

    # ==================================================================
    # TAB 2 — File Cleaner
    # ==================================================================

    def _make_cleaner_tab(self) -> QWidget:
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False); sp.setHandleWidth(6)
        sp.addWidget(self._make_cl_left()); sp.addWidget(self._make_cl_right())
        sp.setSizes([460, 980]); return sp

    def _make_cl_left(self) -> QWidget:
        outer = QWidget(); outer.setMinimumWidth(400); outer.setMaximumWidth(540)
        ol = QVBoxLayout(outer); ol.setContentsMargins(0, 0, 0, 0); ol.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(); v = QVBoxLayout(content)
        v.setContentsMargins(0, 10, 8, 8); v.setSpacing(10)
        v.addWidget(self._make_cl_target_dir())
        v.addWidget(self._make_cl_options())
        v.addWidget(self._make_rules_group(self.cl_rules_model, "_cl_delete_delegate",
                                           self._cl_open_add_rule_dlg, self._cl_open_edit_rule_dlg,
                                           self._del_cl_rule, self._clr_cl_rules,
                                           self._org_ctx_menu, accent="#f38ba8"))
        v.addStretch()
        scroll.setWidget(content); ol.addWidget(scroll, 1)
        ol.addWidget(self._make_cl_action_row()); return outer

    def _make_cl_right(self) -> QWidget:
        panel = QWidget(); v = QVBoxLayout(panel)
        v.setContentsMargins(8, 10, 0, 0); v.setSpacing(0)
        sp = QSplitter(Qt.Orientation.Vertical)
        sp.setChildrenCollapsible(False); sp.setHandleWidth(5)
        sp.addWidget(self._make_preview_table(self.cleaner_model, "Files to Delete"))
        sp.addWidget(self._make_log_panel("cl_log_view")); sp.setSizes([620, 200])
        v.addWidget(sp, 1); return panel

    def _make_cl_target_dir(self) -> QWidget:
        group = QGroupBox("Target Directory")
        group.setStyleSheet("QGroupBox { color: #f38ba8; }")
        h = QHBoxLayout(group); h.setContentsMargins(10, 8, 10, 10); h.setSpacing(6)
        self.cl_edit_dir = QLineEdit()
        self.cl_edit_dir.setPlaceholderText("Folder to scan for deletion…")
        self.cl_btn_browse = QPushButton("Browse")
        self.cl_btn_browse.setObjectName("btn_browse"); self.cl_btn_browse.setFixedWidth(72)
        h.addWidget(self.cl_edit_dir, 1); h.addWidget(self.cl_btn_browse); return group

    def _make_cl_options(self) -> QWidget:
        group = QGroupBox("Cleaner Options")
        group.setStyleSheet("QGroupBox { color: #f38ba8; }")
        v = QVBoxLayout(group); v.setContentsMargins(10, 8, 10, 10); v.setSpacing(8)

        self.cl_chk_recursive = QCheckBox("Include sub-folders")
        self.cl_chk_dryrun    = QCheckBox("Dry run  (preview only — no files deleted)")
        v.addWidget(self.cl_chk_recursive); v.addWidget(self.cl_chk_dryrun)

        sep = QFrame(); sep.setObjectName("separator"); sep.setFrameShape(QFrame.Shape.HLine)
        v.addWidget(sep)

        mode_lbl = QLabel("Default behaviour when no rule matches:")
        mode_lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        v.addWidget(mode_lbl)

        self.cl_radio_matched = QRadioButton(
            "Delete only files with an explicit DELETE rule  (safe default)")
        self.cl_radio_all     = QRadioButton(
            "Delete ALL files — use SKIP rules to protect specific files")
        self.cl_radio_matched.setChecked(True)

        danger_lbl = QLabel("⚠  Use with caution — this will delete every unprotected file.")
        danger_lbl.setStyleSheet("color: #f9e2af; font-size: 11px; margin-left: 22px;")
        danger_lbl.setWordWrap(True)

        v.addWidget(self.cl_radio_matched); v.addWidget(self.cl_radio_all)
        v.addWidget(danger_lbl)

        # Show warning only when "delete all" is selected
        def _toggle_warn():
            danger_lbl.setVisible(self.cl_radio_all.isChecked())
        self.cl_radio_all.toggled.connect(_toggle_warn); _toggle_warn()
        return group

    def _make_cl_action_row(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border-top: 1px solid #313244; padding-top: 6px;")
        v = QVBoxLayout(w); v.setContentsMargins(0, 8, 8, 2); v.setSpacing(4)
        cr = QHBoxLayout()
        self.cl_lbl_file_count = QLabel("")
        self.cl_lbl_file_count.setStyleSheet("color: #6c7086; font-size: 12px;")
        self.cl_lbl_breakdown = QLabel(""); self.cl_lbl_breakdown.setStyleSheet("font-size: 11px;")
        cr.addWidget(self.cl_lbl_file_count); cr.addStretch(); cr.addWidget(self.cl_lbl_breakdown)
        v.addLayout(cr)
        er = QHBoxLayout()
        self.cl_lbl_eta = QLabel("")
        self.cl_lbl_eta.setStyleSheet("color: #f38ba8; font-size: 11px;")
        er.addWidget(self.cl_lbl_eta); er.addStretch(); v.addLayout(er)
        br = QHBoxLayout(); br.setSpacing(8)
        self.cl_btn_preview = QPushButton("Preview"); self.cl_btn_preview.setFixedHeight(38)
        self.cl_btn_run = QPushButton("Delete Files")
        self.cl_btn_run.setObjectName("btn_delete"); self.cl_btn_run.setFixedHeight(38)
        self.cl_btn_cancel = QPushButton("Cancel"); self.cl_btn_cancel.setObjectName("btn_cancel")
        self.cl_btn_cancel.setFixedHeight(38); self.cl_btn_cancel.setVisible(False)
        br.addWidget(self.cl_btn_preview, 1); br.addWidget(self.cl_btn_run, 1)
        br.addWidget(self.cl_btn_cancel, 1); v.addLayout(br); return w

    # ── Shared: preview table & log ───────────────────────────────────

    def _make_preview_table(self, model, title: str) -> QWidget:
        group = QGroupBox(title)
        if "Delete" in title: group.setStyleSheet("QGroupBox { color: #f38ba8; }")
        v = QVBoxLayout(group); v.setContentsMargins(8, 8, 8, 8)
        tbl = QTableView(); tbl.setModel(model)
        tbl.setAlternatingRowColors(True)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setShowGrid(False); tbl.setFrameShape(QFrame.Shape.NoFrame)
        tbl.verticalHeader().hide()
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(tbl)
        if model is self.model: self.table = tbl
        else:                   self.cl_table = tbl
        return group

    def _make_log_panel(self, attr: str) -> QWidget:
        group = QGroupBox("Log")
        v = QVBoxLayout(group); v.setContentsMargins(8, 6, 8, 8); v.setSpacing(4)
        top = QHBoxLayout(); top.addStretch()
        btn_clear = QToolButton(); btn_clear.setText("Clear")
        log_view = QTextEdit(); log_view.setReadOnly(True)
        btn_clear.clicked.connect(log_view.clear)
        top.addWidget(btn_clear); v.addLayout(top); v.addWidget(log_view, 1)
        setattr(self, attr, log_view); return group

    def _make_progress_bar(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(10)
        h = QHBoxLayout(w); h.setContentsMargins(0, 2, 0, 0)
        self.progress = QProgressBar(); self.progress.setFixedHeight(6)
        self.progress.setValue(0); self.progress.setTextVisible(False)
        h.addWidget(self.progress); return w

    # --- Signal wiring ---

    def _connect_signals(self):
        # Organizer
        self.btn_browse.clicked.connect(self._browse)
        self.btn_browse_output.clicked.connect(self._browse_output)
        self.btn_preview.clicked.connect(self._on_org_preview)
        self.btn_run.clicked.connect(self._on_org_run)
        self.btn_cancel.clicked.connect(self._on_org_cancel)
        self.edit_dir.textChanged.connect(self._reset_org_table)
        self.edit_output.textChanged.connect(self._reset_org_table)
        self.combo_sort.currentIndexChanged.connect(self._reset_org_table)
        self.vm.preview_ready.connect(self._on_org_preview_ready)
        self.vm.batch_update.connect(self._on_org_batch)
        self.vm.log_emitted.connect(lambda t: self._append_log(self.log_view, t))
        self.vm.run_finished.connect(self._on_org_finished)
        self.vm.run_error.connect(self._on_org_error)
        self.vm.state_changed.connect(self._on_org_state)
        # Cleaner
        self.cl_btn_browse.clicked.connect(self._cl_browse)
        self.cl_btn_preview.clicked.connect(self._on_cl_preview)
        self.cl_btn_run.clicked.connect(self._on_cl_run)
        self.cl_btn_cancel.clicked.connect(self._on_cl_cancel)
        self.cl_edit_dir.textChanged.connect(self._reset_cl_table)
        self.cleaner_vm.preview_ready.connect(self._on_cl_preview_ready)
        self.cleaner_vm.batch_update.connect(self._on_cl_batch)
        self.cleaner_vm.log_emitted.connect(lambda t: self._append_log(self.cl_log_view, t))
        self.cleaner_vm.run_finished.connect(self._on_cl_finished)
        self.cleaner_vm.run_error.connect(self._on_cl_error)
        self.cleaner_vm.state_changed.connect(self._on_cl_state)

    # ==================================================================
    # ORGANIZER slots
    # ==================================================================

    def _browse(self):
        p = QFileDialog.getExistingDirectory(self, "Select source folder",
                                             self.edit_dir.text() or str(Path.home()))
        if p: self.edit_dir.setText(p); self._on_org_preview()

    def _browse_output(self):
        p = QFileDialog.getExistingDirectory(self, "Select output folder",
                self.edit_output.text() or self.edit_dir.text() or str(Path.home()))
        if p: self.edit_output.setText(p); self._on_org_preview()

    def _update_subtype_state(self):
        ok = self.combo_sort.currentData() == "type"
        self.chk_subtypes.setEnabled(ok)
        if not ok: self.chk_subtypes.setChecked(False)

    def _build_org_config(self) -> OrganizerConfig:
        specs = self.rules_model.specs()
        return OrganizerConfig(
            sort_mode        = SortMode(self.combo_sort.currentData()),
            output_dir       = self.edit_output.text().strip() or None,
            rules            = RuleEngine.from_specs(specs) if specs else None,
            use_subtypes     = self.chk_subtypes.isChecked(),
            dry_run          = self.chk_dryrun.isChecked(),
            recursive        = self.chk_recursive.isChecked(),
            copy_mode        = self.radio_copy.isChecked(),
            duplicate_policy = self.combo_dup.currentData(),
            log_level        = logging.INFO,
        )

    def _on_org_preview(self):
        d = self.edit_dir.text().strip()
        if not d: self.status_bar.showMessage("Select a source directory first."); return
        self.vm.request_preview(d, self._build_org_config())

    def _on_org_preview_ready(self, plan):
        self.model.load(plan)
        count  = len(plan); is_copy = self.radio_copy.isChecked()
        n_act  = sum(1 for r in plan if r.get("action") in ("move", "copy"))
        n_del  = sum(1 for r in plan if r.get("action") == "delete")
        n_skip = sum(1 for r in plan if r.get("action") == "skip")
        self.lbl_file_count.setText(f"{count:,} file{'s' if count != 1 else ''} found")
        verb = "copy" if is_copy else "move"; vc = "#a6e3a1" if is_copy else "#89b4fa"
        parts = []
        if n_act:  parts.append(f'<span style="color:{vc}">{n_act:,} {verb}</span>')
        if n_del:  parts.append(f'<span style="color:#f38ba8">{n_del:,} delete</span>')
        if n_skip: parts.append(f'<span style="color:#6c7086">{n_skip:,} skip</span>')
        self.lbl_action_breakdown.setText("  ".join(parts))
        ops = n_act + n_del
        self.lbl_eta.setText(f"~{ops:,} operation{'s' if ops != 1 else ''} queued" if ops else "")
        self.progress.setRange(0, max(count, 1)); self.progress.setValue(0)
        self.status_bar.showMessage(
            f"Preview: {n_act:,} to {verb}, {n_del:,} to delete, {n_skip:,} to skip.")

    def _on_org_run(self):
        d = self.edit_dir.text().strip()
        if not d: self.status_bar.showMessage("Select a source directory first."); return
        cfg = self._build_org_config()
        self.vm.save_settings(d, self.edit_output.text().strip(),
                              self.combo_sort.currentData(), cfg.dry_run, cfg.recursive,
                              cfg.use_subtypes, self.combo_dup.currentData(),
                              cfg.copy_mode, self.rules_model.specs())
        self._run_start_time = time.time()
        verb = "COPY DRY RUN" if (cfg.copy_mode and cfg.dry_run) else \
               ("DRY RUN" if cfg.dry_run else ("Copying" if cfg.copy_mode else "Organizing"))
        self.lbl_eta.setText("ETA: calculating…")
        self.status_bar.showMessage(f"{verb}…")
        self.vm.start_run(d, cfg)

    def _on_org_cancel(self):
        self.vm.cancel(); self.btn_cancel.setText("Cancelling…"); self.btn_cancel.setEnabled(False)
        self.lbl_eta.setText(""); self.status_bar.showMessage("Cancelling…")

    def _on_org_batch(self, current, total, batch):
        self.progress.setMaximum(max(total, 1)); self.progress.setValue(current)
        eta = self._compute_eta(current, total)
        self.lbl_eta.setText(eta)
        self.status_bar.showMessage(f"Processing {current:,} of {total:,}…  {eta}")
        if batch: self.model.apply_batch(batch)

    def _on_org_finished(self, summary):
        moved   = summary.get("moved",  0); deleted   = summary.get("deleted",  0)
        skipped = summary.get("skipped",0); errors    = summary.get("errors",   0)
        cancelled = summary.get("cancelled", False)
        elapsed = time.time() - self._run_start_time if self._run_start_time else 0
        is_copy = self.radio_copy.isChecked()
        tag  = "[CANCELLED] " if cancelled else ("[DRY RUN] " if self.chk_dryrun.isChecked() else "")
        verb = "copied" if is_copy else "moved"
        parts = [f"{moved:,} {verb}"]
        if deleted: parts.append(f"{deleted:,} deleted")
        parts += [f"{skipped:,} skipped", f"{errors} error(s)"]
        msg = f"{tag}Done — {', '.join(parts)}"
        if elapsed > 0 and not cancelled: msg += f"  ({self._fmt_elapsed(elapsed)})"
        self.status_bar.showMessage(msg)
        self.lbl_eta.setText(f"Completed in {self._fmt_elapsed(elapsed)}" if not cancelled else "")
        if not cancelled: self.progress.setValue(self.progress.maximum())
        self._append_log(self.log_view, f"\n{msg}")

    def _on_org_error(self, msg):
        self.status_bar.showMessage(f"Error: {msg}")
        self.lbl_eta.setText(""); self._append_log(self.log_view, f"[ERROR] {msg}")

    def _on_org_state(self, state):
        busy = state in ("running", "previewing")
        self.btn_run.setEnabled(not busy); self.btn_preview.setEnabled(not busy)
        self.btn_browse.setEnabled(not busy); self.btn_browse_output.setEnabled(not busy)
        self.btn_add_rule.setEnabled(not busy); self.btn_cancel.setVisible(busy)
        if state == "idle":
            self.btn_cancel.setText("Cancel"); self.btn_cancel.setEnabled(True)
            if self.progress.maximum() == 0: self.progress.setRange(0, 1); self.progress.setValue(0)
        elif state == "previewing":
            self.progress.setRange(0, 0)
            self.status_bar.showMessage("Scanning folder…"); self.lbl_eta.setText("")

    # ── Organizer rule actions ────────────────────────────────────────

    def _open_add_rule_dlg(self):
        dlg = RuleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            s = dlg.result_spec()
            if s: self.rules_model.add_spec(s); self._on_org_preview()

    def _open_edit_rule_dlg(self, index: QModelIndex):
        if index.column() == 3: return
        row = index.row(); specs = self.rules_model.specs()
        if row >= len(specs): return
        dlg = RuleDialog(self, spec=specs[row])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            s = dlg.result_spec()
            if s: self.rules_model.remove_row(row); self.rules_model.insert_spec(row, s); self._on_org_preview()

    def _del_org_rule(self, row):
        self.rules_model.remove_row(row); self._on_org_preview()

    def _clr_org_rules(self):
        self.rules_model.load([]); self._on_org_preview()

    def _org_ctx_menu(self, pos, tbl, edit_cb, del_cb):
        idx = tbl.indexAt(pos)
        if not idx.isValid(): return
        menu = QMenu(self)
        ae = menu.addAction("✎  Edit Rule"); ad = menu.addAction("✕  Delete Rule")
        chosen = menu.exec(tbl.viewport().mapToGlobal(pos))
        if chosen == ad: del_cb(idx.row())
        elif chosen == ae: edit_cb(idx)

    # ==================================================================
    # CLEANER slots
    # ==================================================================

    def _cl_browse(self):
        p = QFileDialog.getExistingDirectory(self, "Select target folder",
                                             self.cl_edit_dir.text() or str(Path.home()))
        if p: self.cl_edit_dir.setText(p); self._on_cl_preview()

    def _build_cl_config(self) -> CleanerConfig:
        specs = self.cl_rules_model.specs()
        return CleanerConfig(
            rules                 = RuleEngine.from_specs(specs) if specs else None,
            recursive             = self.cl_chk_recursive.isChecked(),
            dry_run               = self.cl_chk_dryrun.isChecked(),
            delete_all_by_default = self.cl_radio_all.isChecked(),
            log_level             = logging.INFO,
        )

    def _on_cl_preview(self):
        d = self.cl_edit_dir.text().strip()
        if not d: self.status_bar.showMessage("Select a target directory first."); return
        self.cleaner_vm.request_preview(d, self._build_cl_config())

    def _on_cl_preview_ready(self, plan):
        self.cleaner_model.load(plan)
        count = len(plan)
        n_del  = sum(1 for r in plan if r.get("action") == "delete")
        n_keep = count - n_del
        self.cl_lbl_file_count.setText(f"{count:,} file{'s' if count != 1 else ''} found")
        parts = []
        if n_del:  parts.append(f'<span style="color:#f38ba8">{n_del:,} will delete</span>')
        if n_keep: parts.append(f'<span style="color:#6c7086">{n_keep:,} will keep</span>')
        self.cl_lbl_breakdown.setText("  ".join(parts))
        self.cl_lbl_eta.setText(f"~{n_del:,} file{'s' if n_del != 1 else ''} queued for deletion" if n_del else "Nothing to delete")
        self.progress.setRange(0, max(count, 1)); self.progress.setValue(0)
        self.status_bar.showMessage(f"Preview: {n_del:,} to delete, {n_keep:,} to keep.")

    def _on_cl_run(self):
        d = self.cl_edit_dir.text().strip()
        if not d: self.status_bar.showMessage("Select a target directory first."); return
        cfg = self._build_cl_config()
        self.vm.save_cleaner_settings(cfg.recursive, cfg.dry_run,
                                      cfg.delete_all_by_default, self.cl_rules_model.specs())
        self._run_start_time = time.time()
        tag = "DRY RUN " if cfg.dry_run else ""
        self.cl_lbl_eta.setText("ETA: calculating…")
        self.status_bar.showMessage(f"{tag}Deleting files…")
        self.cleaner_vm.start_run(d, cfg)

    def _on_cl_cancel(self):
        self.cleaner_vm.cancel()
        self.cl_btn_cancel.setText("Cancelling…"); self.cl_btn_cancel.setEnabled(False)
        self.cl_lbl_eta.setText(""); self.status_bar.showMessage("Cancelling…")

    def _on_cl_batch(self, current, total, batch):
        self.progress.setMaximum(max(total, 1)); self.progress.setValue(current)
        eta = self._compute_eta(current, total)
        self.cl_lbl_eta.setText(eta)
        self.status_bar.showMessage(f"Deleting {current:,} of {total:,}…  {eta}")
        if batch: self.cleaner_model.apply_batch(batch)

    def _on_cl_finished(self, summary):
        deleted = summary.get("deleted", 0); skipped = summary.get("skipped", 0)
        errors  = summary.get("errors",  0); cancelled = summary.get("cancelled", False)
        elapsed = time.time() - self._run_start_time if self._run_start_time else 0
        tag  = "[CANCELLED] " if cancelled else ("[DRY RUN] " if self.cl_chk_dryrun.isChecked() else "")
        msg  = f"{tag}Done — {deleted:,} deleted, {skipped:,} kept, {errors} error(s)"
        if elapsed > 0 and not cancelled: msg += f"  ({self._fmt_elapsed(elapsed)})"
        self.status_bar.showMessage(msg)
        self.cl_lbl_eta.setText(f"Completed in {self._fmt_elapsed(elapsed)}" if not cancelled else "")
        if not cancelled: self.progress.setValue(self.progress.maximum())
        self._append_log(self.cl_log_view, f"\n{msg}")

    def _on_cl_error(self, msg):
        self.status_bar.showMessage(f"Error: {msg}")
        self.cl_lbl_eta.setText(""); self._append_log(self.cl_log_view, f"[ERROR] {msg}")

    def _on_cl_state(self, state):
        busy = state in ("running", "previewing")
        self.cl_btn_run.setEnabled(not busy); self.cl_btn_preview.setEnabled(not busy)
        self.cl_btn_browse.setEnabled(not busy); self.cl_btn_add_rule.setEnabled(not busy)
        self.cl_btn_cancel.setVisible(busy)
        if state == "idle":
            self.cl_btn_cancel.setText("Cancel"); self.cl_btn_cancel.setEnabled(True)
            if self.progress.maximum() == 0: self.progress.setRange(0, 1); self.progress.setValue(0)
        elif state == "previewing":
            self.progress.setRange(0, 0)
            self.status_bar.showMessage("Scanning for files…"); self.cl_lbl_eta.setText("")

    # ── Cleaner rule actions ──────────────────────────────────────────

    def _cl_open_add_rule_dlg(self):
        dlg = RuleDialog(self, cleaner_mode=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            s = dlg.result_spec()
            if s: self.cl_rules_model.add_spec(s); self._on_cl_preview()

    def _cl_open_edit_rule_dlg(self, index: QModelIndex):
        if index.column() == 3: return
        row = index.row(); specs = self.cl_rules_model.specs()
        if row >= len(specs): return
        dlg = RuleDialog(self, spec=specs[row], cleaner_mode=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            s = dlg.result_spec()
            if s:
                self.cl_rules_model.remove_row(row)
                self.cl_rules_model.insert_spec(row, s); self._on_cl_preview()

    def _del_cl_rule(self, row):
        self.cl_rules_model.remove_row(row); self._on_cl_preview()

    def _clr_cl_rules(self):
        self.cl_rules_model.load([]); self._on_cl_preview()

    # ==================================================================
    # Shared helpers
    # ==================================================================

    def _reset_org_table(self):
        self.model.load([]); self.lbl_file_count.setText("")
        self.lbl_action_breakdown.setText(""); self.lbl_eta.setText(""); self.progress.setValue(0)

    def _reset_cl_table(self):
        self.cleaner_model.load([]); self.cl_lbl_file_count.setText("")
        self.cl_lbl_breakdown.setText(""); self.cl_lbl_eta.setText(""); self.progress.setValue(0)

    def _compute_eta(self, current, total) -> str:
        if current <= 0 or self._run_start_time <= 0: return "ETA: calculating…"
        elapsed = time.time() - self._run_start_time
        if elapsed < 0.5: return "ETA: calculating…"
        remaining = (total - current) / (current / elapsed)
        return f"ETA: {self._fmt_secs(remaining)} remaining"

    @staticmethod
    def _fmt_secs(s: float) -> str:
        s = int(s)
        if s < 60:   return f"{s}s"
        if s < 3600: m, sec = divmod(s, 60); return f"{m}m {sec:02d}s"
        h, r = divmod(s, 3600); return f"{h}h {r // 60:02d}m"

    @staticmethod
    def _fmt_elapsed(s: float) -> str:
        s = int(s)
        if s < 60:   return f"{s}s"
        if s < 3600: m, sec = divmod(s, 60); return f"{m}m {sec:02d}s"
        h, r = divmod(s, 3600); return f"{h}h {r // 60:02d}m"

    @staticmethod
    def _append_log(view: QTextEdit, text: str):
        colors = {"[INFO]": "#a6adc8", "[WARNING]": "#f9e2af",
                  "[ERROR]": "#f38ba8", "[DEBUG]": "#6c7086"}
        html_lines = []
        for line in text.split("\n"):
            if not line: continue
            lc = "#a6adc8"
            for tag, c in colors.items():
                if tag in line: lc = c; break
            html_lines.append(f'<span style="color:{lc}">{line}</span>')
        if html_lines: view.append("<br>".join(html_lines))
        doc = view.document()
        while doc.blockCount() > 500:
            cur = view.textCursor(); cur.movePosition(cur.MoveOperation.Start)
            cur.select(cur.SelectionType.BlockUnderCursor)
            cur.removeSelectedText(); cur.deleteChar()

    # --- Settings ---

    def _restore_settings(self):
        s = self.vm.load_settings()
        idx = self.combo_sort.findData(s["sort_mode"])
        if idx >= 0: self.combo_sort.setCurrentIndex(idx)
        self.chk_dryrun.setChecked(s["dry_run"]); self.chk_recursive.setChecked(s["recursive"])
        self.chk_subtypes.setChecked(s.get("use_subtypes", False))
        self._update_subtype_state()
        idx = self.combo_dup.findData(s["duplicate"])
        if idx >= 0: self.combo_dup.setCurrentIndex(idx)
        if s.get("copy_mode"): self.radio_copy.setChecked(True)
        if s.get("rules"):     self.rules_model.load(s["rules"])
        # Cleaner settings
        cs = self.vm.load_cleaner_settings()
        self.cl_chk_recursive.setChecked(cs["recursive"])
        self.cl_chk_dryrun.setChecked(cs["dry_run"])
        if cs["delete_all"]: self.cl_radio_all.setChecked(True)
        if cs.get("rules"):  self.cl_rules_model.load(cs["rules"])

    def closeEvent(self, event):
        self.vm.cancel(); self.cleaner_vm.cancel(); event.accept()


# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("File Organizer")
    app.setOrganizationName("FileOrganizerApp")
    # Set the window icon so it appears in the title bar and taskbar
    icon_path = _resource_path("app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow(); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
