import os
import glob
import pandas as pd
import json
from skimage.filters import threshold_otsu


def quantify_cells(
        csv_dir='csv',
        results_dir='results',
        panel='panel.csv',
        use_manual_thresholds=False,
        threshold_source_image=None,
        filenames=None,
        populations=None,
):
    """
    Quantifies marker-positive cell populations from per-cell measurements.

    Arguments:
    - csv_dir: directory containing per-image CSVs (default: 'csv')
    - results_dir: directory to save summary files (default: 'results')
    - panel: path to panel.csv defining markers and channel ordering
    - use_manual_thresholds: if True, applies threshold values from a shared *_thresholds.json
    - threshold_source_image: base name of the image used to generate the threshold file

    Threshold logic:
    - DAPI threshold defaults to 0.5 * Otsu threshold if not supplied.
    - Marker thresholds fall back to object 'area' if not provided.
    - Outputs include both all-cell and DAPI+ gated statistics.
    """
    os.makedirs(results_dir, exist_ok=True)

    # Load panel
    if not panel or not os.path.exists(panel):
        raise ValueError("A panel.csv file is required for quantification.")
    panel_df = pd.read_csv(panel)
    marker_list = panel_df["marker"].tolist()

    # Load thresholds (shared for all images)
    thresholds = {}
    if use_manual_thresholds:
        if threshold_source_image:
            threshold_path = os.path.join(csv_dir, f"{threshold_source_image}_thresholds.json")
        else:
            matches = glob.glob(os.path.join(csv_dir, "*_thresholds.json"))
            if not matches:
                raise FileNotFoundError(
                    f"No *_thresholds.json file found in '{csv_dir}', and no --threshold-source-image was provided."
                )
            threshold_path = matches[0]
            print(f"🔍 Auto-detected threshold file: {threshold_path}")

        if not os.path.exists(threshold_path):
            raise FileNotFoundError(f"Threshold file not found at: {threshold_path}")

        with open(threshold_path, "r") as f:
            thresholds = json.load(f)
        print(f"Loaded thresholds from {threshold_path}")

    for fname in filenames or sorted(os.listdir(csv_dir)):
        if not fname.endswith(".csv"):
            continue

        feature_path = os.path.join(csv_dir, fname)
        df = pd.read_csv(feature_path)
        image_base = os.path.splitext(fname)[0]
        summary = {"Image": image_base, "Total Cells": len(df)}

        # Determine DAPI+ cells
        if "DAPI" in marker_list and "DAPI_sum" in df.columns:
            if "DAPI" in thresholds:
                dapi_thresh = thresholds["DAPI"]
            else:
                dapi_thresh = threshold_otsu(df["DAPI_sum"].values) * 0.5
            dapi_pos = df[df["DAPI_sum"] > dapi_thresh]
        else:
            dapi_pos = df

        summary["DAPI+ Cells"] = len(dapi_pos)

        # Quantify marker-positive cells
        quant_markers = [m for m in marker_list if m != "DAPI"]
        for marker in quant_markers:
            col = f"{marker}_sum"
            if col not in df.columns:
                continue

            if marker in thresholds:
                df_pos = df[df[col] > thresholds[marker]]
                dapi_marker_pos = dapi_pos[dapi_pos[col] > thresholds[marker]]
            else:
                df_pos = df[df[col] > df["area"]]
                dapi_marker_pos = dapi_pos[dapi_pos[col] > dapi_pos["area"]]

            summary[f"{marker}+ of All"] = len(df_pos)
            summary[f"{marker}+ of All (%)"] = 100 * len(df_pos) / len(df) if len(df) else 0
            summary[f"{marker}+ of DAPI+"] = len(dapi_marker_pos)
            summary[f"{marker}+ of DAPI+ (%)"] = 100 * len(dapi_marker_pos) / len(dapi_pos) if len(dapi_pos) else 0

        # Quantify double-positive populations
        for A in quant_markers:
            for B in quant_markers:
                if A == B:
                    continue
                col_A = f"{A}_sum"
                col_B = f"{B}_sum"
                if col_A not in df.columns or col_B not in df.columns:
                    continue

                if A in thresholds and B in thresholds:
                    B_pos = df[df[col_B] > thresholds[B]]
                    AB_pos = B_pos[B_pos[col_A] > thresholds[A]]
                    B_pos_dapi = dapi_pos[dapi_pos[col_B] > thresholds[B]]
                    AB_pos_dapi = B_pos_dapi[B_pos_dapi[col_A] > thresholds[A]]
                else:
                    B_pos = df[df[col_B] > df["area"] * 100]
                    AB_pos = B_pos[B_pos[col_A] > B_pos["area"] * 100]
                    B_pos_dapi = dapi_pos[dapi_pos[col_B] > dapi_pos["area"] * 100]
                    AB_pos_dapi = B_pos_dapi[B_pos_dapi[col_A] > B_pos_dapi["area"] * 100]

                summary[f"{A}+ of {B}+ (%) (All)"] = 100 * len(AB_pos) / len(B_pos) if len(B_pos) else 0
                summary[f"{A}+ of {B}+ (%) (DAPI+)"] = 100 * len(AB_pos_dapi) / len(B_pos_dapi) if len(
                    B_pos_dapi) else 0

        if populations:
            from .populations import evaluate_population
            effective_thresholds = dict(thresholds)
            for marker in marker_list:
                col = f"{marker}_sum"
                if marker not in effective_thresholds and col in df:
                    effective_thresholds[marker] = threshold_otsu(df[col].values) if len(df) and df[col].nunique() > 1 else 0
            for population in populations:
                selected = evaluate_population(df, population["rule"], effective_thresholds)
                summary[f"{population['name']} Cells"] = int(selected.sum())
                summary[f"{population['name']} (%)"] = 100 * selected.mean() if len(df) else 0

        summary_df = pd.DataFrame([summary])
        summary_out = os.path.join(results_dir, f"{image_base}_summary.csv")
        summary_df.to_csv(summary_out, index=False)
        print(f"Saved quantification summary for {fname} to {summary_out}")
