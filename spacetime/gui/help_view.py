"""Help browser widget for the editor."""

from pathlib import Path
import re
import sys
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QStyledItemDelegate,
)
from PySide6.QtCore import QEvent, QSize, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QFontMetrics

def installed_ui_font() -> QFont:
    """Return a common installed sans-serif font without using Qt aliases."""
    families = set(QFontDatabase.families())
    family = next(
        (
            name
            for name in ("Helvetica", "Arial", "Liberation Sans", "DejaVu Sans")
            if name in families
        ),
        next(iter(families), ""),
    )
    font = QFont(family)
    font.setPointSize(font.pointSize() + 1)
    return font

class HelpView(QTextBrowser):
    """Display the bundled HTML help page."""

    def __init__(self, parent=None):
        """Load the help document into the browser."""
        font = installed_ui_font()
        if QApplication.instance() is not None:
            QApplication.instance().setFont(font)
        super().__init__(parent)
        self.setFont(font)
        self.document().setDefaultFont(font)
        html = (
            Path(__file__).parents[1] / "resources" / "help" / "index.html"
        )
        self.document().setBaseUrl(QUrl.fromLocalFile(str(html)))
        html_text = html.read_text(encoding="utf-8").replace(
            "__UI_FONT__", font.family()
        )
        self._help_path = html
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._open_help_link)
        self.setHtml(html_text)

    def _open_help_link(self, url: QUrl) -> None:
        """Open the Help document in the system browser when requested."""
        if url.scheme() == "help-browser":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._help_path)))
            return
        self.setSource(url)

    def show_section(self, anchor: str) -> None:
        """Scroll the loaded help document to an internal section."""
        self.scrollToAnchor(anchor)

    def changeEvent(self, event):
        """Keep the rich-text document synchronized with the app font."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.document().setDefaultFont(self.font())


class _ShortcutDelegate(QStyledItemDelegate):
    """Render short shortcut inputs as keycaps with plain separators."""

    _separator_pattern = re.compile(r"(\s+\+\s+|\s+/\s+)")

    def _parts(self, text):
        parts = self._separator_pattern.split(text)
        return parts if len(parts) > 1 and len(text) <= 18 else None

    def paint(self, painter, option, index):
        """Paint keycaps while retaining the cell's original text."""
        text = index.data()
        parts = self._parts(text)
        if parts is None:
            return super().paint(painter, option, index)
        painter.save()
        painter.setFont(option.font)
        metrics = painter.fontMetrics()
        x = option.rect.left() + 6
        center_y = option.rect.center().y()
        for part in parts:
            if not part:
                continue
            if part.isspace() or part.strip() in ("+", "/"):
                painter.setPen(option.palette.text().color())
                painter.drawText(
                    int(x),
                    int(center_y + metrics.ascent() / 2),
                    part.strip(),
                )
                x += metrics.horizontalAdvance(part.strip()) + 6
                continue
            width = metrics.horizontalAdvance(part) + 12
            height = min(24, max(20, option.rect.height() - 6))
            top = center_y - height / 2
            painter.setPen(option.palette.mid().color())
            painter.setBrush(option.palette.alternateBase())
            painter.drawRoundedRect(int(x), int(top), int(width), int(height), 4, 4)
            painter.setPen(option.palette.text().color())
            painter.drawText(
                int(x + 6),
                int(center_y + metrics.ascent() / 2),
                part,
            )
            x += width + 5
        painter.restore()

    def sizeHint(self, option, index):
        """Reserve enough width and height for the rendered keycaps."""
        size = super().sizeHint(option, index)
        parts = self._parts(index.data())
        if parts is None:
            return size
        metrics = QFontMetrics(option.font)
        width = 12
        for part in parts:
            if not part:
                continue
            text = part.strip()
            width += metrics.horizontalAdvance(text) + (12 if text in ("+", "/") else 17)
        return size.expandedTo(QSize(width, 26))


class ShortcutsView(QWidget):
    """Display keyboard, mouse, and trackpad controls in a compact table."""

    def __init__(self, parent=None):
        """Build the platform-aware shortcuts table."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        title = QLabel("Keyboard Shortcuts & Gestures", self)
        title_font = self.font()
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        table = QTableWidget(self)
        self.table = table
        table.setItemDelegateForColumn(0, _ShortcutDelegate(table))
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(table)
        note = QLabel(
            "Mouse-wheel and trackpad sensitivity can be adjusted in Preferences.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        modifier = "Cmd" if sys.platform == "darwin" else "Ctrl"
        rows = [
            ("↑ / ↓", "Advance / rewind time by 0.1"),
            (f"{modifier} + ↑ / ↓", "Advance / rewind time by 1.0 (10× normal)"),
            (f"{modifier} + 0", "Set time to zero"),
            ("← / →", "Move the view"),
            (f"{modifier} + ← / →", "Move the view by 10× normal distance"),
            ("Shift + ↑ / ↓", "Transform frame by relative beta ±0.1"),
            ("Shift + 0", "Return to the original reference frame"),
            ("+ / -", "Zoom in / out"),
            ("Left-drag", "Move Highway objects or free spacetime events"),
            ("Right-click", "Open the context menu"),
            (
                "Wheel / two-finger scroll",
                "Pan horizontally; advance time in the Spacetime Diagram or change frame on the Highway",
            ),
            ("Pinch", "Zoom both views"),
        ]
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Input", "Action"])
        table.setRowCount(len(rows))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setWordWrap(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 150)
        for row, (input_text, action) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(input_text))
            table.setItem(row, 1, QTableWidgetItem(action))

    def changeEvent(self, event):
        """Resize shortcut rows after a global font-size change."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.table.resizeRowsToContents()
