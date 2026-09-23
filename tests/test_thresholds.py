import json

import pandas as pd

from tootuft2count.quantify import quantify_cells
from tootuft2count.thresholds import automatic_threshold, resolve_thresholds


def test_resolve_thresholds_keeps_supplied_values_and_fills_missing():
    data = pd.DataFrame({"A_sum": [0, 0, 100, 120], "B_sum": [0, 10, 20, 30]})
    thresholds = resolve_thresholds(data, ["A", "B"], {"A": 42})
    assert thresholds["A"] == 42
    assert thresholds["B"] == automatic_threshold(data["B_sum"])


def test_quantification_uses_same_thresholds_for_all_outputs(tmp_path):
    csv_dir, results_dir = tmp_path / "csv", tmp_path / "results"
    csv_dir.mkdir()
    pd.DataFrame({
        "Object": [1, 2, 3],
        "area": [10, 10, 10],
        "DAPI_sum": [0, 100, 100],
        "A_sum": [0, 100, 0],
        "B_sum": [0, 100, 100],
    }).to_csv(csv_dir / "sample.csv", index=False)
    panel = tmp_path / "panel.csv"
    pd.DataFrame({"channel": [0, 1, 2], "marker": ["DAPI", "A", "B"]}).to_csv(
        panel, index=False
    )

    quantify_cells(
        str(csv_dir), str(results_dir), str(panel),
        thresholds={"DAPI": 50, "A": 50, "B": 50},
        populations=[{"name": "AB", "rule": "DAPI+ AND A+ AND B+"}],
    )
    summary = pd.read_csv(results_dir / "sample_summary.csv").iloc[0]
    assert summary["DAPI+ Cells"] == 2
    assert summary["A+ of All"] == 1
    assert summary["A+ of DAPI+"] == 1
    assert summary["A+ of B+ (%) (All)"] == 50
    assert summary["B+ of A+ (%) (All)"] == 100
    assert summary["AB Cells"] == 1
    assert summary["A Threshold"] == 50
    assert summary["A Threshold Source"] == "supplied"


def test_manual_threshold_json_is_used(tmp_path):
    csv_dir, results_dir = tmp_path / "csv", tmp_path / "results"
    csv_dir.mkdir()
    pd.DataFrame({"Object": [1, 2], "area": [10, 10], "A_sum": [10, 100]}).to_csv(
        csv_dir / "sample.csv", index=False
    )
    (csv_dir / "source_thresholds.json").write_text(
        json.dumps({"A": 50}), encoding="utf-8"
    )
    panel = tmp_path / "panel.csv"
    pd.DataFrame({"channel": [0], "marker": ["A"]}).to_csv(panel, index=False)

    quantify_cells(
        str(csv_dir), str(results_dir), str(panel),
        use_manual_thresholds=True, threshold_source_image="source",
        filenames=["sample.csv"],
    )
    summary = pd.read_csv(results_dir / "sample_summary.csv").iloc[0]
    assert summary["A+ of All"] == 1
    assert summary["A Threshold"] == 50
    assert summary["A Threshold Source"] == "supplied"
