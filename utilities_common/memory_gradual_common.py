"""
Shared utilities for memory gradual increase detection.

Used by both memory_gradual_check.py (checker) and memory_gradual_handler.py (handler).
"""

import json
import math
import os
from collections import namedtuple
from typing import Callable, Dict, List, Optional, Tuple

try:
    from statistics import correlation, linear_regression as stats_linreg
except ImportError:
    _LinearRegression = namedtuple('LinearRegression', ['slope', 'intercept'])

    def stats_linreg(x, y):
        n = len(x)
        xbar = sum(x) / n
        ybar = sum(y) / n
        slope_num = sum((xi - xbar) * (yi - ybar) for xi, yi in zip(x, y))
        slope_den = sum((xi - xbar) ** 2 for xi in x)
        if slope_den == 0:
            raise ValueError("x is constant")
        slope = slope_num / slope_den
        return _LinearRegression(slope=slope, intercept=ybar - slope * xbar)

    def correlation(x, y):
        n = len(x)
        xbar = sum(x) / n
        ybar = sum(y) / n
        num = sum((xi - xbar) * (yi - ybar) for xi, yi in zip(x, y))
        den = math.sqrt(
            sum((xi - xbar) ** 2 for xi in x) *
            sum((yi - ybar) ** 2 for yi in y)
        )
        if den == 0:
            raise ValueError("correlation requires that the data is not constant")
        return num / den

STATE_DIR = "/var/run"


def get_state_file_path(scale: str) -> str:
    """Get the state file path for a given scale."""
    return os.path.join(STATE_DIR, f"memory_gradual_{scale}.json")


def load_state(state_file: str, log_fn: Optional[Callable[[str], None]] = None) -> Optional[Dict]:
    """
    Load state from JSON file.

    Args:
        state_file: Path to the JSON state file.
        log_fn: Optional logging callback for error reporting.
                 Checker passes log_warning, handler passes log_error.
    """
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        if log_fn:
            log_fn(f"Failed to load state file {state_file}: {e}")
        return None


def linear_regression(y_values: List[float]) -> Tuple[float, float, float]:
    """
    Perform linear regression on a series of values.

    Uses x = [0, 1, 2, ..., n-1] as the independent variable.
    Uses statistics.linear_regression() and statistics.correlation() from stdlib
    (Python 3.10+), with a manual fallback for older interpreters.

    Args:
        y_values: List of dependent variable values (e.g., memory readings)

    Returns:
        Tuple of (slope, intercept, r_squared)
        - slope: Rate of change per unit x
        - intercept: y value when x=0
        - r_squared: Coefficient of determination (0.0 to 1.0)
    """
    n = len(y_values)
    if n < 2:
        return 0.0, y_values[0] if y_values else 0.0, 0.0

    x_values = list(range(n))

    result = stats_linreg(x_values, y_values)
    slope = result.slope
    intercept = result.intercept

    try:
        r = correlation(x_values, y_values)
        r_squared = r ** 2
    except Exception:
        r_squared = 1.0 if slope == 0 else 0.0

    return slope, intercept, r_squared
