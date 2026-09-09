"""Scenario state and operations for the relativistic editor."""

from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Iterable
from .objects import STObject, Clock, Flash
from .events import Event
from .decorations import Decoration, Interval, LightCone, Hyperbola
from .lorentz import _check_beta, inverse_transform, transform, velocity_add
from .worldline import WorldlineRecord

# Match the Java version currently in use: non-flash beta is capped at 0.9999.
MAX_OBJECT_BETA = 0.9999

@dataclass
class Scenario:
    """Mutable collection of objects, events, and diagram decorations."""

    beta_rel: float = 0.0
    time: float = 0.0
    objects: list[STObject] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    decorations: list[Decoration] = field(default_factory=list)
    comments: str = (
        "Add notes about the situation explored in this scenario. "
        "What are its important details?"
    )
    view_xmin: float = -5.0
    view_xmax: float = 5.0
    unknown_properties: dict[str, str] = field(default_factory=dict)
    selected_name: str | None = None
    def __post_init__(self) -> None:
        """Validate the initial reference-frame velocity."""
        _check_beta(self.beta_rel)
    def set_frame(self, beta: float) -> None:
        """Set the scenario's reference-frame velocity."""
        _check_beta(beta); self.beta_rel = beta
    def coordinates(self, x: float, t: float) -> tuple[float,float]:
        """Transform original-frame coordinates into the current frame."""
        return transform(x, t, self.beta_rel)
    def stepped_time(self, direction: int, step: float = 0.1, tolerance: float = 0.01) -> float:
        """Return the next regular time step or the nearest intervening event."""
        if direction > 0:
            boundary = step * round(self.time / step)
            if boundary <= self.time + 1e-6:
                boundary += step
            candidates = [
                transform(event.x, event.t, self.beta_rel)[1]
                for event in self.events
                if self.time < transform(event.x, event.t, self.beta_rel)[1] < boundary
            ]
            target = min(candidates, default=boundary)
            nearby = [
                transform(event.x, event.t, self.beta_rel)[1]
                for event in self.events
                if self.time < transform(event.x, event.t, self.beta_rel)[1]
                and abs(transform(event.x, event.t, self.beta_rel)[1] - target) < tolerance
            ]
            return max(nearby, default=target)
        boundary = step * round(self.time / step)
        if boundary >= self.time - 1e-6:
            boundary -= step
        candidates = [
            transform(event.x, event.t, self.beta_rel)[1]
            for event in self.events
            if boundary < transform(event.x, event.t, self.beta_rel)[1] < self.time
        ]
        target = max(candidates, default=boundary)
        nearby = [
            transform(event.x, event.t, self.beta_rel)[1]
            for event in self.events
            if transform(event.x, event.t, self.beta_rel)[1] < self.time
            and abs(transform(event.x, event.t, self.beta_rel)[1] - target) < tolerance
        ]
        return min(nearby, default=target)
    def object_state(self, obj: STObject, time: float) -> tuple[float, float]:
        """Return an object's position and beta at a time in this frame."""
        records = [record.in_frame(self.beta_rel) for record in obj.worldline.records]
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
    def set_object_state(self, obj: STObject, time: float, x: float, beta: float) -> None:
        """Replace an object's current worldline state using frame coordinates."""
        if obj.kind != "flash":
            beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, beta))
        _check_beta(beta, allow_light=obj.kind == "flash")
        self._remove_boundary_event(obj, "birth")
        self._remove_boundary_event(obj, "termination")
        self.events = [
            event
            for event in self.events
            if not (event.beta_change and event.object_name == obj.name)
        ]
        obj.programmed = False
        original_x, original_t = inverse_transform(x, time, self.beta_rel)
        original_beta = velocity_add(beta, self.beta_rel)
        if obj.kind == "flash":
            original_beta = 1.0 if original_beta >= 0 else -1.0
        else:
            original_beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, original_beta))
        from .worldline import Worldline, WorldlineRecord
        obj.worldline = Worldline([WorldlineRecord(original_x, original_t, original_beta, original_beta)])
        self.synchronize_intersection_events()

    def _object_state_in_original_frame(self, obj: STObject) -> tuple[float, float, float]:
        """Return an object's current state in the original frame."""
        frame_x, frame_beta = self.object_state(obj, self.time)
        original_x, original_t = inverse_transform(frame_x, self.time, self.beta_rel)
        original_beta = velocity_add(frame_beta, self.beta_rel)
        if obj.kind == "flash":
            original_beta = 1.0 if original_beta >= 0 else -1.0
        return original_x, original_t, original_beta

    def set_birth_here_now(self, obj: STObject) -> None:
        """Set an object's birth point to its current displayed state."""
        original_x, original_t, original_beta = self._object_state_in_original_frame(obj)
        obj.worldline.records = [
            record for record in obj.worldline.records if record.t > original_t + 1e-6
        ]
        obj.worldline.records.append(
            WorldlineRecord(original_x, original_t, original_beta, original_beta)
        )
        obj.worldline.records.sort(key=lambda record: record.t)
        obj.worldline.has_birth = True
        self._set_boundary_event(obj, "birth")

    def set_termination_here_now(self, obj: STObject) -> None:
        """Set an object's termination point to its current displayed state."""
        original_x, original_t, original_beta = self._object_state_in_original_frame(obj)
        obj.worldline.records = [
            record for record in obj.worldline.records if record.t < original_t - 1e-6
        ]
        obj.worldline.records.append(
            WorldlineRecord(original_x, original_t, original_beta, original_beta)
        )
        obj.worldline.records.sort(key=lambda record: record.t)
        obj.worldline.has_termination = True
        self._set_boundary_event(obj, "termination")

    def cancel_birth(self, obj: STObject) -> None:
        """Remove the object's birth constraint."""
        obj.worldline.has_birth = False
        self._remove_boundary_event(obj, "birth")

    def cancel_termination(self, obj: STObject) -> None:
        """Remove the object's termination constraint."""
        obj.worldline.has_termination = False
        self._remove_boundary_event(obj, "termination")

    def _boundary_event(self, obj: STObject, boundary: str) -> Event | None:
        """Return the generated birth or termination event for an object."""
        return next(
            (
                event
                for event in self.events
                if event.boundary == boundary and event.object_name == obj.name
            ),
            None,
        )

    def _remove_boundary_event(self, obj: STObject, boundary: str) -> None:
        """Remove a generated boundary event without affecting user events."""
        self.events = [
            event
            for event in self.events
            if not (event.boundary == boundary and event.object_name == obj.name)
        ]

    def _set_boundary_event(self, obj: STObject, boundary: str, add_note: bool = True) -> None:
        """Create or update the event representing an existence boundary."""
        record = obj.worldline.records[0 if boundary == "birth" else -1]
        verb = "born" if boundary == "birth" else "terminated"
        event = self._boundary_event(obj, boundary)
        if event is None:
            event = next(
                (
                    candidate
                    for candidate in self.events
                    if candidate.boundary is None
                    and candidate.fixed_at_intersection
                    and candidate.intersection_names == (obj.name, obj.name)
                    and abs(candidate.x - record.x) < 1e-6
                    and abs(candidate.t - record.t) < 1e-6
                ),
                None,
            )
        if event is None:
            event = Event(
                name=f"e{boundary.title()}{obj.name}",
                x=record.x,
                t=record.t,
                object_name=obj.name,
                intersection_names=(obj.name, obj.name),
                fixed_at_intersection=True,
            )
            self.events.append(event)
        if not event.label:
            event.label = self._next_event_label()
        event.x = record.x
        event.t = record.t
        if add_note:
            event.note = f"{obj.label} {verb}"
        event.object_name = obj.name
        event.intersection_names = (obj.name, obj.name)
        event.fixed_at_intersection = True
        event.boundary = boundary

    def synchronize_boundary_events(self) -> None:
        """Create missing boundary events for objects loaded with boundary flags."""
        for obj in self.objects:
            if obj.worldline.has_birth:
                self._set_boundary_event(obj, "birth", add_note=False)
            else:
                self._remove_boundary_event(obj, "birth")
            if obj.worldline.has_termination:
                self._set_boundary_event(obj, "termination", add_note=False)
            else:
                self._remove_boundary_event(obj, "termination")

    def program_object(self, obj: STObject) -> None:
        """Make one object the currently programmed object."""
        for other in self.objects:
            other.programmed = other is obj

    def add_programmed_change(self, obj: STObject, time: float, x: float, beta: float) -> None:
        """Add a velocity change while preserving the programmed worldline."""
        if obj.kind != "flash":
            beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, beta))
        _check_beta(beta, allow_light=obj.kind == "flash")
        self.cancel_termination(obj)
        original_x, original_t = inverse_transform(x, time, self.beta_rel)
        original_beta = velocity_add(beta, self.beta_rel)
        if obj.kind == "flash":
            original_beta = 1.0 if original_beta >= 0 else -1.0
        else:
            original_beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, original_beta))
        matching_record = next(
            (
                record
                for record in obj.worldline.records
                if abs(record.t - original_t) <= 1e-6
            ),
            None,
        )
        records = [
            record for record in obj.worldline.records if record.t < original_t - 1e-6
        ]
        old_beta = (
            matching_record.beta_old
            if matching_record is not None
            else obj.worldline.velocity(original_t)
        )
        records.append(WorldlineRecord(original_x, original_t, old_beta, original_beta))
        obj.worldline.records = sorted(records, key=lambda record: record.t)
        self.events = [
            event
            for event in self.events
            if not (
                event.beta_change
                and event.object_name == obj.name
                and event.t >= original_t - 1e-6
            )
        ]
        self.events.append(
            Event(
                name="",
                x=original_x,
                t=original_t,
                object_name=obj.name,
                fixed_at_intersection=True,
                beta_change=True,
            )
        )
        self.relabel_beta_change_events(obj)
        self.synchronize_intersection_events()

    def relabel_beta_change_events(self, obj: STObject) -> None:
        """Renumber beta-change events belonging to an object."""
        changes = sorted(
            (
                event
                for event in self.events
                if event.beta_change and event.object_name == obj.name
            ),
            key=lambda event: event.t,
        )
        for index, event in enumerate(changes, start=1):
            event.label = f"{obj.label}-Δβ{index}"
            event.name = f"eDBeta{obj.name}{index}"

    def synchronize_intersection_events(self) -> None:
        """Move constrained events to their current matching worldlines."""
        for event in self.events:
            if event.placed_at_worldline and event.object_name and not event.boundary:
                try:
                    obj = self.object(event.object_name)
                except KeyError:
                    continue
                frame_t = transform(event.x, event.t, self.beta_rel)[1]
                frame_x, _ = self.object_state(obj, frame_t)
                event.x, event.t = inverse_transform(frame_x, frame_t, self.beta_rel)
                continue
            if (
                not event.fixed_at_intersection
                or event.boundary
                or event.beta_change
                or not event.intersection_names
            ):
                continue
            try:
                first = self.object(event.intersection_names[0])
                second = self.object(event.intersection_names[1])
            except KeyError:
                continue
            hits = first.worldline.intersections(second.worldline)
            if hits:
                event.t, event.x = min(
                    hits,
                    key=lambda hit: abs(hit[0] - event.t),
                )
    def add_clock_in_frame(self, x: float, time: float, beta: float, name: str | None = None) -> Clock:
        """Add a clock using coordinates and velocity in the current frame."""
        original_x, original_t = inverse_transform(x, time, self.beta_rel)
        beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, beta))
        return self.add_clock(original_x, original_t, velocity_add(beta, self.beta_rel), name)
    def add_flash_in_frame(self, x: float, time: float, direction: int = 1, name: str | None = None) -> Flash:
        """Add a light flash using coordinates in the current frame."""
        original_x, original_t = inverse_transform(x, time, self.beta_rel)
        return self.add_flash(original_x, original_t, direction, name)
    def add_clock(self, x: float = 0, t: float = 0, beta: float = 0, name: str | None = None) -> Clock:
        """Add and return a clock in the original frame."""
        beta = max(-MAX_OBJECT_BETA, min(MAX_OBJECT_BETA, beta))
        number = sum(isinstance(o, Clock) for o in self.objects) + 1
        n = name or f"C{number}"
        from .worldline import Worldline, WorldlineRecord
        obj = Clock(
            n,
            n,
            note=f"Clock {number}",
            worldline=Worldline([WorldlineRecord(x, t, beta, beta)]),
        )
        self.objects.append(obj); return obj
    def add_flash(self, x: float = 0, t: float = 0, direction: int = 1, name: str | None = None) -> Flash:
        """Add and return a light flash in the original frame."""
        from .worldline import Worldline, WorldlineRecord
        b = 1.0 if direction >= 0 else -1.0
        number = sum(isinstance(o, Flash) for o in self.objects) + 1
        n = name or f"F{number}"
        obj = Flash(
            n,
            n,
            note=f"Flash {number}",
            worldline=Worldline([WorldlineRecord(x, t, b, b)]),
        )
        self.objects.append(obj); return obj
    def add_event(self, x: float, t: float, name: str | None = None) -> Event:
        """Add and return an event at the given coordinates."""
        automatic_name = name is None
        n = name or self._next_event_label()
        note = f"Event {n[1:]}" if automatic_name and n.startswith("E") else f"Event {len(self.events)+1}"
        event = Event(n, x, t, n, note)
        self.events.append(event)
        return event

    def _next_event_label(self) -> str:
        """Return the next available numbered event label."""
        numbers = []
        for event in self.events:
            for value in (event.name, event.label):
                if value.startswith("E") and value[1:].isdigit():
                    numbers.append(int(value[1:]))
        return f"E{max(numbers, default=0) + 1}"
    def remove_object(self, obj: STObject) -> None:
        """Remove an object and dependent scenario data."""
        if obj in self.objects:
            self.objects.remove(obj)
            self.events = [e for e in self.events if e.object_name != obj.name and not (e.intersection_names and obj.name in e.intersection_names)]
            self.decorations = [d for d in self.decorations if not ((getattr(d, "event", None) and getattr(d, "event", None).name == obj.name))]
            if self.selected_name == obj.name:
                self.selected_name = None
    def remove_event(self, event: Event) -> None:
        """Remove an event and dependent decorations or references."""
        if event in self.events:
            self.events.remove(event)
            self.decorations = [d for d in self.decorations if event not in (getattr(d, "event", None), getattr(d, "first", None), getattr(d, "second", None))]
            for e in self.events:
                if e.object_name == event.name:
                    e.object_name = None
                if e.intersection_names and event.name in e.intersection_names:
                    e.intersection_names = None
    def add_interval(self, first: Event, second: Event) -> Interval:
        """Add and return an interval decoration."""
        d = Interval(name=f"I{len(self.decorations)+1:02d}", first=first, second=second)
        self.decorations.append(d); return d
    def add_light_cone(self, event: Event) -> LightCone:
        """Add and return a light-cone decoration."""
        d = LightCone(name=f"L{len(self.decorations)+1:02d}", event=event)
        self.decorations.append(d); return d
    def add_hyperbola(self, event: Event) -> Hyperbola:
        """Add and return a hyperbola decoration."""
        d = Hyperbola(name=f"H{len(self.decorations)+1:02d}", event=event)
        self.decorations.append(d); return d
    def intersection_event(
        self,
        first: STObject,
        second: STObject,
        name: str | None = None,
        hit: tuple[float, float] | None = None,
    ) -> Event:
        """Create an event at an intersection of two objects."""
        hit = hit or first.worldline.intersection(second.worldline)
        if hit is None:
            raise ValueError("worldlines do not intersect")
        t, x = hit
        event = self.add_event(x, t, name)
        event.fixed_at_intersection = True
        event.intersection_names = (first.name, second.name)
        return event
    def all_intersection_events(
        self,
        first: STObject,
        second: STObject,
    ) -> list[Event]:
        """Create fixed events at every existing-worldline intersection."""
        events = []
        for hit in first.worldline.intersections(second.worldline):
            if first.exists(hit[0]) and second.exists(hit[0]):
                events.append(self.intersection_event(first, second, hit=hit))
        return events
    def worldline_event(
        self,
        obj: STObject,
        frame_time: float,
        name: str | None = None,
    ) -> Event:
        """Create an event on an object's worldline at a current-frame time."""
        frame_x, _ = self.object_state(obj, frame_time)
        x, t = inverse_transform(frame_x, frame_time, self.beta_rel)
        event = self.add_event(x, t, name)
        event.object_name = obj.name
        event.placed_at_worldline = True
        return event
    def clone(self) -> "Scenario":
        """Return an independent deep copy of the scenario."""
        return deepcopy(self)
    def object(self, name: str) -> STObject:
        """Return the object with the specified name."""
        for obj in self.objects:
            if obj.name == name: return obj
        raise KeyError(name)
    def event(self, name: str) -> Event:
        """Return the event with the specified name."""
        for event in self.events:
            if event.name == name: return event
        raise KeyError(name)
