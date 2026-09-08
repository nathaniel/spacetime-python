"""Help browser widget for the editor."""

from pathlib import Path
import sys
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont

class HelpView(QTextBrowser):
    """Display the bundled HTML help page."""

    def __init__(self, parent=None):
        """Load the help document into the browser."""
        super().__init__(parent)
        font = QFont("Helvetica")
        self.setFont(font)
        self.document().setDefaultFont(font)
        html = (
            Path(__file__).parents[1] / "resources" / "help" / "index.html"
        )
        self.document().setBaseUrl(QUrl.fromLocalFile(str(html)))
        self.setHtml(html.read_text(encoding="utf-8"))


class ShortcutsView(QTableWidget):
    """Display keyboard, mouse, and trackpad controls in a compact table."""

    def __init__(self, parent=None):
        """Build the platform-aware shortcuts table."""
        super().__init__(parent)
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
                "Pan horizontally; advance time in the spacetime diagram or change frame on the Highway",
            ),
            ("Pinch", "Zoom both views"),
        ]
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Input", "Action"])
        self.setRowCount(len(rows))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 150)
        for row, (input_text, action) in enumerate(rows):
            self.setItem(row, 0, QTableWidgetItem(input_text))
            self.setItem(row, 1, QTableWidgetItem(action))
