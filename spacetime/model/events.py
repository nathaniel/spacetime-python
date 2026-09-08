"""Events associated with objects and spacetime diagrams."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .objects import STObject

@dataclass
class Event:
    """A named point in spacetime."""

    name: str
    x: float
    t: float
    label: str = ""
    note: str = ""
    object_name: Optional[str] = None
    intersection_names: tuple[str, str] | None = None
    placed_at_worldline: bool = False
    fixed_at_intersection: bool = False
    beta_change: bool = False
    boundary: str | None = None
