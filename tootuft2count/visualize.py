import os
import json
import pandas as pd
import numpy as np
import tifffile as tf
from scipy.ndimage import label
from skimage.filters import threshold_otsu
import napari
from magicgui.widgets import VBox, PushButton, CheckBox, FloatSlider
import glob


def launch_viewer(image_path, label_path, csv_path, panel=None, threshold_json_out=None,
                  use_manual_thresholds=False, threshold_source_image=None):
    """
    Launches a Napari GUI to interactively inspect marker intensities and adjust thresholds.

    Arguments:
    - image_path: path to multi-channel TIFF image
    - label_path: path to corresponding label mask
    - csv_path: path to per-cell measurement CSV
    - panel: path to panel.csv to define marker names (required)
    - threshold_json_out: path to save threshold values set in the GUI
    - use_manual_thresholds: whether to load thresholds from a saved *_thresholds.json
    - threshold_source_image: base image name used to identify the JSON file to load

    The GUI includes per-marker sliders, DAPI gating, identity visualization, and export buttons.
    """

    df = pd.read_csv(csv_path)
    orig_img = tf.imread(image_path)
    label_img = tf.imread(label_path)
    labeled_image, _ = label(label_img)

    # Load panel
    if panel and os.path.exists(panel):
        panel_df = pd.read_csv(panel)
        marker_list = panel_df["marker"].tolist()
        marker_map = {marker: f"{marker}_sum" for marker in marker_list}
    else:
        raise ValueError("Panel file is required for dynamic marker detection.")

    thresholds = {}

    if use_manual_thresholds:
        csv_dir = os.path.dirname(csv_path)
        if threshold_source_image:
            threshold_path = os.path.join(csv_dir, f"{threshold_source_image}_thresholds.json")
        else:
            matches = glob.glob(os.path.join(csv_dir, "*_thresholds.json"))
            if not matches:
                raise FileNotFoundError(
                    f"No *_thresholds.json file found in '{csv_dir}', and no --threshold-source-image was provided."
                )
            threshold_path = matches[0]
            print(f"Auto-detected threshold file: {threshold_path}")

        if not os.path.exists(threshold_path):
            raise FileNotFoundError(f"Threshold file not found at: {threshold_path}")

        with open(threshold_path, "r") as f:
            thresholds = json.load(f)
        print(f"Loaded thresholds from {threshold_path}")

    max_area = int(df["area"].max()) if "area" in df.columns else 150

    for marker in marker_list:
        if marker in thresholds:
            print(f"Using manual threshold for {marker}: {thresholds[marker]}")
            continue  # Already loaded from JSON, skip default computation

        col = f"{marker}_sum"
        if col not in df.columns:
            thresholds[marker] = 150
            continue

        if marker == "DAPI":
            try:
                thresholds[marker] = int(threshold_otsu(df[col].values) * 0.5)
            except Exception:
                thresholds[marker] = int(df[col].median())
        else:
            print('Using area as threshold for ' + str(marker))
            thresholds[marker] = max_area

    viewer = napari.Viewer()
    viewer.add_image(orig_img, channel_axis=0, name="Original Image")
    viewer.add_labels(labeled_image, opacity=0.4, blending='additive', name="Labels")
    identity_mask = np.zeros_like(label_img, dtype=np.uint8)
    identity_layer = viewer.add_labels(identity_mask, name="Cell Identity", visible=False)

    # Point layers for each marker
    point_layers = {}
    for marker in marker_list:
        col = f"{marker}_sum"
        if col in df.columns:
            coords = df.loc[df[col] > thresholds[marker], ['centroid-0', 'centroid-1']].values
            point_layers[marker] = viewer.add_points(coords, name=f"{marker}+", size=20, visible=True)

    # GUI controls
    controls = VBox()
    restrict_checkbox = CheckBox(label="Restrict marker channels to DAPI+", value=True)
    identity_checkbox = CheckBox(label="Show full cell labels", value=False)
    run_button = PushButton(label="Run")
    save_button = PushButton(label="Save Thresholds")
    controls.extend([restrict_checkbox, identity_checkbox])

    threshold_sliders = {}
    for marker in marker_list:
        col = f"{marker}_sum"
        if col not in df.columns:
            continue
        max_val = int(min(df[col].max(), 2_000_000_000))
        step_val = max(1, int(max_val // 100_000))
        slider = FloatSlider(label=f"{marker} Threshold", min=0, max=max_val, step=step_val, value=thresholds[marker])
        threshold_sliders[marker] = slider
        controls.append(slider)

    controls.extend([run_button, save_button])

    def update_outputs():
        thresholds.update({marker: slider.value for marker, slider in threshold_sliders.items()})
        restrict = restrict_checkbox.value
        show_identity = identity_checkbox.value

        dapi_col = marker_map.get("DAPI", None)
        dapi_thresh = thresholds.get("DAPI", 0)

        # Update identity labels
        identity_mask[:] = 0
        for _, row in df.iterrows():
            obj_id = row["Object"]
            if restrict and dapi_col and row.get(dapi_col, 0) <= dapi_thresh:
                continue

            non_dapi_markers = [m for m in marker_list if m != "DAPI"]

            for idx, marker in enumerate(non_dapi_markers):
                if row.get(marker_map[marker], 0) > thresholds[marker]:
                    identity_mask[label_img == obj_id] = idx + 2
                    break

            else:
                if dapi_col and row.get(dapi_col, 0) > dapi_thresh:
                    identity_mask[label_img == obj_id] = 1

        identity_layer.visible = show_identity
        identity_layer.data = identity_mask

        # Update point layers with respect to restrict_to_dapi
        for marker in marker_list:
            col = marker_map[marker]
            if col not in df.columns or marker not in point_layers:
                continue

            marker_thresh = thresholds.get(marker, 0)
            if restrict and dapi_col:
                coords = df.loc[
                    (df[col] > marker_thresh) & (df[dapi_col] > dapi_thresh),
                    ['centroid-0', 'centroid-1']
                ].values
            else:
                coords = df.loc[df[col] > marker_thresh, ['centroid-0', 'centroid-1']].values

            point_layers[marker].data = coords

    @run_button.clicked.connect
    def _run():
        update_outputs()

    @save_button.clicked.connect
    def _save():
        if threshold_json_out:
            with open(threshold_json_out, "w") as f:
                json.dump({k: int(v) for k, v in thresholds.items()}, f, indent=4)
            print(f"Saved thresholds to {threshold_json_out}")

    viewer.window.add_dock_widget(controls, name="Threshold Controls", area="right")
    update_outputs()
    napari.run()
