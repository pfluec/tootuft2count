"""Batch orchestration shared by the GUI and programmatic users."""

from pathlib import Path
import shutil
from time import monotonic

import pandas as pd

from .measure import measure_intensities
from .normalize import normalize_sample
from .quantify import quantify_cells
from .segment import segment_images


class PipelineRunner:
    def __init__(self, project, progress=None, cancelled=None):
        self.project = project
        self.progress = progress or (lambda *args: None)
        self.cancelled = cancelled or (lambda: False)

    def run(self, stages=("normalize", "segment", "measure", "quantify"), samples=None):
        selected = samples or self.project.samples
        root = Path(self.project.root)
        started = monotonic()
        for index, sample in enumerate(selected):
            if self.cancelled(): break
            estimate = ((monotonic() - started) / index * (len(selected) - index)) if index else None
            try:
                panel_path = root / ".tootuft2count" / "panels" / f"{sample.name}.csv"
                panel_path.parent.mkdir(parents=True, exist_ok=True)
                markers = [channel["marker"] for channel in sample.channels if channel.get("included", True)]
                pd.DataFrame({"channel": range(len(markers)), "marker": markers}).to_csv(panel_path, index=False)
                if "normalize" in stages:
                    self.progress(index, len(selected), sample.name, "normalize", estimate)
                    normalize_sample(sample, root / "img")
                if "segment" in stages and not sample.mask_path:
                    self.progress(index, len(selected), sample.name, "segment", estimate)
                    segment_images(str(root / "img"), str(root / "masks"), filenames=[f"{sample.name}.tiff"], pixel_size=sample.effective_pixel_size)
                    sample.status["segment"] = "complete"
                elif sample.mask_path:
                    destination = root / "masks" / f"{sample.name}.tiff"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sample.mask_path, destination)
                    sample.status["segment"] = "supplied mask"
                if "measure" in stages:
                    self.progress(index, len(selected), sample.name, "measure", estimate)
                    measure_intensities(str(root / "img"), str(root / "masks"), str(root / "csv"), str(root / "fcs"), str(root / "all_images_fcs" / "combined.fcs"), str(panel_path), filenames=[f"{sample.name}.tiff"])
                    sample.status["measure"] = "complete"
                if "quantify" in stages:
                    self.progress(index, len(selected), sample.name, "quantify", estimate)
                    quantify_cells(str(root / "csv"), str(root / "results"), str(panel_path), filenames=[f"{sample.name}.csv"], populations=self.project.populations)
                    sample.status["quantify"] = "complete"
            except Exception as error:
                sample.status["error"] = str(error)
            finally:
                self.project.save()
        self.progress(len(selected), len(selected), "", "complete", monotonic() - started)
