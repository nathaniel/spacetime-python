"""Model-independent commands used to edit scenarios."""

from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
from collections.abc import Callable
from typing import Protocol
from ..model.scenario import Scenario
from ..model.objects import STObject
from ..model.events import Event

class Command(Protocol):
    """Protocol implemented by reversible commands."""

    def execute(self) -> None:
        """Apply the command."""
        ...
    def undo(self) -> None:
        """Reverse the command."""
        ...

class History:
    """Track executed commands and their redo history."""

    def __init__(self) -> None:
        """Initialize empty undo and redo stacks."""
        self._undo: list[Command] = []; self._redo: list[Command] = []
    def do(self, command: Command) -> None:
        """Execute a command and record it for undo."""
        command.execute(); self._undo.append(command); self._redo.clear()
    def undo(self) -> bool:
        """Undo the most recent command, if available."""
        if not self._undo: return False
        c=self._undo.pop(); c.undo(); self._redo.append(c); return True
    def redo(self) -> bool:
        """Redo the most recently undone command, if available."""
        if not self._redo: return False
        c=self._redo.pop(); c.execute(); self._undo.append(c); return True
    @property
    def can_undo(self) -> bool:
        """Whether an undo operation is available."""
        return bool(self._undo)
    @property
    def can_redo(self) -> bool:
        """Whether a redo operation is available."""
        return bool(self._redo)

@dataclass
class Snapshot:
    """Undoable mutation for a model object, independent of Qt."""
    target: object
    mutate: Callable[[], None]
    before: object | None = None
    after: object | None = None
    def execute(self) -> None:
        """Apply the mutation or restore its captured after-state."""
        if self.before is None:
            self.before = deepcopy(self.target)
            self.mutate()
            self.after = deepcopy(self.target)
        else:
            self._restore(self.after)
    def undo(self) -> None:
        """Restore the captured before-state."""
        self._restore(self.before)
    def _restore(self, value: object | None) -> None:
        """Copy a saved object's state back into the target."""
        if value is None: return
        self.target.__dict__.clear()
        self.target.__dict__.update(deepcopy(value.__dict__))

@dataclass
class DeleteObject:
    """Command that removes an object from a scenario."""
    scenario: Scenario; object: STObject
    def execute(self) -> None:
        """Remove the object."""
        self.scenario.remove_object(self.object)
    def undo(self) -> None:
        """Restore the object if it is absent."""
        if self.object not in self.scenario.objects: self.scenario.objects.append(self.object)

@dataclass
class DeleteEvent:
    """Command that removes an event from a scenario."""
    scenario: Scenario; event: Event
    def execute(self) -> None:
        """Remove the event."""
        self.scenario.remove_event(self.event)
    def undo(self) -> None:
        """Restore the event if it is absent."""
        if self.event not in self.scenario.events: self.scenario.events.append(self.event)

@dataclass
class SetTime:
    """Command that changes the scenario time."""
    scenario: Scenario; value: float; old: float | None = None
    def execute(self) -> None:
        """Set the scenario time while saving the previous value."""
        self.old=self.scenario.time; self.scenario.time=self.value
    def undo(self) -> None:
        """Restore the previous scenario time."""
        if self.old is not None: self.scenario.time=self.old

@dataclass
class SetFrame:
    """Command that changes the scenario reference frame."""
    scenario: Scenario; value: float; old: float | None = None
    def execute(self) -> None:
        """Set the frame while saving the previous value."""
        self.old=self.scenario.beta_rel; self.scenario.set_frame(self.value)
    def undo(self) -> None:
        """Restore the previous reference frame."""
        if self.old is not None: self.scenario.set_frame(self.old)

@dataclass
class ProgramObject:
    """Command that programs one object and preserves prior states."""
    scenario: Scenario
    object: STObject
    old_states: dict[int, tuple[STObject, bool, bool]] | None = None

    def execute(self) -> None:
        """Program the selected object."""
        if self.old_states is None:
            self.old_states = {
                id(obj): (obj, obj.programmed, obj.worldline.has_termination)
                for obj in self.scenario.objects
            }
        self.scenario.program_object(self.object)

    def undo(self) -> None:
        """Restore each object's prior programmed state."""
        if self.old_states is None:
            return
        for obj, programmed, has_termination in self.old_states.values():
            obj.programmed = programmed
            obj.worldline.has_termination = has_termination

@dataclass
class AddObject:
    """Command that adds an object to a scenario."""
    scenario: Scenario; object: STObject
    def execute(self) -> None:
        """Add the object if it is not already present."""
        if self.object not in self.scenario.objects: self.scenario.objects.append(self.object)
    def undo(self) -> None:
        """Remove the object if it is present."""
        if self.object in self.scenario.objects: self.scenario.objects.remove(self.object)

@dataclass
class AddEvent:
    """Command that adds an event to a scenario."""
    scenario: Scenario; event: Event
    def execute(self) -> None:
        """Add the event if it is not already present."""
        if self.event not in self.scenario.events: self.scenario.events.append(self.event)
    def undo(self) -> None:
        """Remove the event if it is present."""
        if self.event in self.scenario.events: self.scenario.events.remove(self.event)
