"""Worldline-backed objects shown in a scenario."""

from __future__ import annotations
from dataclasses import dataclass, field
from .lorentz import gamma
from .worldline import Worldline

@dataclass
class STObject:
    """A named object following a piecewise worldline."""

    name: str
    label: str
    note: str = ""
    worldline: Worldline = field(default_factory=Worldline)
    programmed: bool = False
    kind: str = "object"
    def position(self, t: float) -> float:
        """Return the object's position at coordinate time ``t``."""
        return self.worldline.position(t)
    def velocity(self, t: float) -> float:
        """Return the object's velocity at coordinate time ``t``."""
        return self.worldline.velocity(t)
    def exists(self, t: float) -> bool:
        """Return whether the object exists at coordinate time ``t``."""
        return self.worldline.exists(t)
    def clock_reading(self, t: float) -> float:
        """Return elapsed proper time since the worldline began."""
        return self.worldline.proper_time(self.worldline.first_time, t)
    def synchronized_reading(self, t: float) -> float:
        """Return the object's simultaneity-adjusted clock reading."""
        x = self.position(t); b = self.velocity(t)
        return (t - b*x) / ((1-b*b) ** 0.5)

@dataclass
class Clock(STObject):
    """A clock whose reading follows its worldline."""

    kind: str = "clock"

    def clock_reading(self, t: float) -> float:
        """Return the clock reading at coordinate time ``t``."""
        first = self.worldline.records[0]
        initial = gamma(first.beta_old) * (first.t - first.beta_old * first.x)
        if t <= first.t:
            return gamma(first.beta_old) * (t - first.beta_old * self.position(t))
        return initial + self.worldline.proper_time(first.t, t)

@dataclass
class Flash(STObject):
    """A light-speed signal constrained to beta plus or minus one."""

    kind: str = "flash"
    def __post_init__(self) -> None:
        """Validate that every segment travels at light speed."""
        for record in self.worldline.records:
            if abs(abs(record.beta_old)-1) > 1e-12 or abs(abs(record.beta_new)-1) > 1e-12:
                raise ValueError("light flashes must travel at speed 1")
