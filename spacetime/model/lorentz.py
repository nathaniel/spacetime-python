"""One-dimensional special-relativity calculations, with c=1."""
from __future__ import annotations
import math
from typing import Tuple

def _check_beta(beta: float, *, allow_light: bool = False) -> None:
    """Validate a velocity against the allowed relativistic range."""
    limit = 1 if allow_light else (1 - 1e-15)
    if not math.isfinite(beta) or abs(beta) > limit:
        raise ValueError("velocity must be finite and have absolute value <= 1" if allow_light else "velocity must be finite and have absolute value < 1")

def gamma(beta: float) -> float:
    """Return the Lorentz factor for a subluminal velocity."""
    _check_beta(beta)
    return 1.0 / math.sqrt(1.0 - beta * beta)

def transform(x: float, t: float, beta: float) -> Tuple[float, float]:
    """Coordinates in a frame moving at beta relative to the original frame."""
    _check_beta(beta)
    g = gamma(beta)
    return g * (x - beta * t), g * (t - beta * x)

def inverse_transform(xp: float, tp: float, beta: float) -> Tuple[float, float]:
    """Transform coordinates back to the original frame."""
    _check_beta(beta)
    return transform(xp, tp, -beta)

def velocity_add(u: float, v: float) -> float:
    """Velocity u measured in a frame moving at v, expressed in the original."""
    _check_beta(u, allow_light=True); _check_beta(v)
    result = (u + v) / (1 + u * v)
    return max(-1.0, min(1.0, result))

def velocity_in_frame(beta: float, frame_beta: float) -> float:
    """Express an original-frame velocity in a frame moving at frame_beta."""
    _check_beta(beta, allow_light=True)
    _check_beta(frame_beta)
    result = (beta - frame_beta) / (1.0 - beta * frame_beta)
    return max(-1.0, min(1.0, result))

def interval_squared(dx: float, dt: float) -> float:
    """Return the Minkowski interval squared using c=1."""
    return dt * dt - dx * dx

def classify_interval(dx: float, dt: float, tolerance: float = 1e-10) -> str:
    """Classify a spacetime interval as timelike, lightlike, or spacelike."""
    s = interval_squared(dx, dt)
    if abs(s) <= tolerance:
        return "lightlike"
    return "timelike" if s > 0 else "spacelike"
