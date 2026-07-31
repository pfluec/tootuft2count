# tootuft2count

`tootuft2count` is a modular and extensible pipeline for counting tuft cells (or any cell type) in immunofluorescence images. It allows to go from raw TIFF stacks to single-cell data using a **fully scriptable and inspectable CLI**, with napari support for interactive visualization.
![alt text](https://github.com/pfluec/tootuft2count/blob/main/raw_images/Figure1_400.png)

---

## Features

- Combine single-channel TIFFs into multi-channel images
- Run **cell segmentation** via InstanSeg 
- Measure **per-cell marker intensities** 
- Export **CSV + FCS** files for each image
- Interactively **gate and threshold** via Napari or FlowJo
- Quantify marker-positive cells (with or without DAPI restriction)
- Share thresholds across datasets for reproducibility
- CLI-friendly: `tootuft2count combine ...` through `quantify ...`
- A resumable napari batch workflow for TIFF directories
- Metadata-aware normalization to 0.5 µm/pixel before segmentation

---

## Directory structure

```bash
project_root/
├── raw_images/                  # Folder containing input single-channel TIFF images
│   ├── Sample1_Channel1.tif
│   ├── Sample1_Channel2.tif
│   └── ...
├── img/                       # Optional folder containing images as .tif stacks
├── masks/                     # Optional folder containing segmentation masks from other segmentation model
├── model/                     # Optional folder containing a pretrained model
└── panel.csv                  # CSV file mapping channel numbers to marker names
```
---

## Example Workflow

Assuming your individual single-channel images are in `raw_images/`, and you’ve defined a `panel.csv`:

```bash
tootuft2count combine raw_images img
tootuft2count segment img masks
tootuft2count measure img masks --panel panel.csv
tootuft2count visualize sample1 --panel panel.csv
tootuft2count quantify --panel panel.csv --use-manual-thresholds --threshold-source-image sample1
```

## Napari batch GUI

Launch the project workflow from a terminal:

```bash
tootuft2count gui
```

Drop a directory containing `.tif`/`.tiff` files and a `panel.csv` onto the
workflow panel. Files with common channel suffixes such as `_ch00`, `_ch1`,
`_channel02`, or `_c3` are detected as samples and shown in an editable batch
table. Only the selected sample is loaded into napari; the remaining samples
stay in the persisted project queue. Select no rows to run the entire batch, or
select rows to process only those samples.

The workflow saves `tootuft2count_project.json` beside the output directories,
so completed stages and errors can be reviewed after the application closes.
Original inputs are never changed. Normalized OME-TIFF images are written to
`img/`, masks to `masks/`, measurements to `csv/` and `fcs/`, and summaries to
`results/`.

### Physical pixel sizes

OME physical sizes take priority over TIFF resolution tags with recognized
units. Images finer than 0.5 µm/pixel are downsampled to 0.5 µm/pixel with
anti-aliasing before segmentation and measurement. Images at 0.5 µm/pixel or
coarser are not enlarged. Missing metadata disables automatic resampling and
causes the segmentation pixel-size argument to be omitted. X/Y sizes differing
by more than 1% are treated as anisotropic and are not resampled unless the user
enters a single trusted pixel-size override.

The first GUI release deliberately supports two-dimensional TIFF data and
InstanSeg or supplied masks. CZI, LIF, Z/time processing, and Cellpose are out of
scope for this release.

---

## Input Requirements

### `panel.csv`

This file defines which image channel corresponds to which marker:

| channel | marker   |
|---------|----------|
| 0       | DAPI     |
| 1       | EpCAM    |
| 2       | DCLK1    |
| 3       | SiglecF  |

### TIFF images

- Expected format: `.tif` or `.tiff`
- Combined TIFFs should have shape: `(C, H, W)` or `(H, W, C)` depending on backend
- Segmentation masks should be label images with unique integer IDs

---

##  Installation

Python 3.9-3.11 is required for the package to run. We recommend creating a clean conda environment:

```bash
conda create -n tootuft2count python=3.11
conda activate tootuft2count
```

And then install via pip from PyPI:

```bash
pip install tootuft2count
```

Or install in editable mode from source:

```bash
git clone https://github.com/pfluec/tootuft2count.git
cd tootuft2count
pip install -e .
```

---

## Commands

| Command    | Description                                         |
|------------|-----------------------------------------------------|
| `combine`  | Stack single-channel TIFFs into multi-channel images |
| `segment`  | Run segmentation (InstanSeg)                        |
| `measure`  | Extract per-cell intensities + export to CSV/FCS    |
| `visualize`| Napari-based GUI for interactive threshold tuning   |
| `quantify` | Compute marker+ and double-positive cell types      |

Run `tootuft2count [command] --help` to view CLI options.

---

## GUI-Based Thresholding

The `visualize` command launches a Napari window to:
- Adjust marker thresholds interactively
- See point overlays and cell label masks update in real-time
- Save threshold profiles to reuse across images

---

## Outputs

- Per-cell CSVs (intensities, areas, regionprops)
- Individual and merged `.fcs` files for analysis in FlowJo
- Quantification summaries (CSV) per image
- `_thresholds.json` files for reproducible gating

---

## License

MIT License

---

## Citation / Attribution

If you use `tootuft2count` in your work, please cite the GitHub repository.
