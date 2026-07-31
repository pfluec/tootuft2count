"""Discover and edit logical samples made from TIFF files."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .metadata import inspect_tiff


CHANNEL_RE = re.compile(r"(?i)(?P<prefix>.*?)(?:[_-](?:ch(?:annel)?|c))(?P<channel>\d+)$")


@dataclass
class Channel:
    path: str
    index: int
    marker: str
    included: bool = True


@dataclass
class SampleGroup:
    name: str
    channels: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def discover_groups(directory, recursive=True):
    """Return deterministic, reviewable TIFF groups from *directory*."""
    root = Path(directory)
    files = sorted(
        (p for p in (root.rglob("*") if recursive else root.glob("*")) if p.is_file() and p.suffix.lower() in {".tif", ".tiff"}),
        key=lambda p: str(p).lower(),
    )
    groups = {}
    for path in files:
        metadata = inspect_tiff(path)
        stem_match = CHANNEL_RE.match(path.stem)
        if metadata.channel_count > 1:
            name = path.stem
            group = groups.setdefault(str(path.parent / name), SampleGroup(name))
            for index, marker in enumerate(metadata.channel_names):
                group.channels.append(Channel(str(path), index, marker))
            continue
        if stem_match:
            name = stem_match.group("prefix").rstrip("_-")
            index = int(stem_match.group("channel"))
        else:
            name, index = path.stem, 0
        key = str(path.parent / name)
        groups.setdefault(key, SampleGroup(name)).channels.append(Channel(str(path), index, f"ch{index}"))

    result = list(groups.values())
    for group in result:
        group.channels.sort(key=lambda channel: (channel.index, channel.path.lower()))
        indices = [channel.index for channel in group.channels]
        if len(indices) != len(set(indices)):
            group.warnings.append("Duplicate channel indices require review.")
    return result

