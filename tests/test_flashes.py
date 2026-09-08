"""Tests for light flashes and Qt views."""

import pytest
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
