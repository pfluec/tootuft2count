"""Shared marker-threshold policy for visualization and quantification."""

import math
from collections.abc import Mapping

import numpy as np
from skimage.filters import threshold_otsu


def automatic_threshold(values):
    """Return an Otsu threshold for finite per-cell integrated intensities."""
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if not finite.size:
        return 0.0
    if np.ptp(finite) == 0:
        return float(finite[0])
    return float(threshold_otsu(finite))


def validate_thresholds(thresholds):
    """Normalize a user-supplied marker-to-threshold mapping."""
    if thresholds is not None and not isinstance(thresholds, Mapping):
        raise ValueError("Thresholds must be a marker-to-number object")
    normalized = {}
    for marker, value in (thresholds or {}).items():
        try:
            value = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Threshold for {marker!r} must be numeric") from error
        if not math.isfinite(value):
            raise ValueError(f"Threshold for {marker!r} must be finite")
        if value < 0:
            raise ValueError(f"Threshold for {marker!r} must not be negative")
        normalized[str(marker)] = value
    return normalized


def resolve_thresholds(dataframe, markers, supplied=None):
    """Use supplied values and fill missing marker thresholds with Otsu."""
    resolved = validate_thresholds(supplied)
    for marker in markers:
        column = f"{marker}_sum"
        if marker not in resolved and column in dataframe:
            resolved[marker] = automatic_threshold(dataframe[column].values)
    return resolved
