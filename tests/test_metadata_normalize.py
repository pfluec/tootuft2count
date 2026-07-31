import numpy as np
import tifffile

from tootuft2count.grouping import Channel
from tootuft2count.metadata import inspect_tiff
from tootuft2count.normalize import normalize_sample, resampling_decision
from tootuft2count.project import SampleState


def test_ome_metadata_is_read(tmp_path):
    path = tmp_path / "image.tiff"
    tifffile.imwrite(path, np.zeros((2, 10, 12), np.uint16), ome=True,
                     metadata={"axes": "CYX", "PhysicalSizeX": .25, "PhysicalSizeXUnit": "µm",
                               "PhysicalSizeY": .25, "PhysicalSizeYUnit": "µm",
                               "Channel": {"Name": ["DAPI", "DCLK1"]}})
    metadata = inspect_tiff(path)
    assert metadata.pixel_size_x == .25
    assert metadata.channel_names == ["DAPI", "DCLK1"]


def test_resampling_policy():
    assert resampling_decision(.25, .25)[:2] == (.5, .5)
    assert resampling_decision(.75, .75)[:2] == (1.0, .75)
    assert resampling_decision(None, None)[:2] == (1.0, None)
    assert "anisotropic" in resampling_decision(.25, .3)[2]
    assert resampling_decision(.25, .3, override=.25)[:2] == (.5, .5)


def test_normalization_downsamples_and_preserves_source(tmp_path):
    source = tmp_path / "sample_ch00.tif"
    original = np.arange(100, dtype=np.uint16).reshape(10, 10)
    tifffile.imwrite(source, original, ome=True,
                     metadata={"axes": "YX", "PhysicalSizeX": .25, "PhysicalSizeY": .25})
    sample = SampleState("sample", [vars(Channel(str(source), 0, "DAPI"))])
    output, reason = normalize_sample(sample, tmp_path / "img")
    assert reason == "downsampled"
    assert tifffile.imread(output).shape == (5, 5)
    np.testing.assert_array_equal(tifffile.imread(source), original)
