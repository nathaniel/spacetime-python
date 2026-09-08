"""Tests for loading and saving scenario files."""

from pathlib import Path
import pytest
from spacetime.persistence.scenario_file import load_scenario, save_scenario
from spacetime.model.scenario import Scenario

ROOT=Path(__file__).parents[2]
def test_bundled_scenarios_load():
    """Verify every bundled scenario loads with valid worldlines."""
    files=list((ROOT/"scenarios").glob("*.sce"))
    assert files
    for path in files:
        sc=load_scenario(path)
        assert -1 < sc.beta_rel < 1
        assert all(o.worldline.records for o in sc.objects)

def test_round_trip(tmp_path):
    """Verify saving and loading preserves scenario state."""
    sc=Scenario(beta_rel=.2,time=3); sc.add_clock(1,0,.4); sc.add_event(2,3)
    out=tmp_path/"roundtrip.sce"; save_scenario(sc,out); loaded=load_scenario(out)
    assert loaded.beta_rel==.2 and loaded.time==3
    assert [o.name for o in loaded.objects]==["C1"]
    assert loaded.objects[0].position(2)==pytest.approx(sc.objects[0].position(2))

def test_multiline_comments_round_trip(tmp_path):
    """Verify comments preserve line breaks and literal backslash sequences."""
    sc = Scenario()
    sc.comments = "first line\nsecond line\\ntext"
    out = tmp_path / "comments.sce"
    save_scenario(sc, out)
    loaded = load_scenario(out)
    assert loaded.comments == sc.comments

def test_boundary_event_notes_survive_loading(tmp_path):
    """Preserve notes on generated boundary events when loading a scenario."""
    sc = Scenario(time=1.0)
    clock = sc.add_clock()
    sc.set_birth_here_now(clock)
    boundary = next(event for event in sc.events if event.boundary == "birth")
    boundary.note = "User's custom note"
    out = tmp_path / "boundary-note.sce"
    save_scenario(sc, out)

    loaded = load_scenario(out)
    loaded_boundary = next(event for event in loaded.events if event.boundary == "birth")
    assert loaded_boundary.note == "User's custom note"
