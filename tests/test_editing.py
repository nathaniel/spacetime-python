"""Tests for model editing commands and decorations."""

import pytest

from spacetime.commands.undo_redo import History, Snapshot
from spacetime.model.scenario import Scenario
from spacetime.model.worldline import Worldline, WorldlineRecord


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


def test_automatic_event_notes_match_automatic_event_numbers():
    """Number automatic event notes from their E labels, not event count."""
    scenario = Scenario()
    first = scenario.add_event(0.0, 0.0)
    scenario.add_clock()
    second = scenario.add_event(1.0, 1.0)
    named = scenario.add_event(2.0, 2.0, name="custom")
    third = scenario.add_event(3.0, 3.0)

    assert first.name == "E1"
    assert first.note == "Event 1"
    assert second.name == "E2"
    assert second.note == "Event 2"
    assert named.note == "Event 3"
    assert third.name == "E3"
    assert third.note == "Event 3"


def test_intersection_event_can_target_a_later_crossing():
    """Keep a constrained event at the selected crossing of two worldlines."""
    scenario = Scenario()
    stationary = scenario.add_clock(0, 0, 0.0)
    reversing = scenario.add_clock(-1, 0, 0.5)
    reversing.worldline = Worldline(
        [
            reversing.worldline.records[0],
            WorldlineRecord(1, 4, 0.5, -0.5),
        ]
    )

    intersections = reversing.worldline.intersections(stationary.worldline)
    assert intersections == pytest.approx([(2, 0), (6, 0)])
    event = scenario.intersection_event(
        stationary,
        reversing,
        hit=intersections[1],
    )

    assert event.fixed_at_intersection
    assert event.intersection_names == ("C1", "C2")
    assert event.x == pytest.approx(0)
    assert event.t == pytest.approx(6)


def test_worldline_event_snaps_to_current_simultaneity_line():
    """Create a worldline event at the exact current-frame time."""
    scenario = Scenario(beta_rel=0.6, time=2.0)
    clock = scenario.add_clock(1.0, 0.0, 0.25)

    event = scenario.worldline_event(clock, scenario.time)
    frame_x, frame_t = scenario.coordinates(event.x, event.t)
    object_x, _ = scenario.object_state(clock, scenario.time)

    assert event.placed_at_worldline
    assert event.object_name == clock.name
    assert frame_x == pytest.approx(object_x)
    assert frame_t == pytest.approx(scenario.time)


def test_worldline_event_follows_object_worldline():
    """Keep a constrained event on its worldline when the object changes."""
    scenario = Scenario(time=2.0)
    clock = scenario.add_clock(0.0, 0.0, 0.5)
    event = scenario.worldline_event(clock, scenario.time)
    old_x, old_t = event.x, event.t

    scenario.set_object_state(clock, scenario.time, 0.5, 0.25)

    assert (event.x, event.t) != pytest.approx((old_x, old_t))
    frame_x, frame_t = scenario.coordinates(event.x, event.t)
    object_x, _ = scenario.object_state(clock, scenario.time)
    assert frame_x == pytest.approx(object_x)
    assert frame_t == pytest.approx(scenario.time)


def test_intersections_include_times_before_initial_records():
    """Find a crossing on the semi-infinite segment before t=0."""
    scenario = Scenario()
    first = scenario.add_clock(1, 0, 0.5)
    second = scenario.add_clock(-1, 0, -0.5)

    intersections = first.worldline.intersections(second.worldline)

    assert intersections == pytest.approx([(-2, 0)])


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
    assert first[0].label == "C1-Δβ1"

    scenario.add_programmed_change(clock, 2.0, 1.0, 0.6)
    current = [event for event in scenario.events if event.beta_change]
    assert len(current) == 1
    assert current[0].t == pytest.approx(2.0)
    assert current[0].label == "C1-Δβ1"


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
