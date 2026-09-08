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
