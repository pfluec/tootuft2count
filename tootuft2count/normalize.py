"""Normalize TIFF groups and conservatively downsample physical resolution."""

from pathlib import Path

import numpy as np
import tifffile
from skimage.transform import resize

from .metadata import inspect_tiff


TARGET_PIXEL_SIZE = 0.5
ANISOTROPY_TOLERANCE = 0.01


def resampling_decision(pixel_x, pixel_y, override=None):
    if override is not None:
        pixel_x = pixel_y = float(override)
    if pixel_x is None or pixel_y is None:
        return 1.0, None, "missing pixel metadata"
    if abs(pixel_x - pixel_y) / max(pixel_x, pixel_y) > ANISOTROPY_TOLERANCE:
        return 1.0, None, "anisotropic pixels exceed 1%; supply a single override to resample"
    source = (pixel_x + pixel_y) / 2
    if source >= TARGET_PIXEL_SIZE:
        return 1.0, source, "source resolution retained"
    return source / TARGET_PIXEL_SIZE, TARGET_PIXEL_SIZE, "downsampled"


def _read_channel(channel):
    array = tifffile.imread(channel["path"])
    metadata = inspect_tiff(channel["path"])
    if metadata.channel_count > 1:
        axis = metadata.axes.index("C") if "C" in metadata.axes else metadata.axes.index("S")
        array = np.take(array, channel["index"], axis=axis)
    return np.squeeze(array), metadata


def normalize_sample(sample, output_dir, progress=None):
    included = [channel for channel in sample.channels if channel.get("included", True)]
    if not included:
        raise ValueError(f"Sample {sample.name} has no included channels")
    arrays, metadata = [], None
    for number, channel in enumerate(included, 1):
        array, current = _read_channel(channel)
        if array.ndim != 2:
            raise ValueError(f"Only 2-D channels are supported: {channel['path']}")
        if arrays and array.shape != arrays[0].shape:
            raise ValueError(f"Channel dimensions do not match in sample {sample.name}")
        arrays.append(array)
        metadata = metadata or current
        if progress:
            progress(number, len(included), f"Reading {Path(channel['path']).name}")
    scale, effective, reason = resampling_decision(metadata.pixel_size_x, metadata.pixel_size_y, sample.pixel_size_override)
    if scale < 1:
        shape = tuple(max(1, int(round(length * scale))) for length in arrays[0].shape)
        converted = []
        for array in arrays:
            result = resize(array, shape, order=1, anti_aliasing=True, preserve_range=True)
            if np.issubdtype(array.dtype, np.integer):
                limits = np.iinfo(array.dtype)
                result = np.clip(np.rint(result), limits.min, limits.max)
            converted.append(result.astype(array.dtype))
        arrays = converted
    stack = np.stack(arrays) if len(arrays) > 1 else arrays[0]
    output = Path(output_dir) / f"{sample.name}.tiff"
    output.parent.mkdir(parents=True, exist_ok=True)
    markers = [channel["marker"] for channel in included]
    metadata_out = {"axes": "CYX", "Channel": {"Name": markers}} if len(arrays) > 1 else {"axes": "YX"}
    if effective is not None:
        metadata_out.update({"PhysicalSizeX": effective, "PhysicalSizeXUnit": "µm", "PhysicalSizeY": effective, "PhysicalSizeYUnit": "µm"})
    tifffile.imwrite(output, stack, ome=True, metadata=metadata_out)
    sample.normalized_path = str(output)
    sample.effective_pixel_size = effective
    sample.status["normalize"] = "complete"
    if reason not in {"downsampled", "source resolution retained"}:
        sample.warnings.append(reason)
    return output, reason
