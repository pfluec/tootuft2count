"""Metadata-aware readers for the two-dimensional TIFF workflow."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

import tifffile


@dataclass
class ImageMetadata:
    path: Path
    shape: Tuple[int, ...]
    axes: str
    dtype: str
    channel_count: int
    pixel_size_x: Optional[float] = None
    pixel_size_y: Optional[float] = None
    pixel_size_source: Optional[str] = None
    channel_names: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def spatial_shape(self):
        return (self.shape[self.axes.index("Y")], self.shape[self.axes.index("X")])


def _ome_metadata(series, ome_xml):
    x = y = None
    names = []
    if not ome_xml:
        return x, y, names
    try:
        from xml.etree import ElementTree

        root = ElementTree.fromstring(ome_xml)
        pixels = next(node for node in root.iter() if node.tag.endswith("Pixels"))
        x = float(pixels.attrib["PhysicalSizeX"]) if "PhysicalSizeX" in pixels.attrib else None
        y = float(pixels.attrib["PhysicalSizeY"]) if "PhysicalSizeY" in pixels.attrib else None
        names = [node.attrib.get("Name", f"ch{i}") for i, node in enumerate(pixels) if node.tag.endswith("Channel")]
    except (ValueError, KeyError, StopIteration, ElementTree.ParseError):
        pass
    return x, y, names


def inspect_tiff(path):
    """Inspect a 2-D or multichannel 2-D TIFF without reading its pixels."""
    path = Path(path)
    with tifffile.TiffFile(path) as tif:
        series = tif.series[0]
        axes = series.axes
        shape = tuple(series.shape)
        x, y, names = _ome_metadata(series, tif.ome_metadata)
        source = "OME metadata" if x is not None and y is not None else None
        warnings = []
        if x is None or y is None:
            page = series.pages[0]
            unit = page.tags.get("ResolutionUnit")
            unit_value = unit.value if unit else None
            if unit_value in (2, 3, "INCH", "CENTIMETER"):
                factor = 25400.0 if unit_value in (2, "INCH") else 10000.0
                try:
                    xr = page.tags["XResolution"].value
                    yr = page.tags["YResolution"].value
                    x = factor / (xr[0] / xr[1])
                    y = factor / (yr[0] / yr[1])
                    source = "TIFF resolution tags"
                except (KeyError, ZeroDivisionError, TypeError):
                    x = y = None
        if x is None or y is None:
            warnings.append("No trustworthy physical pixel size was found; automatic resampling is disabled.")

    unsupported = {axis for axis, length in zip(axes, shape) if axis in "TZ" and length > 1}
    if unsupported:
        raise ValueError(f"Unsupported non-2D axes in {path.name}: {axes} {shape}")
    channel_count = shape[axes.index("C")] if "C" in axes else (shape[axes.index("S")] if "S" in axes else 1)
    if not names:
        names = [f"ch{i}" for i in range(channel_count)]
    return ImageMetadata(path, shape, axes, str(series.dtype), channel_count, x, y, source, names, warnings)

