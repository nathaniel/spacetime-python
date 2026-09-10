"""Tests for light flashes and Qt views."""

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from spacetime.commands.undo_redo import History
from spacetime.gui.tables import EventTable, ObjectTable
from spacetime.gui.main_window import MainWindow
from spacetime.gui.views import SpacetimeDiagramView
from spacetime.gui.views import HighwayView
from spacetime.model.lorentz import velocity_add
from spacetime.model.scenario import Scenario


@pytest.fixture(scope="module")
def qt_app():
    """Provide a QApplication for view tests."""
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("direction", [1, -1])
def test_flash_remains_lightlike_in_every_frame(qt_app, direction):
    """Verify a flash remains lightlike in transformed frames."""
    scenario = Scenario(beta_rel=0.6)
    flash = scenario.add_flash(2.0, 1.0, direction)

    x, beta = scenario.object_state(flash, 3.0)
    assert beta == direction

    trace = SpacetimeDiagramView(scenario)._frame_trace(flash, -1.0, 1.0, 2)
    dx = trace[1].x() - trace[0].x()
    dt = trace[1].y() - trace[0].y()
    assert dx == pytest.approx(direction * dt)


def test_jump_to_clock_selects_comoving_frame(qt_app):
    """Verify jumping to a clock selects its comoving frame."""
    scenario = Scenario(beta_rel=0.3, time=2.0)
    clock = scenario.add_clock(0.0, 0.0, 0.6)
    view = HighwayView(scenario)
    view.resize(800, 300)

    view._jump_to_object(clock)

    assert scenario.beta_rel == pytest.approx(0.6)
    assert scenario.object_state(clock, scenario.time)[1] == pytest.approx(0.0)
    x, _ = view._frame_state(clock, scenario.time)
    assert view.origin.x() + x * view.scale == pytest.approx(view.width() / 2)


def test_diagram_hover_finds_worldline_and_event_stays_aligned(qt_app):
    """Use the nearest worldline for hover and constrain created events to it."""
    scenario = Scenario()
    clock = scenario.add_clock(0.0, 0.0, 0.5)
    view = SpacetimeDiagramView(scenario)
    view.resize(800, 400)

    point = QPoint(
        round(view.origin.x() + 0.5 * view.scale),
        round(view.origin.y() - 1.0 * view.scale),
    )
    assert view._hit(point) is clock

    view._create_worldline_event(clock, 1.0)
    event = scenario.events[-1]
    frame_x, frame_t = scenario.coordinates(event.x, event.t)
    assert frame_x == pytest.approx(0.5)
    assert frame_t == pytest.approx(1.0)


def test_all_intersections_selection_uses_partner_worldline(qt_app):
    """Construct all crossings after selecting a second worldline."""
    scenario = Scenario()
    first = scenario.add_clock(0.0, 0.0, 0.5)
    second = scenario.add_clock(2.0, 0.0, -0.5)
    view = SpacetimeDiagramView(scenario)
    view.history = History()
    view.resize(800, 400)
    view._start_all_intersections(first)

    point = QPointF(
        view.origin.x() + 1.5 * view.scale,
        view.origin.y() - 1.0 * view.scale,
    )
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(event)

    assert view._intersection_first_object is None
    assert len(scenario.events) == 1
    assert scenario.events[0].intersection_names == (first.name, second.name)
    assert view.history.undo()
    assert not scenario.events
    assert view.history.redo()
    assert len(scenario.events) == 1


def test_mouse_scroll_uses_mouse_sensitivity_when_pixel_delta_is_present(qt_app):
    """Use mouse sensitivity for mouse events even when pixel data is present."""
    scenario = Scenario()
    view = SpacetimeDiagramView(scenario)
    view.trackpad_sensitivity = 2.0
    view.mouse_wheel_sensitivity = 0.5
    wheel = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 20),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    view.wheelEvent(wheel)

    assert scenario.time == pytest.approx(0.025)


def test_pixel_scroll_uses_trackpad_sensitivity(qt_app):
    """Use trackpad sensitivity for pixel-only scroll data."""
    scenario = Scenario()
    view = SpacetimeDiagramView(scenario)
    view.trackpad_sensitivity = 2.0
    view.mouse_wheel_sensitivity = 0.5
    wheel = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 20),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    view.wheelEvent(wheel)

    assert scenario.time == pytest.approx(0.2)


def test_spacetime_vertical_scroll_scales_with_zoom(qt_app):
    """Advance farther in time per screen gesture when zoomed out."""
    scenario = Scenario()
    view = SpacetimeDiagramView(scenario)
    view.scale = 30.0
    wheel = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 20),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    view.wheelEvent(wheel)

    assert scenario.time == pytest.approx(0.2)


def test_highway_vertical_pixel_scroll_uses_fixed_frame_step(qt_app):
    """Do not amplify Highway frame changes by trackpad gesture distance."""
    scenario = Scenario()
    view = HighwayView(scenario)
    view.trackpad_sensitivity = 1.0
    first = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 20),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    second = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 100),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    view.wheelEvent(first)
    first_beta = scenario.beta_rel
    view.wheelEvent(second)
    second_delta = scenario.beta_rel - first_beta

    assert first_beta == pytest.approx(0.025)
    assert second_delta == pytest.approx(velocity_add(first_beta, 0.025) - first_beta)


def test_object_table_edit_is_undoable(qt_app):
    """Undo a completed object-table edit as one logical change."""
    scenario = Scenario()
    scenario.add_clock()
    table = ObjectTable(scenario)
    table.history = History()

    table.item(0, 5).setText("A new note")

    assert scenario.objects[0].note == "A new note"
    assert table.history.undo()
    assert scenario.objects[0].note == "Clock 1"


def test_event_table_edit_is_undoable(qt_app):
    """Undo a completed event-table edit as one logical change."""
    scenario = Scenario()
    scenario.add_event(1.0, 2.0)
    table = EventTable(scenario)
    table.history = History()

    table.item(0, 3).setText("A new note")

    assert scenario.events[0].note == "A new note"
    assert table.history.undo()
    assert scenario.events[0].note == "Event 1"


def test_hover_cursor_only_marks_draggable_events(qt_app):
    """Use a draggable cursor only where a diagram item can be moved."""
    scenario = Scenario()
    scenario.add_event(0.0, 0.0)
    view = SpacetimeDiagramView(scenario)
    view.resize(800, 400)
    event_point = QPoint(
        round(view.origin.x()),
        round(view.origin.y()),
    )

    view._update_hover(event_point)

    assert view.cursor().shape() == Qt.CursorShape.OpenHandCursor

    scenario.add_clock(1.0, 0.0, 0.0)
    worldline_point = QPoint(
        round(view.origin.x() + view.scale),
        round(view.origin.y()),
    )
    view._update_hover(worldline_point)

    assert view.cursor().shape() == Qt.CursorShape.ArrowCursor

    scenario.add_clock(2.0, 0.0, 0.0)
    view._intersection_first_object = scenario.objects[0]
    second_worldline_point = QPoint(
        round(view.origin.x() + 2 * view.scale),
        round(view.origin.y()),
    )
    view._update_hover(second_worldline_point)

    assert view.cursor().shape() == Qt.CursorShape.PointingHandCursor

    constrained = scenario.add_event(2.0, 0.0)
    constrained.placed_at_worldline = True
    constrained_point = QPoint(
        round(view.origin.x() + 2 * view.scale),
        round(view.origin.y()),
    )
    view._update_hover(constrained_point)

    assert view.cursor().shape() == Qt.CursorShape.ArrowCursor

    second_event = scenario.add_event(3.0, 0.0)
    view._interval_first_event = scenario.events[0]
    second_event_point = QPoint(
        round(view.origin.x() + 3 * view.scale),
        round(view.origin.y()),
    )
    view._update_hover(second_event_point)

    assert view.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_diagram_worldline_click_does_not_enter_drag_state(qt_app):
    """Clicking a diagram worldline must not imply that it can be dragged."""
    scenario = Scenario()
    scenario.add_clock(0.0, 0.0, 0.5)
    view = SpacetimeDiagramView(scenario)
    view.resize(800, 400)
    point = QPoint(round(view.origin.x()), round(view.origin.y()))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    view.mousePressEvent(event)

    assert view.dragged is None
    assert view.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_replacing_scenario_rebinds_view_history(qt_app):
    """Keep all views on the main window's history after loading a scenario."""
    window = MainWindow(Scenario())
    history = History()
    window.history = history

    window._set_scenario(Scenario())

    assert window.highway.history is history
    assert window.diagram.history is history
    assert window.object_table.history is history
    assert window.event_table.history is history
    window.close()


def test_spacetime_constructions_are_undoable(qt_app):
    """Create, undo, and redo each type of spacetime decoration."""
    scenario = Scenario()
    first = scenario.add_event(0.0, 0.0)
    second = scenario.add_event(1.0, 1.0)
    view = SpacetimeDiagramView(scenario)
    view.history = History()

    view._add_decoration("lightcone", first)
    view._add_decoration("hyperbola", first)
    view._add_interval(first, second)

    assert [decoration.kind for decoration in scenario.decorations] == [
        "lightcone",
        "hyperbola",
        "interval",
    ]
    for expected_count in (2, 1, 0):
        assert view.history.undo()
        assert len(scenario.decorations) == expected_count
    for expected_count in (1, 2, 3):
        assert view.history.redo()
        assert len(scenario.decorations) == expected_count


def test_light_cone_is_painted(qt_app):
    """Render a light cone across the diagram viewport."""
    scenario = Scenario()
    event = scenario.add_event(0.0, 0.0)
    view = SpacetimeDiagramView(scenario)
    view.resize(800, 400)
    view._add_decoration("lightcone", event)
    image = QImage(800, 400, QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)

    view.render(image)

    red_pixels = 0
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.red() > 200 and 80 < color.green() < 220 and 80 < color.blue() < 220:
                red_pixels += 1
    assert red_pixels > 100
