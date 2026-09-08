"""Application entry point for the Spacetime editor."""

from __future__ import annotations
import sys
from pathlib import Path
import argparse
from .model.scenario import Scenario
from .persistence.scenario_file import load_scenario
def main() -> int:
    """Parse command-line arguments and run the editor."""
    try:
        from PySide6.QtWidgets import QApplication
        from .gui.main_window import MainWindow
    except ImportError as exc:
        print("PySide6 is required to run the GUI:", exc, file=sys.stderr); return 2
    parser=argparse.ArgumentParser(description="Spacetime special-relativity scenario editor")
    parser.add_argument("scenario", nargs="?", help="scenario .sce file to open")
    args=parser.parse_args()
    scenario = load_scenario(args.scenario) if args.scenario else Scenario()
    if not scenario.objects and not args.scenario: scenario.add_clock()
    app=QApplication(sys.argv); window=MainWindow(scenario, path=args.scenario); window.show(); return app.exec()
if __name__ == "__main__": raise SystemExit(main())
