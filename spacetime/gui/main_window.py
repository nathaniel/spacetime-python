"""Main Qt window for the Spacetime scenario editor."""

from __future__ import annotations
from copy import deepcopy
from ..commands.undo_redo import AddEvent, AddObject, DeleteEvent, DeleteObject, History, SetFrame, SetTime, Snapshot
from ..persistence.scenario_file import load_scenario, save_scenario
from pathlib import Path
import sys
from .views import HighwayView, SpacetimeDiagramView
from ..model.scenario import Scenario
from ..model.lorentz import transform
from PySide6.QtWidgets import (
    QDockWidget,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QApplication,
    QCheckBox,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QTextEdit,
)
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from .tables import ObjectTable, EventTable
from .help_view import HelpView, ShortcutsView

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

class _StatusPanel(QWidget):
    """Java-style bottom status area with prioritized hover details."""

    def __init__(self, parent=None):
        """Create the time and detail labels."""
        super().__init__(parent)
        self.time_label = QLabel(self)
        self.detail_label = QLabel(self)
        self.time_label.setFixedWidth(105)
        self.detail_label.hide()

    def set_time(self, text: str) -> None:
        """Set the fixed-width time display."""
        self.time_label.setText(text)

    def set_detail(self, text: str) -> None:
        """Set or clear the prioritized hover detail."""
        self.detail_label.setText(text)
        self.detail_label.setVisible(bool(text))
        if text:
            self.detail_label.raise_()

    def resizeEvent(self, event):
        """Keep the time and detail labels positioned."""
        super().resizeEvent(event)
        height = self.height()
        self.time_label.setGeometry(0, 0, 105, height)
        self.detail_label.setGeometry(105, 0, max(0, self.width() - 105), height)

class _PreferencesDialog(QDialog):
    """Edit persistent application preferences."""

    def __init__(self, parent, font_size: int, trackpad: float, wheel: float):
        """Build the preferences form with the current values."""
        super().__init__(parent)
        self.setWindowTitle(
            "Spacetime Preferences" if sys.platform == "darwin" else "Settings"
        )
        # Keep the form geometry stable while the application font is previewed.
        self.setFont(QApplication.instance().font())
        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 32)
        self.font_size.setValue(font_size)
        self.trackpad = QSpinBox()
        self.trackpad.setRange(10, 500)
        self.trackpad.setSingleStep(10)
        self.trackpad.setSuffix("%")
        self.trackpad.setValue(round(trackpad * 100))
        self.wheel = QSpinBox()
        self.wheel.setRange(10, 500)
        self.wheel.setSingleStep(10)
        self.wheel.setSuffix("%")
        self.wheel.setValue(round(wheel * 100))
        layout.addRow("Application font size:", self.font_size)
        layout.addRow("Trackpad / pixel-scroll sensitivity (10–500%):", self.trackpad)
        layout.addRow("Mouse-wheel sensitivity (10–500%):", self.wheel)
        for field in (self.font_size, self.trackpad, self.wheel):
            layout.setAlignment(field, Qt.AlignmentFlag.AlignRight)
        note = QLabel(
            "Note: Some devices may combine or interpret trackpad and mouse-wheel input differently."
        )
        note.setWordWrap(True)
        layout.addRow(note)
        self.reset_defaults = QPushButton("Reset to Defaults")
        self.reset_defaults.clicked.connect(self._reset_defaults)
        layout.addRow(self.reset_defaults)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.rejected.connect(self.reject)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        layout.addRow(buttons)

    def _reset_defaults(self) -> None:
        """Restore the built-in preference defaults in the form."""
        self.font_size.setValue(12)
        self.trackpad.setValue(100)
        self.wheel.setValue(100)

class _GettingStartedDialog(QDialog):
    """Give first-time users a brief overview of the main controls."""

    def __init__(self, parent=None):
        """Build the first-launch introduction."""
        super().__init__(parent)
        self.setWindowTitle("Getting Started with Spacetime")
        layout = QVBoxLayout(self)
        message = QLabel(
            "<p>Welcome to the Spacetime special-relativity explorer!</p>"
            "<p>A clock has been placed here to show you how the two views work "
            "together. The <b>Highway</b> shows where it is now; the "
            "<b>Spacetime Diagram</b> shows its path through time.</p>"
            "<p><b>Up / Down</b>: advance or rewind time<br>"
            "<b>Shift + Up / Down</b>: change the reference frame<br>"
            "<b>Left / Right</b>: move the view<br>"
            "<b>+ / -</b>: zoom<br>"
            "<b>Right-click</b>: create objects, events, and decorations</p>"
            "<p>Objects and events can also be edited in the <b>Tables</b> panel. "
            "Use <b>Help</b> for the detailed <b>Tutorial</b> and complete "
            "<b>Shortcuts &amp; Gestures</b> reference.</p>"
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        self.dont_show_again = QCheckBox("Don't show this again")
        layout.addWidget(self.dont_show_again)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.open_help = QPushButton("Open Getting Started")
        buttons.addButton(self.open_help, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.rejected.connect(self.reject)
        self.open_help.clicked.connect(self.accept)
        layout.addWidget(buttons)

class MainWindow(QMainWindow):
    """Coordinate the editor views, controls, and scenario persistence."""

    def __init__(self, scenario, parent=None, path=None):
        """Build the window around a scenario."""
        super().__init__(parent); self.scenario=scenario; self.history=History()
        self.path=Path(path) if path else None; self.dirty=False
        self.settings = QSettings("Spacetime", "Spacetime")
        self._trackpad_sensitivity = self._read_setting("trackpadSensitivity", 1.0)
        self._mouse_wheel_sensitivity = self._read_setting("mouseWheelSensitivity", 1.0)
        self._saved_scenario = deepcopy(scenario)
        self.setWindowTitle("Spacetime"); self.resize(1100,700)
        self._instruction = ""
        self._hovered_item = None
        self._modifier_name = "Cmd" if sys.platform == "darwin" else "Ctrl"
        root=QWidget(); layout=QVBoxLayout(root)
        split=QSplitter(Qt.Vertical); self.highway=HighwayView(scenario); self.diagram=SpacetimeDiagramView(scenario)
        self.highway.history = self.history
        self.diagram.history = self.history
        self._apply_scroll_preferences()
        self.diagram.center_current_time()
        self._syncing_horizontal_view = False
        self.highway.horizontal_view_changed.connect(
            lambda scale, offset: self._sync_horizontal_view(self.highway, scale, offset)
        )
        self.diagram.horizontal_view_changed.connect(
            lambda scale, offset: self._sync_horizontal_view(self.diagram, scale, offset)
        )
        self.highway.changed.connect(self.mark_dirty); self.diagram.changed.connect(self.mark_dirty)
        self.highway.hover_changed.connect(lambda item: self._show_hover_detail(item))
        self.diagram.hover_changed.connect(lambda item: self._show_hover_detail(item))
        self.diagram.instruction_changed.connect(self._set_instruction)
        self.highway_panel = _TitledPanel("Highway", self.highway, "top-right")
        self.diagram_panel = _TitledPanel("Spacetime Diagram", self.diagram, "top-left")
        split.addWidget(self.highway_panel)
        split.addWidget(self.diagram_panel)
        layout.addWidget(split)
        self.setCentralWidget(root)
        self.status_panel = _StatusPanel()
        self.statusBar().addWidget(self.status_panel, 1)
        self._update_status()
        self.object_table = ObjectTable(scenario)
        self.event_table = EventTable(scenario)
        self.object_table.history = self.history
        self.event_table.history = self.history
        self.object_table.jump_requested.connect(self.highway._jump_to_object)
        self.event_table.interval_requested.connect(self.diagram._start_interval)
        self.object_table.changed.connect(self.mark_dirty)
        self.event_table.changed.connect(self.mark_dirty)
        tabs=QTabWidget(); tabs.addTab(self.object_table, "Objects"); tabs.addTab(self.event_table, "Events");         self.comments=QTextEdit(); self.comments.setPlainText(scenario.comments); self.comments.textChanged.connect(self.mark_dirty)
        tabs.addTab(self.comments, "Scenario")
        self.help_view = HelpView()
        self.shortcuts_view = ShortcutsView()
        tabs.addTab(self.shortcuts_view, "Shortcuts")
        self.tabs = tabs
        self.table_dock=QDockWidget("Tables", self); self.table_dock.setWidget(tabs); self.addDockWidget(Qt.RightDockWidgetArea, self.table_dock)
        self.help_dock = QDockWidget("Help", self)
        self.help_dock.setWidget(self.help_view)
        self.help_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.addDockWidget(Qt.RightDockWidgetArea, self.help_dock)
        self.help_dock.hide()
        self._add_actions()
        self._apply_font_size(self._read_font_size())
        self._update_title()
        QTimer.singleShot(0, self._apply_scenario_horizontal_view)
        QTimer.singleShot(0, self._show_getting_started_if_needed)

    def _read_setting(self, key: str, default: float) -> float:
        """Read a bounded positive numeric preference."""
        try:
            value = float(self.settings.value(key, default))
        except (TypeError, ValueError):
            return default
        return value if value > 0 else default

    def _read_font_size(self) -> int:
        """Read the persisted application font size."""
        try:
            value = int(self.settings.value("fontSize", QApplication.instance().font().pointSize()))
        except (TypeError, ValueError):
            return QApplication.instance().font().pointSize()
        return max(6, min(32, value))

    def _apply_scroll_preferences(self) -> None:
        """Apply persisted scroll sensitivities to both diagram views."""
        for view in (self.highway, self.diagram):
            view.trackpad_sensitivity = self._trackpad_sensitivity
            view.mouse_wheel_sensitivity = self._mouse_wheel_sensitivity

    def _apply_font_size(self, point_size: int, persist: bool = True) -> None:
        """Apply an application-wide font size, optionally persisting it."""
        app = QApplication.instance()
        if app is None:
            return
        font = app.font()
        font.setPointSize(point_size)
        app.setFont(font)
        for widget in (
            self.highway,
            self.diagram,
            self.object_table,
            self.event_table,
            self.help_view,
            self.shortcuts_view,
        ):
            widget.setFont(font)
        for panel in (self.highway_panel, self.diagram_panel):
            panel.title_label.setFont(font)
            panel.title_label.adjustSize()
            panel._position_title()
        self.object_table.resizeRowsToContents()
        self.event_table.resizeRowsToContents()
        if persist:
            self.settings.setValue("fontSize", point_size)
        self.highway.update()
        self.diagram.update()
    def _add_actions(self):
        """Create menus and connect their actions."""
        menu=self.menuBar().addMenu("&Scenario")
        new=menu.addAction("&New"); new.setShortcut("Ctrl+N"); new.triggered.connect(self.new_scenario)
        open_action=menu.addAction("&Open…"); open_action.setShortcut("Ctrl+R"); open_action.triggered.connect(self.open_scenario)
        save=menu.addAction("&Save"); save.setShortcut("Ctrl+S"); save.triggered.connect(self.save)
        save_as=menu.addAction("Save &As…"); save_as.triggered.connect(self.save_as)
        menu.addSeparator()
        quit_action=menu.addAction("&Quit"); quit_action.setShortcut("Ctrl+Q"); quit_action.triggered.connect(self.close)
        advance_fast = QAction(self)
        advance_fast.setShortcuts(["Ctrl+Up", "Meta+Up"])
        advance_fast.triggered.connect(lambda: self._step_time(1, 1.0))
        self.addAction(advance_fast)
        rewind_fast = QAction(self)
        rewind_fast.setShortcuts(["Ctrl+Down", "Meta+Down"])
        rewind_fast.triggered.connect(lambda: self._step_time(-1, 1.0))
        self.addAction(rewind_fast)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction("&Undo", self.undo).setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction("&Redo", self.redo).setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addSeparator()
        add_event = edit_menu.addAction("Create Event")
        add_event.triggered.connect(self.create_event)
        add_clock = edit_menu.addAction("Create Clock")
        add_clock.triggered.connect(self.create_clock)
        add_flash = edit_menu.addAction("Create Light Flash")
        add_flash.triggered.connect(self.create_flash)
        preferences = QAction(
            "Preferences..." if sys.platform == "darwin" else "Settings...",
            self,
        )
        preferences.setMenuRole(QAction.MenuRole.PreferencesRole)
        preferences.triggered.connect(self.show_preferences)
        if sys.platform == "darwin":
            menu.addAction(preferences)
        else:
            edit_menu.addSeparator()
            edit_menu.addAction(preferences)

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
        original.setShortcut("Shift+0")
        original.triggered.connect(lambda: self.history.do(SetFrame(self.scenario, 0.0)) or self.refresh())
        coordinates = self.menuBar().addMenu("&Coordinates")
        advance=coordinates.addAction(
            f"Advance time ({self._modifier_name} = 10×)"
        )
        advance.setShortcut("Up")
        advance.triggered.connect(lambda: self._step_time(1, 0.1))
        rewind=coordinates.addAction(
            f"Rewind time ({self._modifier_name} = 10×)"
        )
        rewind.setShortcut("Down")
        rewind.triggered.connect(lambda: self._step_time(-1, 0.1))
        set_time = coordinates.addAction("Set time...")
        set_time.triggered.connect(self.set_time)
        zero_time = coordinates.addAction("Set time to zero")
        zero_time.setShortcut("Ctrl+0")
        zero_time.triggered.connect(self._set_time_zero)
        coordinates.addSeparator()
        center_x = coordinates.addAction("Center on x...")
        center_x.triggered.connect(self.center_on_x)
        view_menu = self.menuBar().addMenu("&View")
        zoom_in = view_menu.addAction("Zoom in")
        zoom_in.setShortcut("+")
        zoom_in.triggered.connect(lambda: self.zoom(1.1))
        zoom_out = view_menu.addAction("Zoom out")
        zoom_out.setShortcut("-")
        zoom_out.triggered.connect(lambda: self.zoom(1/1.1))
        move_left = view_menu.addAction(f"Move left ({self._modifier_name} = 10×)")
        move_left.setShortcut("Left")
        move_left.triggered.connect(lambda: self._move_view(20))
        move_right = view_menu.addAction(f"Move right ({self._modifier_name} = 10×)")
        move_right.setShortcut("Right")
        move_right.triggered.connect(lambda: self._move_view(-20))
        help_menu=self.menuBar().addMenu("&Help")
        help_action = help_menu.addAction("&Help Contents")
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help)
        help_menu.addSeparator()
        getting_started = help_menu.addAction("Getting Started")
        getting_started.triggered.connect(lambda: self.show_help("getting_started"))
        tutorial = help_menu.addAction("Tutorial")
        tutorial.triggered.connect(lambda: self.show_help("tutorial"))
        shortcuts = help_menu.addAction("Shortcuts && Gestures")
        shortcuts.triggered.connect(self.show_shortcuts)
        about=help_menu.addAction("&About"); about.triggered.connect(lambda: QMessageBox.about(self,"About Spacetime","Spacetime — special relativity scenario editor"))

    def increase_font_size(self) -> None:
        """Increase the application-wide Qt font size by one point."""
        self._change_font_size(1)

    def decrease_font_size(self) -> None:
        """Decrease the application-wide Qt font size by one point."""
        self._change_font_size(-1)

    def _change_font_size(self, delta: int) -> None:
        """Adjust the application-wide Qt font size within a usable range."""
        app = QApplication.instance()
        if app is None:
            return
        self._apply_font_size(max(6, min(32, app.font().pointSize() + delta)))

    def show_preferences(self) -> None:
        """Preview, commit, or cancel persistent application preferences."""
        dialog = _PreferencesDialog(
            self,
            QApplication.instance().font().pointSize(),
            self._trackpad_sensitivity,
            self._mouse_wheel_sensitivity,
        )
        committed = (
            QApplication.instance().font().pointSize(),
            self._trackpad_sensitivity,
            self._mouse_wheel_sensitivity,
        )

        def values():
            return (
                dialog.font_size.value(),
                dialog.trackpad.value() / 100,
                dialog.wheel.value() / 100,
            )

        def preview():
            font_size, trackpad, wheel = values()
            self._trackpad_sensitivity = trackpad
            self._mouse_wheel_sensitivity = wheel
            self._apply_scroll_preferences()
            self._apply_font_size(font_size, persist=False)

        def apply():
            nonlocal committed
            preview()
            committed = values()
            font_size, trackpad, wheel = committed
            self.settings.setValue("fontSize", font_size)
            self.settings.setValue("trackpadSensitivity", trackpad)
            self.settings.setValue("mouseWheelSensitivity", wheel)
            dialog.accept()

        def cancel():
            font_size, trackpad, wheel = committed
            self._trackpad_sensitivity = trackpad
            self._mouse_wheel_sensitivity = wheel
            self._apply_scroll_preferences()
            self._apply_font_size(font_size, persist=False)

        dialog.font_size.valueChanged.connect(preview)
        dialog.trackpad.valueChanged.connect(preview)
        dialog.wheel.valueChanged.connect(preview)
        dialog.apply_button.clicked.connect(apply)
        dialog.reset_defaults.clicked.connect(preview)
        dialog.rejected.connect(cancel)
        dialog.exec()

    def show_help(self, anchor: str | None = None) -> None:
        """Reveal Help at half the height of the right dock area."""
        self.help_dock.show()
        self.help_dock.raise_()
        total_height = (
            self.table_dock.geometry().height()
            + self.help_dock.geometry().height()
        )
        half_height = max(1, total_height // 2)
        self.resizeDocks(
            [self.table_dock, self.help_dock],
            [half_height, total_height - half_height],
            Qt.Orientation.Vertical,
        )
        if anchor:
            QTimer.singleShot(0, lambda: self.help_view.show_section(anchor))

    def show_shortcuts(self) -> None:
        """Show the keyboard and pointing-device shortcut reference."""
        self.table_dock.show()
        self.table_dock.raise_()
        self.tabs.setCurrentWidget(self.shortcuts_view)

    def _show_getting_started_if_needed(self) -> None:
        """Show the first-launch introduction unless the user disabled it."""
        if not self.settings.value("showGettingStarted", True, type=bool):
            return
        dialog = _GettingStartedDialog(self)
        opened_help = dialog.exec() == QDialog.DialogCode.Accepted
        if dialog.dont_show_again.isChecked():
            self.settings.setValue("showGettingStarted", False)
        if opened_help:
            self.show_help("getting_started")

    def _step_time(self, direction: int, step: float) -> None:
        """Advance or rewind time using the requested step size."""
        self.history.do(
            SetTime(
                self.scenario,
                self.scenario.stepped_time(direction, step=step),
            )
        )
        self.refresh()

    def _move_view(self, pixels: float) -> None:
        """Move both synchronized views horizontally."""
        self.highway.pan_horizontal(pixels)

    def center_on_x(self) -> None:
        """Center both synchronized views on a chosen current-frame x."""
        x = self._number("Center on x", "Coordinate x:", 0.0)
        if x is None:
            return
        self.highway.offset = (-x * self.highway.scale, self.highway.offset[1])
        self.highway.horizontal_view_changed.emit(
            self.highway.scale,
            self.highway.offset[0],
        )
        self.highway.update()

    def set_time(self) -> None:
        """Set the current time through an undoable coordinate command."""
        time = self._number("Set time", "Time t:", self.scenario.time)
        if time is None:
            return
        self.history.do(SetTime(self.scenario, time))
        self.refresh()

    def _set_time_zero(self) -> None:
        """Set the current time to zero through an undoable command."""
        self.history.do(SetTime(self.scenario, 0.0))
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
            self,
            "Create light flash",
            "Direction:",
            ["Right (β = +1)", "Left (β = -1)"],
            0,
            False,
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
        self.dirty = self.scenario != self._saved_scenario
        self._update_status()
        if self._hovered_item is not None:
            self._show_hover_detail(self._hovered_item)
        self.diagram.center_current_time()
        self.highway.update()
        self.diagram.update()
        self.object_table.refresh()
        self.event_table.refresh()
        self._update_title()

    def _set_instruction(self, text: str) -> None:
        """Store an interaction instruction for the bottom status area."""
        self._instruction = text
        if text:
            self.status_panel.set_detail(text)
        elif self._hovered_item is not None:
            self._show_hover_detail(self._hovered_item)
        else:
            self._update_status()

    def _show_hover_detail(self, item) -> None:
        """Display Java-style information for the item under the pointer."""
        self._hovered_item = item
        if self._instruction:
            self.status_panel.set_detail(self._instruction)
            return
        if item is None:
            self.status_panel.set_detail("")
            self._update_status()
            return
        if item in self.scenario.events:
            x, time = transform(item.x, item.t, self.scenario.beta_rel)
            detail = f"{item.label}:   x = {x:.2f}    t = {time:.2f}"
        elif item in self.scenario.objects:
            x, beta = self.scenario.object_state(item, self.scenario.time)
            gamma_text = (
                "∞"
                if item.kind == "flash"
                else f"{1 / (1 - beta * beta) ** 0.5:.4f}"
            )
            detail = f"{item.label}:   x = {x:.2f}    β = {beta:.4f}    γ = {gamma_text}"
        else:
            detail = ""
        if item.note:
            detail += f";   {item.note}"
        self.status_panel.set_detail(detail)

    def _update_status(self) -> None:
        """Refresh the bottom time and interaction details."""
        self.status_panel.set_time(f"Time t = {self.scenario.time:.3f}")
        if self._hovered_item is None:
            self.status_panel.set_detail(self._instruction)
    def mark_dirty(self):
        """Mark the scenario modified and refresh dependent widgets."""
        self.scenario.comments=self.comments.toPlainText()
        self.dirty=True; self.refresh()
    def _update_title(self):
        """Update the window title with the current path and dirty state."""
        self.setWindowTitle(("* " if self.dirty else "") + (self.path.name if self.path else "Spacetime"))
    def undo(self):
        """Undo the latest edit and refresh the window."""
        self.history.undo(); self.refresh()
    def redo(self):
        """Redo the latest undone edit and refresh the window."""
        self.history.redo(); self.refresh()
    def new_scenario(self):
        """Create a new empty scenario after handling unsaved changes."""
        if not self.maybe_save("creating a new one"): return
        self._set_scenario(Scenario()); self._saved_scenario=deepcopy(self.scenario); self.path=None; self.dirty=False; self._apply_scenario_horizontal_view(); self.refresh()
    def open_scenario(self):
        """Open a scenario selected through the file dialog."""
        if not self.maybe_save("reading a new one"): return
        path,_=QFileDialog.getOpenFileName(self,"Open scenario","","Scenario files (*.sce);;All files (*)")
        if path:
            try: self._set_scenario(load_scenario(path)); self.path=Path(path); self.history=History(); self._saved_scenario=deepcopy(self.scenario); self.dirty=False; self._apply_scenario_horizontal_view(); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Open failed",str(exc))
    def save(self):
        """Save the current scenario to its associated path."""
        if not self.path: return self.save_as()
        self.scenario.comments=self.comments.toPlainText(); save_scenario(self.scenario,self.path); self._saved_scenario=deepcopy(self.scenario); self.dirty=False; self._update_title()
    def save_as(self):
        """Choose a path and save the current scenario."""
        path,_=QFileDialog.getSaveFileName(self,"Save scenario","","Scenario files (*.sce)")
        if path: self.path=Path(path); self.save()
    def maybe_save(self, next_action: str = "quitting"):
        """Prompt to save dirty changes before the next application action."""
        if not self.dirty: return True
        message = f"Do you want to save the current scenario\nbefore {next_action}?"
        answer=QMessageBox.question(
            self,
            "Save current scenario?",
            message,
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
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
        self.event_table.scenario=scenario; self.event_table.history=self.history
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
        width = max(1.0, source.width())
        self.scenario.view_xmin = -(width / 2.0 + offset_x) / scale
        self.scenario.view_xmax = (width / 2.0 - offset_x) / scale
        target.update()
        self._syncing_horizontal_view = False

    def _apply_scenario_horizontal_view(self) -> None:
        """Set the synchronized horizontal view from the scenario range."""
        width = max(1.0, self.highway.width())
        span = self.scenario.view_xmax - self.scenario.view_xmin
        if span <= 0:
            return
        scale = max(5.0, min(500.0, width / span))
        center = (self.scenario.view_xmin + self.scenario.view_xmax) / 2.0
        offset = -center * scale
        self.highway.scale = scale
        self.diagram.scale = scale
        self.highway.offset = (offset, self.highway.offset[1])
        self.diagram.offset = (offset, self.diagram.offset[1])
        self.diagram.center_current_time()
        self.highway.update()
        self.diagram.update()
