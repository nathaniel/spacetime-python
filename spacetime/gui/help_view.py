"""Help browser widget for the editor."""

from pathlib import Path
import sys
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QEvent, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase

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


class ShortcutsView(QWidget):
    """Display keyboard, mouse, and trackpad controls in a compact table."""

    def __init__(self, parent=None):
        """Build the platform-aware shortcuts table."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("Keyboard Shortcuts & Gestures", self)
        title_font = self.font()
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        table = QTableWidget(self)
        self.table = table
        layout.addWidget(table)
        modifier = "Cmd" if sys.platform == "darwin" else "Ctrl"
        rows = [
            ("↑ / ↓", "Advance / rewind time by 0.1"),
            (f"{modifier}+↑ / ↓", "Advance / rewind time by 1.0"),
            (f"{modifier}+0", "Set time to zero"),
            ("← / →", "Move the view"),
            (f"{modifier}+← / →", "Move the view by 10× the normal distance"),
            ("Shift+↑ / ↓", "Transform the reference frame"),
            ("Shift+0", "Return to the original reference frame"),
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
