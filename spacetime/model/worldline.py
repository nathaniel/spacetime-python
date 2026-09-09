"""Piecewise constant-velocity worldlines."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Iterable, List
from .lorentz import gamma, inverse_transform, transform, velocity_add, velocity_in_frame

@dataclass
class WorldlineRecord:
    """A worldline point and the velocity before and after it."""

    x: float
    t: float
    beta_old: float
    beta_new: float
    def __post_init__(self) -> None:
        """Validate coordinates and segment velocities."""
        for value in (self.x, self.t):
            if not math.isfinite(value): raise ValueError("coordinates must be finite")
        for value in (self.beta_old, self.beta_new):
            if not math.isfinite(value) or abs(value) > 1: raise ValueError("velocity must be in [-1, 1]")

    @classmethod
    def from_frame(cls, xp: float, tp: float, old: float, new: float, beta_rel: float) -> "WorldlineRecord":
        """Construct a record from coordinates in another frame."""
        x, t = inverse_transform(xp, tp, beta_rel)
        return cls(x, t, velocity_add(old, beta_rel), velocity_add(new, beta_rel))
    def in_frame(self, beta_rel: float) -> tuple[float, float, float, float]:
        """Return this record expressed in another frame."""
        xp, tp = transform(self.x, self.t, beta_rel)
        return xp, tp, velocity_in_frame(self.beta_old, beta_rel), velocity_in_frame(self.beta_new, beta_rel)

@dataclass
class Worldline:
    """A sorted sequence of piecewise-constant-velocity segments."""

    records: List[WorldlineRecord] = field(default_factory=list)
    has_birth: bool = False
    has_termination: bool = False

    def __post_init__(self) -> None:
        """Ensure a valid initial record and unique record times."""
        if not self.records: self.records.append(WorldlineRecord(0.0, 0.0, 0.0, 0.0))
        self.records.sort(key=lambda r: r.t)
        if any(b.t == a.t for a, b in zip(self.records, self.records[1:])):
            raise ValueError("worldline records must have distinct times")
    @property
    def first_time(self) -> float:
        """Return the first record time."""
        return self.records[0].t
    @property
    def last_time(self) -> float:
        """Return the last record time."""
        return self.records[-1].t
    def _segment(self, t: float) -> WorldlineRecord:
        """Find the segment active at coordinate time ``t``."""
        if t <= self.first_time: return self.records[0]
        for record in reversed(self.records):
            if t >= record.t: return record
        return self.records[0]
    def position(self, t: float) -> float:
        """Return the position at coordinate time ``t``."""
        r = self._segment(t)
        return r.x + r.beta_new * (t - r.t)
    def velocity(self, t: float) -> float:
        """Return the velocity at coordinate time ``t``."""
        return self._segment(t).beta_old if t <= self.first_time else self._segment(t).beta_new
    def exists(self, t: float) -> bool:
        """Return whether the worldline exists at coordinate time ``t``."""
        return (not self.has_birth or t >= self.first_time) and (not self.has_termination or t <= self.last_time)
    def add_change(self, x: float, t: float, old: float | None = None, new: float | None = None) -> WorldlineRecord:
        """Add and return a velocity-change record."""
        prior = self.velocity(t) if old is None else old
        changed = prior if new is None else new
        record = WorldlineRecord(x, t, prior, changed)
        self.records.append(record); self.records.sort(key=lambda r: r.t)
        return record
    def proper_time(self, start: float, end: float) -> float:
        """Integrate proper time between two coordinate times."""
        if end < start: return -self.proper_time(end, start)
        total = 0.0; cursor = start
        points = [r.t for r in self.records if start < r.t < end] + [end]
        for point in points:
            b = self.velocity((cursor + point) / 2)
            total += (point - cursor) / gamma(b)
            cursor = point
        return total
    def intersection(self, other: "Worldline", start: float = -math.inf, end: float = math.inf) -> tuple[float,float] | None:
        """Return the first intersection with another worldline, if any."""
        intersections = self.intersections(other, start, end)
        return intersections[0] if intersections else None

    def intersections(self, other: "Worldline", start: float = -math.inf, end: float = math.inf) -> list[tuple[float, float]]:
        """Return all finite intersections with another worldline."""
        boundaries = sorted({start, end, *[r.t for r in self.records], *[r.t for r in other.records]})
        intersections = []
        for a, b in zip(boundaries, boundaries[1:]):
            if not b > a: continue
            left = max(a, start)
            right = min(b, end)
            if right <= left: continue
            if math.isfinite(left) and math.isfinite(right):
                sample = (left + right) / 2
            elif math.isfinite(right):
                sample = right - 1
            elif math.isfinite(left):
                sample = left + 1
            else:
                continue
            va, vb = self.velocity(sample), other.velocity(sample)
            xa, xb = self.position(sample), other.position(sample)
            if abs(va-vb) < 1e-12:
                if abs(xa-xb) < 1e-9:
                    intersections.append((sample, xa))
                continue
            t = sample + (xb-xa)/(va-vb)
            if left-1e-9 <= t <= right+1e-9:
                hit = (t, self.position(t))
                if not intersections or abs(intersections[-1][0] - hit[0]) > 1e-9:
                    intersections.append(hit)
        return intersections
