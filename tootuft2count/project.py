"""Versioned persistent project state for resumable batch processing."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .grouping import Channel, SampleGroup


SCHEMA_VERSION = 1


@dataclass
class SampleState:
    name: str
    channels: list
    status: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    mask_path: str = ""
    pixel_size_override: float = None
    normalized_path: str = ""
    effective_pixel_size: float = None


@dataclass
class Project:
    root: str
    panel_path: str = ""
    samples: list = field(default_factory=list)
    shared_thresholds: dict = field(default_factory=dict)
    per_image_thresholds: dict = field(default_factory=dict)
    populations: list = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_groups(cls, root, groups, panel_path=""):
        samples = [SampleState(g.name, [asdict(c) for c in g.channels], warnings=g.warnings) for g in groups]
        return cls(str(Path(root).resolve()), str(panel_path), samples)

    def save(self, path=None):
        path = Path(path or Path(self.root) / "tootuft2count_project.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return path

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Unsupported project schema: {data.get('schema_version')}")
        data["samples"] = [SampleState(**sample) for sample in data.get("samples", [])]
        return cls(**data)
