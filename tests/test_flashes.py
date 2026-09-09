"""Tests for light flashes and Qt views."""

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from spacetime.gui.views import SpacetimeDiagramView
from spacetime.gui.views import HighwayView
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


def test_all_intersections_selection_cancels_on_empty_click(qt_app):
    """Cancel partner selection without creating a free event."""
    scenario = Scenario()
    first = scenario.add_clock()
    scenario.add_clock(2.0, 0.0, -0.5)
    view = SpacetimeDiagramView(scenario)
    view.resize(800, 400)
    view._start_all_intersections(first)

    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(20, 20),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(event)

    assert view._intersection_first_object is None
    assert scenario.events == []
