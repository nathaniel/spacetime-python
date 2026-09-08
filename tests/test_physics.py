"""Tests for Lorentz transformations and worldline physics."""

import math
import pytest
from spacetime.model.lorentz import gamma, transform, inverse_transform, velocity_add, classify_interval
from spacetime.model.worldline import Worldline, WorldlineRecord

def test_lorentz_round_trip_and_interval():
    """Verify coordinate transforms and interval classification."""
    x,t=transform(3,5,.6)
    assert inverse_transform(x,t,.6)==pytest.approx((3,5))
    assert classify_interval(0,2)=="timelike"
    assert gamma(.6)==pytest.approx(1.25)

def test_velocity_addition_and_validation():
    """Verify relativistic velocity addition and validation."""
    assert velocity_add(.5,.5)==pytest.approx(.8)
    assert velocity_add(.999999,.999999)<1
    with pytest.raises(ValueError): gamma(1)

def test_piecewise_worldline_proper_time_and_intersection():
    """Verify piecewise motion, proper time, and intersections."""
    w=Worldline([WorldlineRecord(0,0,0,0),WorldlineRecord(2,2,0,.6)])
    assert w.position(3)==pytest.approx(2.6)
    assert w.proper_time(0,2)==pytest.approx(2)
    assert w.proper_time(2,3)==pytest.approx(.8)
    other=Worldline([WorldlineRecord(3,0,0,0)])
    assert w.intersection(other)==pytest.approx((11/3,3))
