"""Interactive Qt views for spacetime and velocity diagrams."""

from __future__ import annotations

import math
from copy import deepcopy

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget, QMenu

from ..commands.undo_redo import AddEvent, AddObject, DeleteEvent, DeleteObject, ProgramObject, Snapshot
from ..model.lorentz import classify_interval, gamma, inverse_transform, transform, velocity_add
from ..model.scenario import MAX_OBJECT_BETA


class _View(QWidget):
    """Shared interaction and drawing helpers for diagram views."""

    changed = Signal()
    instruction_changed = Signal(str)
    hover_changed = Signal(object)
    horizontal_view_changed = Signal(float, float)
    def __init__(self, scenario, parent=None):
        """Initialize a view bound to a scenario."""
        super().__init__(parent)
        self.scenario = scenario
        self.scale = 60.0
        self.offset = (0.0, 0.0)
        self.hovered = None
        self.dragged = None
        self._drag_start = None
        self._drag_before = None
        self._drag_before_scenario = False
        self._drag_moved = False
        self._interval_first_event = None
        self.history = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(300, 180)

    @property
    def origin(self) -> QPointF:
        """Return the pixel origin including the current pan offset."""
        return QPointF(self.width() / 2 + self.offset[0], self.height() / 2 + self.offset[1])

    def _frame_state(self, obj, time: float) -> tuple[float, float]:
        """Return x and beta at a time measured in the current frame."""
        records = [record.in_frame(self.scenario.beta_rel) for record in obj.worldline.records]
        if not records:
            return 0.0, 0.0
        if time < records[0][1]:
            x, t, old, _ = records[0]
            return x + old * (time - t), old
        for previous, current in zip(records, records[1:]):
            if time < current[1]:
                x, t, _, new = previous
                return x + new * (time - t), new
        x, t, _, new = records[-1]
        return x + new * (time - t), new

    def _object_exists(self, obj, frame_time: float, frame_x: float) -> bool:
        """Check object existence for coordinates in the current frame."""
        _, original_time = inverse_transform(frame_x, frame_time, self.scenario.beta_rel)
        return obj.exists(original_time)

    def _visible_time_bounds(self, origin) -> tuple[float, float]:
        """Return a slightly overscanned time range for the diagram viewport."""
        minimum = (origin.y() - self.height()) / self.scale
        maximum = origin.y() / self.scale
        margin = 2.0 / self.scale
        return minimum - margin, maximum + margin

    def _frame_trace(self, obj, minimum: float, maximum: float, count: int = 120) -> list[QPointF]:
        """Sample an object's worldline for drawing."""
        records = [record.in_frame(self.scenario.beta_rel) for record in obj.worldline.records]
        if obj.worldline.has_birth:
            minimum = max(minimum, records[0][1])
        if obj.worldline.has_termination:
            maximum = min(maximum, records[-1][1])
        if maximum < minimum:
            return []
        step = (maximum - minimum) / max(1, count - 1)
        return [
            QPointF(
                self._frame_state(obj, frame_time)[0],
                frame_time,
            )
            for i in range(count)
            for frame_time in (minimum + i * step,)
        ]

    def _draw_clock_trace(self, painter, obj, minimum: float, maximum: float, origin) -> None:
        """Draw piecewise clock worldline segments."""
        records = [record.in_frame(self.scenario.beta_rel) for record in obj.worldline.records]
        for index, (_, record_time, old_beta, new_beta) in enumerate(records):
            start = record_time if index or obj.worldline.has_birth else minimum
            end = records[index + 1][1] if index + 1 < len(records) else maximum
            if index == len(records) - 1 and obj.worldline.has_termination:
                end = min(end, record_time)
            start = max(start, minimum)
            end = min(end, maximum)
            if end <= start:
                continue
            beta = new_beta if index or obj.worldline.has_birth else old_beta
            x_start = records[index][0] + beta * (start - record_time)
            x_end = records[index][0] + beta * (end - record_time)
            painter.drawLine(
                QPointF(origin.x() + x_start * self.scale, origin.y() - start * self.scale),
                QPointF(origin.x() + x_end * self.scale, origin.y() - end * self.scale),
            )

    def wheelEvent(self, event):
        """Handle scrolling for panning, zooming, and stepping."""
        angle_delta = event.angleDelta()
        pixel_delta = event.pixelDelta()
        horizontal = angle_delta.x() or pixel_delta.x()
        vertical = angle_delta.y() or pixel_delta.y()
        if horizontal and vertical:
            horizontal_size = abs(horizontal)
            vertical_size = abs(vertical)
            if horizontal_size < vertical_size * 1.5:
                horizontal = 0
            if vertical_size < horizontal_size * 1.5:
                vertical = 0
        if horizontal:
            if pixel_delta.x() and not angle_delta.x():
                self.pan_horizontal(-pixel_delta.x() * 0.18)
            else:
                self.pan_horizontal(-10.0 if horizontal > 0 else 10.0)
        if vertical:
            if isinstance(self, HighwayView):
                step = (
                    0.0025 * abs(pixel_delta.y())
                    if pixel_delta.y() and not angle_delta.y()
                    else 0.025
                )
                self._transform_by(step if vertical > 0 else -step)
            else:
                if pixel_delta.y() and not angle_delta.y():
                    step = 0.005 * abs(pixel_delta.y())
                    self.scenario.time += step if vertical > 0 else -step
                else:
                    self.scenario.time = self.scenario.stepped_time(
                        1 if vertical > 0 else -1,
                        step=0.05,
                    )
                self.changed.emit()
                self.update()
        event.accept()

    def event(self, event):
        """Handle native pinch gestures before normal Qt dispatch."""
        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                factor = math.exp(event.value())
                self.scale = max(5.0, min(500.0, self.scale * factor))
                self.horizontal_view_changed.emit(self.scale, self.offset[0])
                self.changed.emit()
                self.update()
                event.accept()
                return True
        return super().event(event)

    def _transform_by(self, delta: float) -> None:
        """Transform to a frame offset by a relativistic delta."""
        beta = self.scenario.beta_rel
        try:
            self.scenario.set_frame((beta + delta) / (1.0 + beta * delta))
        except ValueError:
            return
        self.changed.emit()
        self.update()

    def _transform_up(self) -> None:
        """Move to a frame with greater positive velocity."""
        beta = self.scenario.beta_rel
        self.scenario.set_frame((beta + 0.1) / (1.0 + beta * 0.1))
        self.changed.emit()
        self.update()

    def _transform_down(self) -> None:
        """Move to a frame with greater negative velocity."""
        beta = self.scenario.beta_rel
        self.scenario.set_frame((beta - 0.1) / (1.0 - beta * 0.1))
        self.changed.emit()
        self.update()

    def _original_frame(self) -> None:
        """Return to the original reference frame."""
        self.scenario.set_frame(0.0)
        self.changed.emit()
        self.update()

    def _create_event(self, point) -> None:
        """Create an event at a snapped diagram point."""
        frame_x = self._snap_tenth((point.x() - self.origin.x()) / self.scale)
        frame_t = self._snap_tenth((self.origin.y() - point.y()) / self.scale)
        x, t = inverse_transform(frame_x, frame_t, self.scenario.beta_rel)
        event = self.scenario.add_event(x, t)
        if self.history is not None:
            self.scenario.events.remove(event)
            self.history.do(AddEvent(self.scenario, event))
        self.changed.emit()
        self.update()

    def keyPressEvent(self, event):
        """Handle keyboard navigation and view controls."""
        if (
            event.key() == Qt.Key.Key_Escape
            and isinstance(self, SpacetimeDiagramView)
            and self._interval_first_event is not None
        ):
            self._interval_first_event = None
            self.instruction_changed.emit("")
            self.update()
            event.accept()
            return
        step = 0.1
        if event.key() == Qt.Key.Key_Up and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.scenario.set_frame((self.scenario.beta_rel + step) / (1 + self.scenario.beta_rel * step))
        elif event.key() == Qt.Key.Key_Down and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.scenario.set_frame((self.scenario.beta_rel - step) / (1 - self.scenario.beta_rel * step))
        elif event.key() == Qt.Key.Key_Up:
            step_size = 1.0 if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier) else 0.1
            self.scenario.time = self.scenario.stepped_time(1, step=step_size)
        elif event.key() == Qt.Key.Key_Down:
            step_size = 1.0 if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier) else 0.1
            self.scenario.time = self.scenario.stepped_time(-1, step=step_size)
        elif event.key() == Qt.Key.Key_Left:
            distance = 200 if event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            ) else 20
            self.pan_horizontal(distance)
        elif event.key() == Qt.Key.Key_Right:
            distance = 200 if event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            ) else 20
            self.pan_horizontal(-distance)
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.scale = min(500, self.scale*1.1)
            self.horizontal_view_changed.emit(self.scale, self.offset[0])
        elif event.key() == Qt.Key.Key_Minus:
            self.scale = max(5, self.scale/1.1)
            self.horizontal_view_changed.emit(self.scale, self.offset[0])
        elif event.key() == Qt.Key.Key_Shift: pass
        else: return super().keyPressEvent(event)
        self.changed.emit(); self.update()

    def mousePressEvent(self, event):
        """Begin hit testing and dragging for a mouse press."""
        self.setFocus()
        point = event.position().toPoint()
        self.hovered = self._hit(point)
        if event.button() == Qt.MouseButton.RightButton:
            self._context_menu(point); return
        if event.button() != Qt.MouseButton.LeftButton: return
        candidate = self._hit(event.position().toPoint())
        if isinstance(self, HighwayView):
            for obj in self.scenario.objects:
                if obj.programmed and obj is not candidate:
                    obj.programmed = False
                    self.changed.emit()
        if (
            isinstance(self, SpacetimeDiagramView)
            and self._interval_first_event is not None
        ):
            if candidate in self.scenario.events and candidate is not self._interval_first_event:
                self._add_interval(self._interval_first_event, candidate)
                self._interval_first_event = None
            elif candidate is None:
                self._interval_first_event = None
                self.instruction_changed.emit("")
            return
        self.dragged = candidate
        if (
            isinstance(self, SpacetimeDiagramView)
            and self.dragged in self.scenario.events
            and (
                self.dragged.fixed_at_intersection
                or self.dragged.placed_at_worldline
            )
        ):
            self.dragged = None
            return
        self._drag_before_scenario = (
            isinstance(self, HighwayView)
            and self.dragged is not None
            and self.dragged in self.scenario.objects
        )
        self._drag_before = (
            deepcopy(self.scenario)
            if self._drag_before_scenario
            else deepcopy(self.dragged)
            if self.dragged is not None
            else None
        )
        self._drag_start = event.position()
        self._drag_moved = False

    def mouseMoveEvent(self, event):
        """Update hover state and any active drag."""
        self.hovered = self._hit(event.position().toPoint())
        self.hover_changed.emit(self.hovered)
        if self.dragged is not None and self._drag_start is not None:
            self._drag_moved |= event.position() != self._drag_start
            self._drag_to(event.position(), event.modifiers())
            self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        """Finish a drag and record it in history when appropriate."""
        if self.dragged is not None:
            target = self.scenario if self._drag_before_scenario else self.dragged
            changed = (
                target.__dict__ != self._drag_before.__dict__
                if self._drag_before is not None
                else False
            )
            if (
                self.history is not None
                and self._drag_before is not None
                and (changed or (self._drag_before_scenario and self._drag_moved))
            ):
                self.history.do(
                    Snapshot(
                        target,
                        lambda: None,
                        before=self._drag_before,
                        after=deepcopy(target),
                    )
                )
            self.changed.emit()
        self.dragged = self._drag_start = self._drag_before = None
        self._drag_before_scenario = False
        self._drag_moved = False

    def leaveEvent(self, event):
        """Clear hover information when the pointer leaves the view."""
        self.hovered = None
        self.hover_changed.emit(None)
        super().leaveEvent(event)

    def _hit(self, point):
        """Return the model item nearest a screen point."""
        origin = self.origin
        if isinstance(self, HighwayView):
            for obj in self.scenario.objects:
                x, beta = self._frame_state(obj, self.scenario.time)
                if (point.x()-(origin.x()+x*self.scale))**2 + (point.y()-self._beta_to_screen(beta))**2 < 14**2: return obj
        else:
            for event in self.scenario.events:
                x,t=transform(event.x,event.t,self.scenario.beta_rel)
                if (point.x()-(origin.x()+x*self.scale))**2+(point.y()-(origin.y()-t*self.scale))**2<12**2:return event
            for obj in self.scenario.objects:
                x,_=self._frame_state(obj,self.scenario.time)
                if abs(point.x()-(origin.x()+x*self.scale))<10 and abs(point.y()-(origin.y()-self.scenario.time*self.scale))<10:return obj
        return None

    def _drag_to(self, point, modifiers):
        """Apply a drag position to the selected model item."""
        if isinstance(self, HighwayView) and self.dragged in self.scenario.objects:
            x=(point.x()-self.origin.x())/self.scale
            beta=self._screen_to_beta(point.y())
            current_x, current_beta = self.scenario.object_state(self.dragged, self.scenario.time)
            if modifiers & Qt.KeyboardModifier.ShiftModifier: x = current_x
            if modifiers & Qt.KeyboardModifier.ControlModifier: beta = current_beta
            if self.dragged.kind == "clock":
                x = self._snap_tenth(x)
            beta = self._snap_beta(beta, allow_light=self.dragged.kind == "flash")
            if self.dragged.kind != "flash":
                beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, beta))
            if self.dragged.programmed and not modifiers & (
                Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier
            ):
                self.scenario.add_programmed_change(
                    self.dragged,
                    self.scenario.time,
                    current_x,
                    beta,
                )
            else:
                self.scenario.set_object_state(self.dragged, self.scenario.time, x, beta)
        elif isinstance(self, SpacetimeDiagramView) and self.dragged in self.scenario.events:
            x,t=inverse_transform((point.x()-self.origin.x())/self.scale,(self.origin.y()-point.y())/self.scale,self.scenario.beta_rel)
            if self.dragged.placed_at_worldline and self.dragged.object_name:
                obj=self.scenario.object(self.dragged.object_name); x=obj.position(t)
            if self.dragged.fixed_at_intersection and self.dragged.intersection_names:
                a=self.scenario.object(self.dragged.intersection_names[0]); b=self.scenario.object(self.dragged.intersection_names[1])
                hit=a.worldline.intersection(b.worldline)
                if hit: t,x=hit
            if modifiers & Qt.KeyboardModifier.ControlModifier: x,t=round(x,1),round(t,1)
            self.dragged.x,self.dragged.t=x,t

    def _context_menu(self, point):
        """Show context actions for the selected or empty area."""
        menu=QMenu(self)
        if isinstance(self, HighwayView):
            if self.hovered:
                obj = self.hovered
                object_type = "Clock" if obj.kind == "clock" else "Light flash"
                title = menu.addAction(f"{object_type} {obj.label}")
                title.setEnabled(False)
                menu.addSeparator()
                menu.addAction("Delete", lambda: self._delete_object(obj))
                if obj.kind == "clock":
                    menu.addAction("Jump to object", lambda: self._jump_to_object(obj))
                if obj.worldline.has_birth:
                    menu.addAction("Cancel birth", lambda: self._cancel_birth(obj))
                else:
                    menu.addAction(
                        "Set birth here && now",
                        lambda: self._set_birth(obj),
                    )
                if obj.worldline.has_termination:
                    menu.addAction(
                        "Cancel termination",
                        lambda: self._cancel_termination(obj),
                    )
                else:
                    menu.addAction(
                        "Set termination here && now",
                        lambda: self._set_termination(obj),
                    )
                menu.addAction("Program", lambda: self._program(obj))
            else:
                x = (point.x()-self.origin.x())/self.scale
                beta = self._screen_to_beta(point.y())
                create_menu = menu.addMenu("Create")
                create_menu.addAction("Clock", lambda: self._create_clock(x, beta))
                create_menu.addAction("Light flash", lambda: self._create_flash(x, beta))
                transform_menu = menu.addMenu("Transform")
                transform_menu.addAction("Up", self._transform_up)
                transform_menu.addAction("Down", self._transform_down)
                transform_menu.addAction("Original frame", self._original_frame)
        else:
            if self.hovered in self.scenario.events:
                selected_event = self.hovered
                title = menu.addAction(f"Event {selected_event.label}")
                title.setEnabled(False)
                menu.addSeparator()
                construct_menu = menu.addMenu("Construct")
                construct_menu.addAction(
                    "Light cone",
                    lambda: self._add_decoration("lightcone", selected_event),
                )
                construct_menu.addAction(
                    "Invariant hyperbola",
                    lambda: self._add_decoration("hyperbola", selected_event),
                )
                construct_menu.addAction(
                    "Spacetime interval to . . .",
                    lambda: self._start_interval(selected_event),
                )
                menu.addAction("Delete", lambda: self._delete_event(selected_event))
            else: menu.addAction("Create event", lambda: self._create_event(point))
        menu.exec(self.mapToGlobal(point))

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
        self.update()

    def _start_interval(self, event) -> None:
        """Choose the first event for a new spacetime interval."""
        self.setFocus()
        self._interval_first_event = event
        self.instruction_changed.emit(
            "Create invariant interval: select or click on another event."
        )

    def _add_interval(self, first, second) -> None:
        """Add an interval between two selected events."""
        mutation = lambda: self.scenario.add_interval(first, second)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.instruction_changed.emit("")
        self.changed.emit()
        self.update()

    def _create_clock(self, x: float, beta: float) -> None:
        """Create a clock from a highway position and velocity."""
        try:
            obj = self.scenario.add_clock_in_frame(
                self._snap_tenth(x),
                self.scenario.time,
                self._snap_beta(beta, allow_light=False),
            )
        except ValueError:
            return
        if self.history is not None:
            self.scenario.objects.remove(obj)
            self.history.do(AddObject(self.scenario, obj))
        self.changed.emit()

    def _create_flash(self, x: float, beta: float) -> None:
        """Create a light flash from a highway position and velocity."""
        snapped_beta = self._snap_beta(beta, allow_light=True)
        obj = self.scenario.add_flash_in_frame(
            self._snap_tenth(x),
            self.scenario.time,
            1 if snapped_beta >= 0 else -1,
        )
        if self.history is not None:
            self.scenario.objects.remove(obj)
            self.history.do(AddObject(self.scenario, obj))
        self.changed.emit()

    def _delete_object(self, obj) -> None:
        """Delete an object, recording the command when possible."""
        if self.history is None:
            self.scenario.remove_object(obj)
        else:
            self.history.do(DeleteObject(self.scenario, obj))
        self.changed.emit()
        self.update()

    def _delete_event(self, event) -> None:
        """Delete an event, recording the command when possible."""
        if self.history is None:
            self.scenario.remove_event(event)
        else:
            self.history.do(DeleteEvent(self.scenario, event))
        self.changed.emit()
        self.update()

    def _set_birth(self, obj) -> None:
        """Set an object's birth point at the displayed state."""
        mutation = lambda: self.scenario.set_birth_here_now(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()
        self.update()

    def _set_termination(self, obj) -> None:
        """Set an object's termination point at the displayed state."""
        mutation = lambda: self.scenario.set_termination_here_now(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()
        self.update()

    def _cancel_birth(self, obj) -> None:
        """Cancel an object's existing birth constraint."""
        mutation = lambda: self.scenario.cancel_birth(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()
        self.update()

    def _cancel_termination(self, obj) -> None:
        """Cancel an object's existing termination constraint."""
        mutation = lambda: self.scenario.cancel_termination(obj)
        if self.history is None:
            mutation()
        else:
            self.history.do(Snapshot(self.scenario, mutation))
        self.changed.emit()
        self.update()

    def _program(self, obj) -> None:
        """Program an object for velocity-change editing."""
        if self.history is None:
            self.scenario.program_object(obj)
        else:
            self.history.do(ProgramObject(self.scenario, obj))
        self.changed.emit()
        self.update()

    def _screen_to_beta(self, y):
        """Convert a highway screen coordinate to velocity."""
        s=(self.height()/2-y)/(self.height()*.46)
        return math.copysign(abs(s)**.25,s) if s else 0.0

    def pan_horizontal(self, pixels: float) -> None:
        """Pan the view horizontally by a pixel amount."""
        self.offset = (self.offset[0] + pixels, self.offset[1])
        self.horizontal_view_changed.emit(self.scale, self.offset[0])
        self.update()

    def _draw_tick_label(self, painter: QPainter, text: str, x: float, y: float) -> None:
        """Draw one axis tick label."""
        painter.drawText(QPointF(x, y), text)

    @staticmethod
    def _snap_tenth(value: float) -> float:
        """Round a value to the nearest tenth."""
        return math.floor(10.0 * value + 0.5) / 10.0

    def _nice_tick_unit(self) -> float:
        """Choose a readable axis tick spacing."""
        unit = 1.0
        while unit * self.scale < 50.0:
            unit *= 2.0
        while unit * self.scale > 300.0:
            unit /= 2.0
        return unit


class SpacetimeDiagramView(_View):
    """Display worldlines and events against spacetime axes."""

    def center_current_time(self) -> None:
        """Center the vertical view on the current scenario time."""
        self.offset = (self.offset[0], self.scenario.time * self.scale)

    def paintEvent(self, event):
        """Paint axes, worldlines, events, and decorations."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        origin = self.origin
        width, height = self.width(), self.height()
        axis_font = painter.font()
        axis_font.setPointSize(max(1, round(axis_font.pointSize() * 0.825)))
        painter.setFont(axis_font)

        painter.setPen(QPen(QColor("#d0d0d0"), 1))
        painter.drawLine(QPointF(0, origin.y()), QPointF(width, origin.y()))
        painter.drawLine(QPointF(origin.x(), 0), QPointF(origin.x(), height))
        painter.setPen(QPen(QColor("#777777"), 1))
        unit = self._nice_tick_unit()
        first_tick = math.floor((-origin.x()) / (self.scale * unit))
        last_tick = math.ceil((width - origin.x()) / (self.scale * unit))
        for tick in range(first_tick, last_tick + 1):
            value = tick * unit
            px = origin.x() + value * self.scale
            painter.drawLine(QPointF(px, origin.y() - 4), QPointF(px, origin.y() + 4))
            self._draw_tick_label(painter, f"{value:g}", px - 4, origin.y() + 18)
        time_unit = self._nice_tick_unit()
        first_time_tick = math.floor((-(height - origin.y())) / (self.scale * time_unit))
        last_time_tick = math.ceil(origin.y() / (self.scale * time_unit))
        for tick in range(first_time_tick, last_time_tick + 1):
            value = tick * time_unit
            py = origin.y() - value * self.scale
            painter.drawLine(QPointF(origin.x() - 4, py), QPointF(origin.x() + 4, py))
            self._draw_tick_label(painter, f"{value:g}", origin.x() - 24, py + 4)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawText(QPointF(width - 20, origin.y() - 8), "x")
        painter.drawText(QPointF(origin.x() + 8, 14), "t")

        current_y = origin.y() - self.scenario.time * self.scale
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 90, 220, 45))
        painter.drawRect(QRectF(0, current_y - 6, width, 12))
        painter.setPen(QPen(QColor(30, 90, 220, 170), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(0, current_y), QPointF(width, current_y))

        minimum, maximum = self._visible_time_bounds(origin)
        for obj in self.scenario.objects:
            color = QColor("#1769aa") if obj.kind == "clock" else QColor("#c62828")
            x, beta = self._frame_state(obj, self.scenario.time)
            painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine if obj.kind == "flash" else Qt.PenStyle.SolidLine))
            if obj.kind == "clock":
                self._draw_clock_trace(painter, obj, minimum, maximum, origin)
            else:
                points = self._frame_trace(obj, minimum, maximum)
                if points:
                    path = QPainterPath()
                    path.moveTo(
                        QPointF(
                            origin.x() + points[0].x() * self.scale,
                            origin.y() - points[0].y() * self.scale,
                        )
                    )
                    for point in points[1:]:
                        path.lineTo(
                            QPointF(
                                origin.x() + point.x() * self.scale,
                                origin.y() - point.y() * self.scale,
                            )
                        )
                    painter.drawPath(path)
            painter.setPen(QPen(color, 1.0))
            if self._object_exists(obj, self.scenario.time, x):
                painter.setPen(QPen(color, 1.5))
                painter.setBrush(Qt.GlobalColor.white)
                painter.drawEllipse(QPointF(origin.x() + x * self.scale, current_y), 5, 5)
                painter.drawText(QPointF(origin.x() + x * self.scale + 7, current_y - 5), obj.label)

        for event in self.scenario.events:
            x, t = transform(event.x, event.t, self.scenario.beta_rel)
            point = QPointF(
                origin.x() + x * self.scale,
                origin.y() - t * self.scale,
            )
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setBrush(Qt.GlobalColor.black)
            if event.beta_change:
                painter.drawRect(QRectF(point.x() - 4, point.y() - 4, 8, 8))
            elif event.boundary:
                painter.drawPolygon(
                    [
                        QPointF(point.x(), point.y() - 5),
                        QPointF(point.x() + 5, point.y()),
                        QPointF(point.x(), point.y() + 5),
                        QPointF(point.x() - 5, point.y()),
                    ]
                )
            else:
                painter.drawEllipse(point, 4, 4)
            painter.drawText(QPointF(origin.x() + x * self.scale + 7, origin.y() - t * self.scale + 4), event.label)
        x_min = -origin.x() / self.scale
        x_max = (width - origin.x()) / self.scale
        for d in self.scenario.decorations:
            if getattr(d, "first", None) and getattr(d, "second", None):
                a,b=d.first,d.second
                ax,at=transform(a.x,a.t,self.scenario.beta_rel); bx,bt=transform(b.x,b.t,self.scenario.beta_rel)
                first_point = QPointF(origin.x() + ax * self.scale, origin.y() - at * self.scale)
                second_point = QPointF(origin.x() + bx * self.scale, origin.y() - bt * self.scale)
                interval_color = QColor("#ffafaf")
                painter.setPen(QPen(interval_color, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(first_point, 4, 4)
                painter.drawEllipse(second_point, 4, 4)
                painter.drawLine(first_point, second_point)

                dx = abs(a.x - b.x)
                dt = abs(a.t - b.t)
                interval_squared = d.squared
                interval_type = {
                    "lightlike": "L",
                    "timelike": "T",
                    "spacelike": "S",
                }[classify_interval(b.x - a.x, b.t - a.t)]
                interval_value = math.sqrt(abs(interval_squared))
                label = (
                    f"{interval_type}: {interval_value:.2f}; "
                    f"Δx={dx:.2f}; Δt={dt:.2f}"
                )
                midpoint = QPointF(
                    origin.x() + (ax + bx) * self.scale / 2.0,
                    origin.y() - (at + bt) * self.scale / 2.0,
                )
                metrics = painter.fontMetrics()
                label_width = metrics.horizontalAdvance(label)
                label_height = metrics.height()
                label_rect = QRectF(
                    midpoint.x() - label_width / 2.0 - 1.5,
                    midpoint.y() - label_height + label_height / 3.0 - 8.0 - 1.5,
                    label_width + 3.0,
                    label_height + 3.0,
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(250, 150, 150, 200))
                painter.drawRoundedRect(label_rect, 8.0, 8.0)
                painter.setPen(QPen(Qt.GlobalColor.black, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawText(
                    QPointF(
                        midpoint.x() - label_width / 2.0,
                        midpoint.y() + label_height / 3.0 - 8.0,
                    ),
                    label,
                )
            elif getattr(d,"event",None):
                x,t=transform(d.event.x,d.event.t,self.scenario.beta_rel)
                painter.setPen(QPen(QColor("#ffb0b0"), 1.5, Qt.PenStyle.SolidLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if d.kind == "lightcone":
                    for direction in (-1, 1):
                        painter.drawLine(
                            QPointF(
                                origin.x() + x_min * self.scale,
                                origin.y()
                                - (t + direction * (x_min - x)) * self.scale,
                            ),
                            QPointF(
                                origin.x() + x_max * self.scale,
                                origin.y()
                                - (t + direction * (x_max - x)) * self.scale,
                            ),
                        )
                elif d.kind == "hyperbola":
                    # Draw the constant-interval curve through the event.
                    interval_squared = t * t - x * x
                    path = QPainterPath()
                    if abs(interval_squared) <= 1e-9:
                        if abs(t) > 1e-9 or abs(x) > 1e-9:
                            direction = 1.0 if t >= 0 else -1.0
                            branch = 1.0 if x >= 0 else -1.0
                            sample_x = x_min if branch < 0 else x_max
                            if branch < 0:
                                sample_x = min(sample_x, -1e-9)
                            else:
                                sample_x = max(sample_x, 1e-9)
                            start = QPointF(
                                origin.x() + x * self.scale,
                                origin.y() - t * self.scale,
                            )
                            end = QPointF(
                                origin.x() + sample_x * self.scale,
                                origin.y()
                                - (t + direction * (sample_x - x)) * self.scale,
                            )
                            painter.drawLine(start, end)
                    elif interval_squared > 1e-9:
                        sign = 1.0 if t >= 0 else -1.0
                        radius = math.sqrt(interval_squared)
                        for index in range(161):
                            sample_x = x_min + (x_max - x_min) * index / 160
                            sample_t = sign * math.sqrt(sample_x * sample_x + radius * radius)
                            point = QPointF(
                                origin.x() + sample_x * self.scale,
                                origin.y() - sample_t * self.scale,
                            )
                            if index == 0:
                                path.moveTo(point)
                            else:
                                path.lineTo(point)
                    elif interval_squared < -1e-9:
                        radius = math.sqrt(-interval_squared)
                        time_min = minimum
                        time_max = maximum
                        sign = 1.0 if x >= 0 else -1.0
                        for index in range(161):
                            sample_t = time_min + (time_max - time_min) * index / 160
                            sample_x = sign * math.sqrt(sample_t * sample_t + radius * radius)
                            point = QPointF(
                                origin.x() + sample_x * self.scale,
                                origin.y() - sample_t * self.scale,
                            )
                            if index == 0:
                                path.moveTo(point)
                            else:
                                path.lineTo(point)
                    painter.drawPath(path)


class HighwayView(_View):
    """Display objects by position and velocity at one time."""

    def _beta_to_screen(self, beta: float) -> float:
        """Map a velocity to the highway's vertical coordinate."""
        # Match the Java display: velocity is expanded near zero and compressed
        # near the speed-of-light boundaries.
        signed = math.copysign(abs(beta) ** 4, beta) if beta else 0.0
        top_margin = 19.0
        bottom_margin = 5.0
        usable_height = max(1.0, self.height() - top_margin - bottom_margin)
        return top_margin + usable_height / 2 - signed * (usable_height * 0.46)

    def _snap_beta(self, beta: float, allow_light: bool) -> float:
        """Snap a velocity to the display's preferred values."""
        if allow_light:
            return 1.0 if beta >= 0 else -1.0
        sign = math.copysign(1.0, beta) if beta else 1.0
        magnitude = min(abs(beta), MAX_OBJECT_BETA)
        target_gamma = 1.0 / math.sqrt(1.0 - magnitude * magnitude)
        max_gamma_index = math.floor(
            (1.0 / math.sqrt(1.0 - MAX_OBJECT_BETA * MAX_OBJECT_BETA) - 1.0) / 0.1
        )
        gamma_values = (1.0 + 0.1 * index for index in range(max_gamma_index + 1))
        snapped_gamma = min(gamma_values, key=lambda value: abs(value - target_gamma))
        snapped_beta = math.sqrt(1.0 - 1.0 / (snapped_gamma * snapped_gamma))
        return sign * snapped_beta

    def _clock_reading_in_frame(self, obj, frame_time: float, x: float) -> float:
        """Return a clock reading at a displayed position."""
        _, original_time = inverse_transform(x, frame_time, self.scenario.beta_rel)
        return obj.clock_reading(original_time)

    def _clock_is_synchronized(self, obj, frame_time: float, x: float, beta: float) -> bool:
        """Check whether a clock matches the frame's synchronized time."""
        original_x, original_time = inverse_transform(x, frame_time, self.scenario.beta_rel)
        original_beta = velocity_add(beta, self.scenario.beta_rel)
        if abs(original_beta) >= 1.0:
            return True
        synchronized = gamma(original_beta) * (original_time - original_beta * original_x)
        return abs(obj.clock_reading(original_time) - synchronized) < 1e-6

    def _draw_clock(
        self,
        painter: QPainter,
        obj,
        px: float,
        py: float,
        beta: float,
        color: QColor,
        fill_color: QColor,
        synchronized: bool,
    ) -> None:
        """Draw a clock face and its reading."""
        painter.save()
        radius = 12.0
        contraction = math.sqrt(max(0.0, 1.0 - beta * beta))
        width = 2.0 * radius * contraction
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(fill_color)
        painter.drawEllipse(QPointF(px, py), width / 2.0, radius)

        # The hands show the clock's proper-time reading without face labels.
        reading = self._clock_reading_in_frame(
            obj,
            self.scenario.time,
            (px - self.origin.x()) / self.scale,
        )
        angle = 2.0 * math.pi * (reading % 1.0)
        hand_x = px + (width / 2.0) * 0.72 * math.sin(angle)
        hand_y = py - radius * 0.72 * math.cos(angle)
        painter.drawLine(QPointF(px, py), QPointF(hand_x, hand_y))
        painter.drawEllipse(QPointF(px, py), 1.5, 1.5)

        font = painter.font()
        font.setPointSize(max(1, round(font.pointSize() * 0.825)))
        painter.setFont(font)
        reading_text = f"{reading:.2f}"
        text_width = painter.fontMetrics().horizontalAdvance(reading_text)
        text_height = painter.fontMetrics().height()
        badge_background = QColor(250, 250, 250, 200) if synchronized else QColor(5, 5, 5, 200)
        badge_text = Qt.GlobalColor.black if synchronized else Qt.GlobalColor.white
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_background)
        badge_y = py - radius - text_height - 5.5
        painter.drawRoundedRect(
            QRectF(
                px - text_width / 2.0 - 1.5,
                badge_y,
                text_width + 3.0,
                text_height + 3.0,
            ),
            8.0,
            8.0,
        )
        painter.setPen(QPen(badge_text, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(
            QPointF(px - text_width / 2.0, py - radius - 5.5),
            reading_text,
        )
        painter.restore()

    def _draw_flash(self, painter: QPainter, px: float, py: float, color: QColor) -> None:
        """Draw a light-flash marker."""
        radius = 9.0
        painter.setPen(QPen(color, 1.5))
        for angle in (0.0, math.pi / 4.0, math.pi / 2.0, 3.0 * math.pi / 4.0):
            dx = radius * math.cos(angle)
            dy = radius * math.sin(angle)
            painter.drawLine(QPointF(px - dx, py - dy), QPointF(px + dx, py + dy))

    def _draw_edge_indicator(self, painter: QPainter, y: float, left: bool, color: QColor) -> None:
        """Draw an indicator for an object outside the horizontal view."""
        edge = 100.0 if left else self.width()
        inward = 10.0 if left else -10.0
        painter.setPen(QPen(color, 1.0))
        painter.setBrush(color)
        painter.drawPolygon(
            (
                QPointF(edge, y),
                QPointF(edge + inward, y - 6.0),
                QPointF(edge + inward, y + 6.0),
            )
        )

    def _jump_to_object(self, obj) -> None:
        """Change to an object's comoving frame and center it."""
        x, beta = self._frame_state(obj, self.scenario.time)
        frame_beta = velocity_add(beta, self.scenario.beta_rel)
        synchronized_time = gamma(beta) * (self.scenario.time - beta * x)
        self.scenario.set_frame(frame_beta)
        self.scenario.time = synchronized_time
        centered_x, _ = self._frame_state(obj, self.scenario.time)
        self.offset = (-centered_x * self.scale, self.offset[1])
        self.horizontal_view_changed.emit(self.scale, self.offset[0])
        self.changed.emit()
        self.update()

    def paintEvent(self, event):
        """Paint the position lane, velocity axis, and objects."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        origin = self.origin
        width, height = self.width(), self.height()
        lane_origin_y = self._beta_to_screen(0.0)
        axis_start = 100.0
        painter.save()
        axis_font = painter.font()
        axis_font.setPointSize(max(1, round(axis_font.pointSize() * 0.825)))
        painter.setFont(axis_font)

        painter.setPen(QPen(QColor("#d0d0d0"), 1))
        painter.drawLine(QPointF(axis_start, lane_origin_y), QPointF(width, lane_origin_y))
        painter.setPen(QPen(QColor("#777777"), 1))
        unit = self._nice_tick_unit()
        first_tick = math.floor((-origin.x()) / (self.scale * unit))
        last_tick = math.ceil((width - origin.x()) / (self.scale * unit))
        for tick in range(first_tick, last_tick + 1):
            value = tick * unit
            px = origin.x() + value * self.scale
            if px < axis_start:
                continue
            painter.drawLine(QPointF(px, lane_origin_y - 4), QPointF(px, lane_origin_y + 4))
            self._draw_tick_label(painter, f"{value:g}", px - 4, lane_origin_y + 18)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawText(QPointF(width - 20, lane_origin_y - 8), "x")

        axis_x = 44.0
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawLine(
            QPointF(axis_x, self._beta_to_screen(1.0)),
            QPointF(axis_x, self._beta_to_screen(-1.0)),
        )
        beta_label_x = axis_x - 42.0
        gamma_label_x = 60.0
        beta_ticks = (-1.0, -0.9, -0.8, 0.0, 0.8, 0.9, 1.0)
        for beta in beta_ticks:
            y = self._beta_to_screen(beta)
            painter.setPen(QPen(QColor("#777777"), 1))
            painter.drawLine(QPointF(axis_x - 5, y), QPointF(axis_x, y))
            painter.drawText(
                QRectF(beta_label_x - 8.0, y - 8.0, 42.0, 16.0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{beta:.2f}",
            )

        for gamma_value in (1, 2, 3, 5):
            beta = math.sqrt(1 - 1 / (gamma_value * gamma_value))
            y = self._beta_to_screen(beta)
            painter.drawLine(QPointF(axis_x + 5, y), QPointF(axis_x, y))
            painter.drawLine(
                QPointF(axis_x + 5, self._beta_to_screen(-beta)),
                QPointF(axis_x, self._beta_to_screen(-beta)),
            )
            painter.drawText(QPointF(gamma_label_x, y + 4), f"{gamma_value:.1f}")
            painter.drawText(
                QPointF(gamma_label_x, self._beta_to_screen(-beta) + 4),
                f"{gamma_value:.1f}",
            )

        painter.drawLine(
            QPointF(axis_x + 5, self._beta_to_screen(1.0)),
            QPointF(axis_x, self._beta_to_screen(1.0)),
        )
        painter.drawLine(
            QPointF(axis_x + 5, self._beta_to_screen(-1.0)),
            QPointF(axis_x, self._beta_to_screen(-1.0)),
        )
        painter.drawText(QPointF(gamma_label_x, self._beta_to_screen(1.0) + 4), "∞")
        painter.drawText(QPointF(gamma_label_x, self._beta_to_screen(-1.0) + 4), "∞")
        axis_label_y = self._beta_to_screen(1.0) - 16.0
        painter.drawText(
            QRectF(beta_label_x - 8.0, axis_label_y - 8.0, 42.0, 16.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "β",
        )
        painter.drawText(QPointF(gamma_label_x, axis_label_y), "γ")
        painter.restore()
        painter.setFont(axis_font)

        for obj in self.scenario.objects:
            x, beta = self._frame_state(obj, self.scenario.time)
            if not self._object_exists(obj, self.scenario.time, x):
                continue
            px, py = origin.x() + x * self.scale, self._beta_to_screen(beta)
            color = QColor("#1769aa") if obj.kind == "clock" else QColor("#c62828")
            if px < axis_start:
                self._draw_edge_indicator(painter, py, True, color)
                continue
            if px > width:
                self._draw_edge_indicator(painter, py, False, color)
                continue
            epsilon = 1e-6
            _, old_beta = self._frame_state(obj, self.scenario.time - epsilon)
            _, new_beta = self._frame_state(obj, self.scenario.time + epsilon)
            if obj.kind == "clock":
                old_color = QColor(180, 180, 180, 200)
                new_color = QColor("#00c000") if obj.programmed else color
                old_synchronized = self._clock_is_synchronized(obj, self.scenario.time, x, old_beta)
                new_synchronized = self._clock_is_synchronized(obj, self.scenario.time, x, new_beta)
                self._draw_clock(
                    painter,
                    obj,
                    px,
                    self._beta_to_screen(old_beta),
                    old_beta,
                    old_color,
                    QColor(255, 255, 255, 200),
                    old_synchronized,
                )
                self._draw_clock(
                    painter,
                    obj,
                    px,
                    self._beta_to_screen(new_beta),
                    new_beta,
                    new_color,
                    Qt.GlobalColor.white,
                    new_synchronized,
                )
            else:
                self._draw_flash(
                    painter,
                    px,
                    self._beta_to_screen(old_beta),
                    QColor(180, 180, 180, 200),
                )
                self._draw_flash(
                    painter,
                    px,
                    self._beta_to_screen(new_beta),
                    QColor("#00c000") if obj.programmed else color,
                )
            painter.setPen(QPen(color, 1))
            painter.drawText(QPointF(px + 14, py + 4), obj.label)

        for event in self.scenario.events:
            x, t = transform(event.x, event.t, self.scenario.beta_rel)
            if abs(t - self.scenario.time) < 0.01:
                px = origin.x() + x * self.scale
                color = QColor("#008000") if event.beta_change else QColor("#d32f2f")
                painter.setPen(QPen(color, 1))
                painter.drawLine(QPointF(px, self._beta_to_screen(-1)), QPointF(px, self._beta_to_screen(1)))
                label_width = painter.fontMetrics().horizontalAdvance(event.label)
                painter.drawText(
                    QPointF(px - label_width / 2, self._beta_to_screen(1.0) - 16),
                    event.label,
                )
