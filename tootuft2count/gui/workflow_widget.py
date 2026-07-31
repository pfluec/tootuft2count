"""Dockable batch workflow UI for napari."""

from pathlib import Path

import pandas as pd
from qtpy.QtCore import QThread, Signal
from qtpy.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QLabel,
                            QMessageBox, QProgressBar, QPushButton, QTableWidget,
                            QTableWidgetItem, QVBoxLayout, QWidget)

from ..grouping import discover_groups
from ..pipeline import PipelineRunner
from ..project import Project


class PipelineWorker(QThread):
    progress = Signal(int, int, str, str, object)
    finished_with_project = Signal(object)

    def __init__(self, project, samples):
        super().__init__()
        self.project, self.samples, self._cancel = project, samples, False

    def cancel(self): self._cancel = True

    def run(self):
        PipelineRunner(self.project, self.progress.emit, lambda: self._cancel).run(samples=self.samples)
        self.finished_with_project.emit(self.project)


class WorkflowWidget(QWidget):
    """Manage many images in a table while displaying only the selected one."""

    def __init__(self, viewer=None):
        super().__init__()
        self.viewer, self.project, self.worker = viewer, None, None
        self.setAcceptDrops(True)
        self.setLayout(QVBoxLayout())
        self.drop_label = QLabel("Drop a TIFF directory and panel.csv here")
        self.layout().addWidget(self.drop_label)
        buttons = QHBoxLayout()
        self.open_button, self.panel_button = QPushButton("Open directory"), QPushButton("Choose panel")
        buttons.addWidget(self.open_button); buttons.addWidget(self.panel_button)
        self.layout().addLayout(buttons)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Sample", "Included markers (comma-separated)", "Pixel override (µm)", "Normalize", "Segment", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layout().addWidget(self.table)
        actions = QHBoxLayout()
        self.run_button, self.cancel_button = QPushButton("Run selected / all"), QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.run_button); actions.addWidget(self.cancel_button)
        self.layout().addLayout(actions)
        self.progress = QProgressBar(); self.eta = QLabel("ETA: waiting")
        self.layout().addWidget(self.progress); self.layout().addWidget(self.eta)
        self.open_button.clicked.connect(self.choose_directory)
        self.panel_button.clicked.connect(self.choose_panel)
        self.run_button.clicked.connect(self.run_pipeline)
        self.cancel_button.clicked.connect(lambda: self.worker and self.worker.cancel())
        self.table.itemSelectionChanged.connect(self.show_selected)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir(): self.load_directory(path)
            elif path.name.lower() == "panel.csv": self.set_panel(path)

    def choose_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Choose TIFF directory")
        if path: self.load_directory(path)

    def choose_panel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose panel", filter="CSV (*.csv)")
        if path: self.set_panel(path)

    def load_directory(self, path):
        groups = discover_groups(path)
        self.project = Project.from_groups(Path(path).parent, groups, self.project.panel_path if self.project else "")
        self.project.save(); self.refresh()

    def set_panel(self, path):
        panel = pd.read_csv(path)
        if not {"channel", "marker"}.issubset(panel.columns):
            QMessageBox.warning(self, "Invalid panel", "panel.csv must contain channel and marker columns")
            return
        if not self.project:
            self.project = Project(str(Path(path).parent), str(path))
        self.project.panel_path = str(path)
        markers = dict(zip(panel.channel.astype(int), panel.marker.astype(str)))
        for sample in self.project.samples:
            for channel in sample.channels:
                channel["marker"] = markers.get(channel["index"], channel["marker"])
        self.project.save(); self.refresh()

    def refresh(self):
        if not self.project: return
        self.table.setRowCount(len(self.project.samples))
        for row, sample in enumerate(self.project.samples):
            values = [sample.name, ", ".join(c["marker"] for c in sample.channels if c.get("included", True)), str(sample.pixel_size_override or ""), sample.status.get("normalize", "pending"), sample.status.get("segment", "pending"), sample.status.get("error", sample.status.get("quantify", "pending"))]
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(value))

    def _sync_edits(self):
        for row, sample in enumerate(self.project.samples):
            sample.name = self.table.item(row, 0).text().strip()
            markers = [value.strip() for value in self.table.item(row, 1).text().split(",") if value.strip()]
            for index, channel in enumerate(sample.channels):
                channel["included"] = index < len(markers)
                if channel["included"]:
                    channel["marker"] = markers[index]
            raw = self.table.item(row, 2).text().strip()
            sample.pixel_size_override = float(raw) if raw else None

    def selected_samples(self):
        rows = sorted({item.row() for item in self.table.selectedItems()})
        return [self.project.samples[row] for row in rows] or self.project.samples

    def run_pipeline(self):
        if not self.project or not self.project.panel_path:
            QMessageBox.warning(self, "Configuration incomplete", "Choose a TIFF directory and panel.csv first.")
            return
        self._sync_edits(); self.worker = PipelineWorker(self.project, self.selected_samples())
        self.worker.progress.connect(self.update_progress); self.worker.finished_with_project.connect(self.finished)
        self.run_button.setEnabled(False); self.cancel_button.setEnabled(True); self.worker.start()

    def update_progress(self, done, total, sample, stage, estimate):
        self.progress.setMaximum(max(1, total)); self.progress.setValue(done)
        if stage == "complete":
            self.eta.setText(f"Complete in {estimate:.1f}s")
        else:
            eta = "calculating" if estimate is None else f"{estimate:.1f}s"
            self.eta.setText(f"{stage}: {sample} — ETA {eta}")

    def finished(self, project):
        self.project = project; self.run_button.setEnabled(True); self.cancel_button.setEnabled(False); self.refresh()

    def show_selected(self):
        if not self.viewer or not self.project or not self.table.selectedItems(): return
        sample = self.project.samples[self.table.selectedItems()[0].row()]
        if sample.normalized_path and Path(sample.normalized_path).exists():
            import tifffile
            for name in ("Workflow image", "Workflow labels"):
                if name in self.viewer.layers: self.viewer.layers.remove(name)
            self.viewer.add_image(tifffile.imread(sample.normalized_path), channel_axis=0, name="Workflow image")
