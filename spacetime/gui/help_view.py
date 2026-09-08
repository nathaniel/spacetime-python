"""Help browser widget for the editor."""

from pathlib import Path
import sys
from PySide6.QtWidgets import QTextBrowser

class HelpView(QTextBrowser):
    """Display the bundled HTML help page."""

    def __init__(self, parent=None):
        """Load the help document into the browser."""
        super().__init__(parent)
        html = (
            Path(__file__).parents[1] / "resources" / "help" / "index.html"
        ).read_text(encoding="utf-8")
        modifier = "Cmd" if sys.platform == "darwin" else "Ctrl"
        self.setHtml(html.replace("MODIFIER", modifier))
