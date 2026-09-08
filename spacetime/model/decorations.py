"""Optional spacetime-diagram decorations."""

from __future__ import annotations
from dataclasses import dataclass
from .events import Event
from .lorentz import interval_squared

@dataclass
class Decoration:
    """Base metadata for a diagram decoration."""

    name: str
    kind: str

@dataclass
class Interval(Decoration):
    """Decoration connecting two events."""

    first: Event | None = None
    second: Event | None = None
    kind: str = "interval"
    @property
    def squared(self) -> float:
        """Return the squared spacetime interval between the events."""
        if self.first is None or self.second is None: raise ValueError("interval needs two events")
        return interval_squared(self.second.x-self.first.x, self.second.t-self.first.t)

@dataclass
class LightCone(Decoration):
    """Light cone drawn from an event."""

    event: Event | None = None
    kind: str = "lightcone"

@dataclass
class Hyperbola(Decoration):
    """Constant-proper-time hyperbola from an event."""

    event: Event | None = None
    kind: str = "hyperbola"
    def point(self, proper_time: float, branch: int = 1) -> tuple[float,float]:
        """Return a point on the selected hyperbola branch."""
        if self.event is None: raise ValueError("hyperbola needs an event")
        if proper_time < 0 or branch not in (-1, 1): raise ValueError("invalid hyperbola parameters")
        import math
        return self.event.x + branch*math.sinh(proper_time), self.event.t + math.cosh(proper_time)
