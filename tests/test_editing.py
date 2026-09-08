"""Tests for model editing commands and decorations."""

import pytest

from spacetime.commands.undo_redo import History, Snapshot
from spacetime.model.scenario import Scenario


def test_intersection_and_decorations_are_model_only():
    """Verify intersections and decorations without requiring Qt."""
    scenario = Scenario()
    left = scenario.add_clock(-1, 0, 0.5)
    right = scenario.add_clock(1, 0, -0.5)
    event = scenario.intersection_event(left, right)
    assert event.x == pytest.approx(0)
    assert event.t == pytest.approx(2)
    assert scenario.add_interval(event, event).squared == pytest.approx(0)
    assert scenario.add_light_cone(event).event is event
    assert scenario.add_hyperbola(event).point(0) == pytest.approx((0, 3))


def test_snapshot_history_supports_redo():
    """Verify snapshot undo and redo behavior."""
    scenario = Scenario()
    history = History()
    history.do(Snapshot(scenario, lambda: setattr(scenario, "time", 4.0)))
    assert scenario.time == 4
    history.undo()
    assert scenario.time == 0
    history.redo()
    assert scenario.time == 4


def test_programmed_change_creates_and_replaces_delta_beta_event():
    """Verify programmed velocity changes replace their event."""
    scenario = Scenario()
    clock = scenario.add_clock()
    scenario.program_object(clock)

    scenario.add_programmed_change(clock, 2.0, 1.0, 0.5)
    first = [event for event in scenario.events if event.beta_change]
    assert len(first) == 1
    assert first[0].label == "C1:Δβ1"

    scenario.add_programmed_change(clock, 2.0, 1.0, 0.6)
    current = [event for event in scenario.events if event.beta_change]
    assert len(current) == 1
    assert current[0].t == pytest.approx(2.0)
    assert current[0].label == "C1:Δβ1"


def test_birth_and_termination_create_boundary_events():
    scenario = Scenario(time=2.0)
    clock = scenario.add_clock()
    first_event = scenario.add_event(0.0, 1.0)
    assert first_event.label == "E1"

    scenario.set_birth_here_now(clock)
    birth = [event for event in scenario.events if event.boundary == "birth"]
    assert len(birth) == 1
    assert birth[0].label == "E2"
    assert birth[0].note == "C1 born"

    scenario.time = 4.0
    scenario.set_termination_here_now(clock)
    termination = [event for event in scenario.events if event.boundary == "termination"]
    assert len(termination) == 1
    assert termination[0].label == "E3"
    assert termination[0].note == "C1 terminated"

    scenario.cancel_birth(clock)
    scenario.cancel_termination(clock)
    assert not [event for event in scenario.events if event.boundary]


def test_manual_object_state_change_removes_boundary_events():
    """Verify replacing a worldline removes stale boundary events."""
    scenario = Scenario(time=2.0)
    clock = scenario.add_clock()
    scenario.set_birth_here_now(clock)
    scenario.time = 4.0
    scenario.set_termination_here_now(clock)
    assert len(scenario.events) == 2

    scenario.set_object_state(clock, scenario.time, 1.0, 0.25)

    assert not [event for event in scenario.events if event.boundary]
    assert not clock.worldline.has_birth
    assert not clock.worldline.has_termination


def test_manual_object_state_change_removes_delta_beta_events():
    """Verify replacing a programmed worldline removes its change events."""
    scenario = Scenario(time=2.0)
    clock = scenario.add_clock()
    scenario.program_object(clock)
    scenario.add_programmed_change(clock, 2.0, 1.0, 0.25)
    assert any(event.beta_change for event in scenario.events)

    scenario.set_object_state(clock, scenario.time, 1.0, 0.5)

    assert not [event for event in scenario.events if event.beta_change]
    assert not clock.programmed


def test_programming_preserves_termination_until_a_new_beta():
    """Verify programming waits for a beta change before removing termination."""
    scenario = Scenario(time=2.0)
    clock = scenario.add_clock()
    scenario.program_object(clock)
    scenario.add_programmed_change(clock, 2.0, 1.0, 0.25)
    scenario.time = 4.0
    scenario.add_programmed_change(clock, 4.0, 2.0, 0.5)
    scenario.set_termination_here_now(clock)
    scenario.time = 2.0

    scenario.program_object(clock)

    assert any(record.t > 2.0 for record in clock.worldline.records)
    assert any(event.beta_change for event in scenario.events)
    assert any(event.boundary == "termination" for event in scenario.events)
    assert clock.worldline.has_termination

    scenario.add_programmed_change(clock, 2.0, 1.0, 0.75)

    assert not any(event.boundary == "termination" for event in scenario.events)
    assert not clock.worldline.has_termination
