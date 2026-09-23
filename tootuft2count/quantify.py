"""Quantify marker-positive cells with one consistent threshold policy."""

import glob
import json
import os

import pandas as pd

from .thresholds import resolve_thresholds, validate_thresholds


def _manual_thresholds(csv_dir, threshold_source_image=None):
    if threshold_source_image:
        threshold_path = os.path.join(csv_dir, f"{threshold_source_image}_thresholds.json")
    else:
        matches = sorted(glob.glob(os.path.join(csv_dir, "*_thresholds.json")))
        if not matches:
            raise FileNotFoundError(
                f"No *_thresholds.json file found in '{csv_dir}', and no "
                "--threshold-source-image was provided."
            )
        threshold_path = matches[0]
        print(f"Auto-detected threshold file: {threshold_path}")
    if not os.path.exists(threshold_path):
        raise FileNotFoundError(f"Threshold file not found at: {threshold_path}")
    with open(threshold_path, "r", encoding="utf-8") as stream:
        loaded = validate_thresholds(json.load(stream))
    print(f"Loaded thresholds from {threshold_path}")
    return loaded


def quantify_cells(
        csv_dir='csv',
        results_dir='results',
        panel='panel.csv',
        use_manual_thresholds=False,
        threshold_source_image=None,
        filenames=None,
        populations=None,
        thresholds=None,
):
    """Quantify all outputs using integrated intensity and one threshold/marker.

    Explicit ``thresholds`` (for example from a saved project) take priority.
    A manual JSON can be loaded for CLI compatibility. Missing values are
    filled per image using Otsu on the corresponding ``<marker>_sum`` values.
    The same resolved values drive DAPI gating, single-marker results,
    double-positive results, and Boolean population rules.
    """
    os.makedirs(results_dir, exist_ok=True)
    if not panel or not os.path.exists(panel):
        raise ValueError("A panel.csv file is required for quantification.")
    panel_df = pd.read_csv(panel).sort_values("channel")
    marker_list = panel_df["marker"].astype(str).tolist()

    supplied = validate_thresholds(thresholds)
    if use_manual_thresholds:
        loaded = _manual_thresholds(csv_dir, threshold_source_image)
        loaded.update(supplied)
        supplied = loaded

    for fname in filenames or sorted(os.listdir(csv_dir)):
        if not fname.endswith(".csv"):
            continue
        feature_path = os.path.join(csv_dir, fname)
        df = pd.read_csv(feature_path)
        image_base = os.path.splitext(fname)[0]
        effective = resolve_thresholds(df, marker_list, supplied)
        summary = {"Image": image_base, "Total Cells": len(df)}
        for marker in marker_list:
            if marker in effective:
                summary[f"{marker} Threshold"] = effective[marker]
                summary[f"{marker} Threshold Source"] = (
                    "supplied" if marker in supplied else "Otsu"
                )

        dapi_col = "DAPI_sum"
        if "DAPI" in marker_list and dapi_col in df and "DAPI" in effective:
            dapi_pos = df[df[dapi_col] > effective["DAPI"]]
        else:
            dapi_pos = df
        summary["DAPI+ Cells"] = len(dapi_pos)

        quant_markers = [marker for marker in marker_list if marker != "DAPI"]
        for marker in quant_markers:
            column = f"{marker}_sum"
            if column not in df or marker not in effective:
                continue
            positive = df[df[column] > effective[marker]]
            dapi_positive = dapi_pos[dapi_pos[column] > effective[marker]]
            summary[f"{marker}+ of All"] = len(positive)
            summary[f"{marker}+ of All (%)"] = 100 * len(positive) / len(df) if len(df) else 0
            summary[f"{marker}+ of DAPI+"] = len(dapi_positive)
            summary[f"{marker}+ of DAPI+ (%)"] = (
                100 * len(dapi_positive) / len(dapi_pos) if len(dapi_pos) else 0
            )

        for marker_a in quant_markers:
            for marker_b in quant_markers:
                if marker_a == marker_b:
                    continue
                column_a, column_b = f"{marker_a}_sum", f"{marker_b}_sum"
                if (column_a not in df or column_b not in df
                        or marker_a not in effective or marker_b not in effective):
                    continue
                b_positive = df[df[column_b] > effective[marker_b]]
                ab_positive = b_positive[b_positive[column_a] > effective[marker_a]]
                b_positive_dapi = dapi_pos[dapi_pos[column_b] > effective[marker_b]]
                ab_positive_dapi = b_positive_dapi[
                    b_positive_dapi[column_a] > effective[marker_a]
                ]
                summary[f"{marker_a}+ of {marker_b}+ (%) (All)"] = (
                    100 * len(ab_positive) / len(b_positive) if len(b_positive) else 0
                )
                summary[f"{marker_a}+ of {marker_b}+ (%) (DAPI+)"] = (
                    100 * len(ab_positive_dapi) / len(b_positive_dapi)
                    if len(b_positive_dapi) else 0
                )

        if populations:
            from .populations import evaluate_population
            for population in populations:
                selected = evaluate_population(df, population["rule"], effective)
                summary[f"{population['name']} Cells"] = int(selected.sum())
                summary[f"{population['name']} (%)"] = 100 * selected.mean() if len(df) else 0

        summary_out = os.path.join(results_dir, f"{image_base}_summary.csv")
        pd.DataFrame([summary]).to_csv(summary_out, index=False)
        print(f"Saved quantification summary for {fname} to {summary_out}")
