"""Main Qt window for the Spacetime scenario editor."""

from __future__ import annotations
from ..commands.undo_redo import AddEvent, AddObject, DeleteEvent, DeleteObject, History, SetFrame, SetTime, Snapshot
from ..persistence.scenario_file import load_scenario, save_scenario
from pathlib import Path
from .views import HighwayView, SpacetimeDiagramView
from ..model.scenario import Scenario
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from .tables import ObjectTable, EventTable
from .help_view import HelpView

class _TitledPanel(QFrame):
    """Compact framed container with a title drawn over its top border."""

    def __init__(self, title, widget, position="top-left", parent=None):
        """Create a titled panel containing ``widget``."""
        super().__init__(parent)
        self.title_position = position
        self.setStyleSheet(
            "QFrame { border: 1px solid #707070; border-radius: 2px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(widget)
        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(
            "QLabel { background: white; color: black; padding: 0 4px; }"
        )
        self.title_label.adjustSize()
        self._position_title()
        self.title_label.raise_()

    def _position_title(self):
        """Place the title at its configured corner of the frame."""
        x = 8 if self.title_position.endswith("left") else self.width() - self.title_label.width() - 8
        y = 0 if self.title_position.startswith("top") else self.height() - self.title_label.height()
        self.title_label.move(max(8, x), max(0, y))

    def resizeEvent(self, event):
        """Keep the overlaid title aligned after the panel is resized."""
        super().resizeEvent(event)
        self._position_title()

class MainWindow(QMainWindow):
    """Coordinate the editor views, controls, and scenario persistence."""

    def __init__(self, scenario, parent=None, path=None):
        """Build the window around a scenario."""
        super().__init__(parent); self.scenario=scenario; self.history=History()
        self.path=Path(path) if path else None; self.dirty=False
        self.setWindowTitle("Spacetime"); self.resize(1100,700)
        root=QWidget(); layout=QVBoxLayout(root)
        self.time_control=QDoubleSpinBox()
        self.time_control.setRange(-1e6,1e6)
        self.time_control.setDecimals(6)
        self.time_control.setSingleStep(0.1)
        self.time_control.setValue(scenario.time)
        self.time_control.setPrefix("t = ")
        self.time_control.valueChanged.connect(self._time_changed)
        navigation = QHBoxLayout()
        navigation.addWidget(self.time_control)
        left = QPushButton("←")
        left.setToolTip("Move Highway view left")
        left.clicked.connect(lambda: self.highway.pan_horizontal(80))
        right = QPushButton("→")
        right.setToolTip("Move Highway view right")
        right.clicked.connect(lambda: self.highway.pan_horizontal(-80))
        navigation.addWidget(left)
        navigation.addWidget(right)
        layout.addLayout(navigation)
        split=QSplitter(Qt.Vertical); self.highway=HighwayView(scenario); self.diagram=SpacetimeDiagramView(scenario)
        self.highway.history = self.history
        self.diagram.history = self.history
        self.diagram.center_current_time()
        self._syncing_horizontal_view = False
        self.highway.horizontal_view_changed.connect(
            lambda scale, offset: self._sync_horizontal_view(self.highway, scale, offset)
        )
        self.diagram.horizontal_view_changed.connect(
            lambda scale, offset: self._sync_horizontal_view(self.diagram, scale, offset)
        )
        self.highway.changed.connect(self.mark_dirty); self.diagram.changed.connect(self.mark_dirty)
        self.diagram.instruction_changed.connect(self.statusBar().showMessage)
        highway_panel = _TitledPanel("Highway", self.highway, "bottom-right")
        diagram_panel = _TitledPanel("Spacetime diagram", self.diagram, "top-left")
        split.addWidget(highway_panel)
        split.addWidget(diagram_panel)
        layout.addWidget(split)
        self.setCentralWidget(root)
        self.object_table = ObjectTable(scenario)
        self.event_table = EventTable(scenario)
        self.object_table.history = self.history
        self.object_table.changed.connect(self.mark_dirty)
        self.event_table.changed.connect(self.mark_dirty)
        tabs=QTabWidget(); tabs.addTab(self.object_table, "Objects"); tabs.addTab(self.event_table, "Events");         self.comments=QTextEdit(); self.comments.setPlainText(scenario.comments); self.comments.textChanged.connect(self.mark_dirty)
        tabs.addTab(self.comments, "Comments")
        self.help_view = HelpView()
        tabs.addTab(self.help_view, "Help")
        self.tabs = tabs
        self.table_dock=QDockWidget("Tables", self); self.table_dock.setWidget(tabs); self.addDockWidget(Qt.RightDockWidgetArea, self.table_dock)
        self._add_actions()
        self._update_title()
    def _add_actions(self):
        """Create menus and connect their actions."""
        menu=self.menuBar().addMenu("&Scenario")
        new=menu.addAction("&New"); new.setShortcut("Ctrl+N"); new.triggered.connect(self.new_scenario)
        open_action=menu.addAction("&Open…"); open_action.setShortcut("Ctrl+R"); open_action.triggered.connect(self.open_scenario)
        save=menu.addAction("&Save"); save.setShortcut("Ctrl+S"); save.triggered.connect(self.save)
        save_as=menu.addAction("Save &As…"); save_as.triggered.connect(self.save_as)
        menu.addSeparator()
        undo=menu.addAction("&Undo"); undo.setShortcut(QKeySequence.StandardKey.Undo); undo.triggered.connect(self.undo)
        redo=menu.addAction("&Redo"); redo.setShortcut(QKeySequence.StandardKey.Redo); redo.triggered.connect(self.redo)
        menu.addSeparator()
        quit_action=menu.addAction("&Quit"); quit_action.setShortcut("Ctrl+Q"); quit_action.triggered.connect(self.close)
        advance=menu.addAction("Advance time"); advance.setShortcut("Up"); advance.triggered.connect(lambda: self._step_time(1, 0.1))
        rewind=menu.addAction("Rewind time"); rewind.setShortcut("Down"); rewind.triggered.connect(lambda: self._step_time(-1, 0.1))
        advance_fast = QAction(self)
        advance_fast.setShortcuts(["Ctrl+Up", "Meta+Up"])
        advance_fast.triggered.connect(lambda: self._step_time(1, 1.0))
        self.addAction(advance_fast)
        rewind_fast = QAction(self)
        rewind_fast.setShortcuts(["Ctrl+Down", "Meta+Down"])
        rewind_fast.triggered.connect(lambda: self._step_time(-1, 1.0))
        self.addAction(rewind_fast)

        objects = self.menuBar().addMenu("&Objects")
        add_clock = objects.addAction("Create clock")
        add_clock.triggered.connect(self.create_clock)
        add_flash = objects.addAction("Create light flash")
        add_flash.triggered.connect(self.create_flash)
        add_event = self.menuBar().addMenu("&Events").addAction("Create event")
        add_event.triggered.connect(self.create_event)

        frames = self.menuBar().addMenu("&Reference frame")
        set_frame = frames.addAction("Set beta...")
        set_frame.triggered.connect(self.set_frame)
        frame_up = frames.addAction("Transform up")
        frame_up.setShortcut("Shift+Up")
        frame_up.triggered.connect(lambda: self.change_frame(0.1))
        frame_down = frames.addAction("Transform down")
        frame_down.setShortcut("Shift+Down")
        frame_down.triggered.connect(lambda: self.change_frame(-0.1))
        original = frames.addAction("Return to original frame")
        original.triggered.connect(lambda: self.history.do(SetFrame(self.scenario, 0.0)) or self.refresh())
        view_menu = self.menuBar().addMenu("&View")
        zoom_in = view_menu.addAction("Zoom in")
        zoom_in.setShortcut("+")
        zoom_in.triggered.connect(lambda: self.zoom(1.1))
        zoom_out = view_menu.addAction("Zoom out")
        zoom_out.setShortcut("-")
        zoom_out.triggered.connect(lambda: self.zoom(1/1.1))
        help_menu=self.menuBar().addMenu("&Help")
        help_action = help_menu.addAction("&Help")
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help)
        about=help_menu.addAction("&About"); about.triggered.connect(lambda: QMessageBox.about(self,"About Spacetime","Spacetime — special relativity scenario editor"))

    def show_help(self) -> None:
        """Select and reveal the Help tab."""
        self.tabs.setCurrentWidget(self.help_view)
        self.table_dock.raise_()

    def _step_time(self, direction: int, step: float) -> None:
        """Advance or rewind time using the requested step size."""
        self.history.do(
            SetTime(
                self.scenario,
                self.scenario.stepped_time(direction, step=step),
            )
        )
        self.refresh()

    def _number(self, title: str, label: str, value: float = 0.0) -> float | None:
        """Prompt for a bounded floating-point value."""
        number, accepted = QInputDialog.getDouble(self, title, label, value, -1e6, 1e6, 6)
        return number if accepted else None

    def create_clock(self) -> None:
        """Prompt for and create a clock."""
        x = self._number("Create clock", "Position x:", 0.0)
        if x is None:
            return
        beta = self._number("Create clock", "Velocity beta (-1 < beta < 1):", 0.0)
        if beta is None:
            return
        try:
            obj = self.scenario.add_clock_in_frame(x, self.scenario.time, beta)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot create clock", str(exc))
            return
        self.history.do(AddObject(self.scenario, obj))
        self.refresh()

    def create_flash(self) -> None:
        """Prompt for and create a light flash."""
        x = self._number("Create light flash", "Position x:", 0.0)
        if x is None:
            return
        direction, accepted = QInputDialog.getItem(
            self, "Create light flash", "Direction:", ["Right (+1)", "Left (-1)"], 0, False
        )
        if not accepted:
            return
        obj = self.scenario.add_flash_in_frame(x, self.scenario.time, 1 if direction.startswith("Right") else -1)
        self.history.do(AddObject(self.scenario, obj))
        self.refresh()

    def create_event(self) -> None:
        """Prompt for and create an event."""
        x = self._number("Create event", "Position x:", 0.0)
        if x is None:
            return
        event = self.scenario.add_event(x=x, t=self.scenario.time)
        self.history.do(AddEvent(self.scenario, event))
        self.refresh()

    def set_frame(self) -> None:
        """Prompt for and set the reference frame."""
        beta = self._number("Reference frame", "Frame velocity beta (-1 < beta < 1):", self.scenario.beta_rel)
        if beta is None:
            return
        try:
            self.history.do(SetFrame(self.scenario, beta))
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot change reference frame", str(exc))
            return
        self.refresh()

    def change_frame(self, delta: float) -> None:
        """Adjust the reference frame by a relativistic delta."""
        beta = self.scenario.beta_rel
        try:
            value = (beta + delta) / (1.0 + beta * delta)
            self.history.do(SetFrame(self.scenario, value))
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot change reference frame", str(exc))
            return
        self.refresh()

    def refresh(self):
        """Refresh all controls and views from the scenario."""
        self.time_control.blockSignals(True)
        self.time_control.setValue(self.scenario.time)
        self.time_control.blockSignals(False)
        self.diagram.center_current_time()
        self.highway.update()
        self.diagram.update()
        self.object_table.refresh()
        self.event_table.refresh()
        self._update_title()

    def _time_changed(self, value: float) -> None:
        """Record a change to the displayed time."""
        self.history.do(SetTime(self.scenario, value))
        self.refresh()
    def mark_dirty(self):
        """Mark the scenario modified and refresh dependent widgets."""
        self.scenario.comments=self.comments.toPlainText()
        self.dirty=True; self.refresh()
    def _update_title(self):
        """Update the window title with the current path and dirty state."""
        self.setWindowTitle(("* " if self.dirty else "") + (self.path.name if self.path else "Spacetime"))
    def undo(self):
        """Undo the latest edit and refresh the window."""
        self.history.undo(); self.dirty=True; self.refresh()
    def redo(self):
        """Redo the latest undone edit and refresh the window."""
        self.history.redo(); self.dirty=True; self.refresh()
    def new_scenario(self):
        """Create a new empty scenario after handling unsaved changes."""
        if not self.maybe_save(): return
        self._set_scenario(Scenario()); self.path=None; self.dirty=False; self.refresh()
    def open_scenario(self):
        """Open a scenario selected through the file dialog."""
        if not self.maybe_save(): return
        path,_=QFileDialog.getOpenFileName(self,"Open scenario","","Scenario files (*.sce);;All files (*)")
        if path:
            try: self._set_scenario(load_scenario(path)); self.path=Path(path); self.history=History(); self.dirty=False; self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Open failed",str(exc))
    def save(self):
        """Save the current scenario to its associated path."""
        if not self.path: return self.save_as()
        self.scenario.comments=self.comments.toPlainText(); save_scenario(self.scenario,self.path); self.dirty=False; self._update_title()
    def save_as(self):
        """Choose a path and save the current scenario."""
        path,_=QFileDialog.getSaveFileName(self,"Save scenario","","Scenario files (*.sce)")
        if path: self.path=Path(path); self.save()
    def maybe_save(self):
        """Prompt to save dirty changes before replacing or closing."""
        if not self.dirty: return True
        answer=QMessageBox.question(self,"Unsaved changes","Save changes?",QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Save: self.save(); return not self.dirty
        return answer==QMessageBox.StandardButton.Discard
    def closeEvent(self,event):
        """Accept or reject window closing based on unsaved changes."""
        if self.maybe_save(): event.accept()
        else: event.ignore()
    def _set_scenario(self, scenario):
        """Bind all editor widgets to a replacement scenario."""
        self.scenario=scenario
        for view in (self.highway, self.diagram): view.scenario=scenario
        self.object_table.scenario=scenario; self.object_table.history=self.history
        self.event_table.scenario=scenario
        self.comments.blockSignals(True); self.comments.setPlainText(scenario.comments); self.comments.blockSignals(False)
    def zoom(self, factor):
        """Zoom both synchronized views by a scale factor."""
        scale = max(5, min(500, self.highway.scale * factor))
        self.highway.scale = scale
        self.diagram.scale = scale
        self.diagram.center_current_time()
        self.highway.update()
        self.diagram.update()

    def _sync_horizontal_view(self, source, scale: float, offset_x: float) -> None:
        """Synchronize horizontal view state between the two canvases."""
        if self._syncing_horizontal_view:
            return
        self._syncing_horizontal_view = True
        target = self.diagram if source is self.highway else self.highway
        target.scale = scale
        target.offset = (offset_x, target.offset[1])
        if target is self.diagram:
            target.center_current_time()
        target.update()
        self._syncing_horizontal_view = False
