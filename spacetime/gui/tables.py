"""Qt table widgets for editing scenario objects and events."""

from __future__ import annotations
import math
from PySide6.QtWidgets import QHeaderView, QMenu, QTableWidget, QTableWidgetItem, QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from ..commands.undo_redo import DeleteEvent, DeleteObject, ProgramObject, Snapshot
from ..model.lorentz import _check_beta, inverse_transform

class ObjectTable(QTableWidget):
    """Table showing and editing scenario objects."""

    changed = Signal()
    jump_requested = Signal(object)
    _read_only_color = QColor(232, 232, 232)

    @staticmethod
    def _format_gamma(value: float) -> str:
        """Format a Lorentz factor for display."""
        return "∞" if math.isinf(value) else f"{value:.4f}"

    def __init__(self, scenario, parent=None):
        """Create a table bound to a scenario."""
        super().__init__(0, 6, parent); self.scenario=scenario
        self.history = None
        self._updating = False
        font = self.font()
        font.setPointSizeF(max(1.0, font.pointSizeF() * 0.9))
        self.setFont(font)
        headers = ["Object", "x", "β", "γ", "reading", "notes"]
        self.setHorizontalHeaderLabels(headers)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for column, width in enumerate((100, 50, 65, 65, 100, 250)):
            self.setColumnWidth(column, width)
        self.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked|QTableWidget.EditTrigger.SelectedClicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemChanged.connect(self._edited)
        self.refresh()

    def _context_menu(self, position) -> None:
        """Show actions for the object under the pointer."""
        item = self.itemAt(position)
        if item is None:
            return
        obj = self.scenario.objects[item.row()]
        menu = QMenu(self)
        object_type = "Clock" if obj.kind == "clock" else "Light flash"
        title = menu.addAction(f"{object_type} {obj.label}")
        title.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._delete_object(obj))
        if obj.kind == "clock":
            menu.addAction("Jump to object", lambda: self.jump_requested.emit(obj))
        if obj.worldline.has_birth:
            menu.addAction("Cancel birth", lambda: self._cancel_birth(obj))
        else:
            menu.addAction("Set birth here && now", lambda: self._set_birth(obj))
        if obj.worldline.has_termination:
            menu.addAction("Cancel termination", lambda: self._cancel_termination(obj))
        else:
            menu.addAction("Set termination here && now", lambda: self._set_termination(obj))
        menu.addAction("Program", lambda: self._program(obj))
        menu.exec(self.viewport().mapToGlobal(position))

    def _delete_object(self, obj) -> None:
        """Delete an object and record the change when possible."""
        if self.history is None:
            self.scenario.remove_object(obj)
        else:
            self.history.do(DeleteObject(self.scenario, obj))
        self.changed.emit()

    def _set_birth(self, obj) -> None:
        """Set an object's birth point at the current time."""
        mutation = lambda: self.scenario.set_birth_here_now(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()

    def _set_termination(self, obj) -> None:
        """Set an object's termination point at the current time."""
        mutation = lambda: self.scenario.set_termination_here_now(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()

    def _cancel_birth(self, obj) -> None:
        """Cancel an object's existing birth constraint."""
        mutation = lambda: self.scenario.cancel_birth(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()

    def _cancel_termination(self, obj) -> None:
        """Cancel an object's existing termination constraint."""
        mutation = lambda: self.scenario.cancel_termination(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()

    def _program(self, obj) -> None:
        """Program an object for subsequent velocity changes."""
        if self.history is None:
            self.scenario.program_object(obj)
        else:
            self.history.do(ProgramObject(self.scenario, obj))
        self.changed.emit()
    def refresh(self):
        """Refresh displayed values from the scenario."""
        self.setRowCount(len(self.scenario.objects))
        t=self.scenario.time
        self._updating = True
        for row,obj in enumerate(self.scenario.objects):
            position, beta = self.scenario.object_state(obj, t)
            gamma_value = 1/(1-beta*beta)**.5 if abs(beta) < 1 else float("inf")
            _, original_time = inverse_transform(position, t, self.scenario.beta_rel)
            exists = obj.exists(original_time)
            clock_value = f"Time = {obj.clock_reading(original_time):.2f}" if obj.kind == "clock" else ""
            values = (
                obj.label,
                f"{position:.2f}" if exists else "---",
                f"{beta:.4f}" if exists else "---",
                self._format_gamma(gamma_value) if exists else "---",
                clock_value if exists else "---",
                obj.note,
            )
            for col,val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 4:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(self._read_only_color)
                self.setItem(row,col,item)
        self._updating = False
    def _edited(self,item):
        """Apply an edited table cell to the model."""
        if self._updating or not 0 <= item.row() < len(self.scenario.objects): return
        obj=self.scenario.objects[item.row()]
        try:
            if item.column()==0:
                obj.label = item.text()
                self.scenario.relabel_beta_change_events(obj)
            elif item.column() in (1,2,3):
                position, beta = self.scenario.object_state(obj, self.scenario.time)
                if item.column()==1: position=float(item.text())
                elif item.column()==2: beta=float(item.text())
                else:
                    gamma_value=float(item.text())
                    if not math.isfinite(gamma_value) or gamma_value < 1:
                        raise ValueError("gamma must be finite and at least 1")
                    beta=math.copysign(math.sqrt(1 - 1/(gamma_value*gamma_value)), beta)
                _check_beta(beta, allow_light=obj.kind == "flash")
                if obj.programmed and item.column() in (2, 3):
                    self.scenario.add_programmed_change(obj, self.scenario.time, position, beta)
                    obj.programmed = False
                else:
                    self.scenario.set_object_state(obj, self.scenario.time, position, beta)
            elif item.column() == 5:
                obj.note = item.text()
            else:
                return
        except (TypeError, ValueError) as exc:
            self._updating=True
            self.refresh()
            self._updating=False
            QMessageBox.warning(self, "Invalid object value", str(exc))
            return
        self.changed.emit()

class EventTable(QTableWidget):
    """Table showing and editing scenario events."""

    changed = Signal()
    interval_requested = Signal(object)
    _read_only_color = QColor(232, 232, 232)
    def __init__(self, scenario, parent=None):
        """Create a table bound to a scenario."""
        super().__init__(0, 4, parent); self.scenario=scenario
        self.history = None
        self._updating = False
        self.setHorizontalHeaderLabels(["Event", "x", "t", "Note"]); self.itemChanged.connect(self._edited)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for column, width in enumerate((100, 65, 65)):
            self.setColumnWidth(column, width)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.refresh()
        self.resizeColumnToContents(3)
    def refresh(self):
        """Refresh displayed event values from the scenario."""
        self.setRowCount(len(self.scenario.events))
        self._updating = True
        for row,event in enumerate(self.scenario.events):
            for col,val in enumerate((event.label,f"{event.x:.2f}",f"{event.t:.2f}",event.note)):
                item = QTableWidgetItem(val)
                if col in (1, 2) and (
                    event.fixed_at_intersection or event.placed_at_worldline
                ):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setBackground(self._read_only_color)
                self.setItem(row,col,item)
        self.resizeColumnToContents(3)
        self._updating = False

    def _context_menu(self, position) -> None:
        """Show the same construction and deletion actions as the diagram."""
        item = self.itemAt(position)
        if item is None:
            return
        event = self.scenario.events[item.row()]
        menu = QMenu(self)
        title = menu.addAction(f"Event {event.label}")
        title.setEnabled(False)
        menu.addSeparator()
        construct_menu = menu.addMenu("Construct")
        construct_menu.addAction(
            "Light cone",
            lambda: self._add_decoration("lightcone", event),
        )
        construct_menu.addAction(
            "Invariant hyperbola",
            lambda: self._add_decoration("hyperbola", event),
        )
        construct_menu.addAction(
            "Spacetime interval to . . .",
            lambda: self.interval_requested.emit(event),
        )
        menu.addAction("Delete", lambda: self._delete_event(event))
        menu.exec(self.viewport().mapToGlobal(position))

    def _add_decoration(self, kind: str, event) -> None:
        """Add a light cone or invariant hyperbola around an event."""
        if kind == "lightcone":
            mutation = lambda: self.scenario.add_light_cone(event)
        else:
            mutation = lambda: self.scenario.add_hyperbola(event)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()

    def _delete_event(self, event) -> None:
        """Delete an event and its dependent decorations."""
        if self.history is None:
            self.scenario.remove_event(event)
        else:
            self.history.do(DeleteEvent(self.scenario, event))
        self.changed.emit()

    def _edited(self,item):
        """Apply an edited event cell to the model."""
        if self._updating or not 0 <= item.row() < len(self.scenario.events): return
        event=self.scenario.events[item.row()]
        try:
            if item.column()==0: event.label=item.text()
            elif item.column()==1: event.x=float(item.text())
            elif item.column()==2: event.t=float(item.text())
            elif item.column()==3: event.note=item.text()
            else: return
        except ValueError as exc:
            self._updating=True
            self.refresh()
            self._updating=False
            QMessageBox.warning(self, "Invalid event value", str(exc))
            return
        self.changed.emit()
