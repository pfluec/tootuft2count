import numpy as np
import tifffile

from tootuft2count.grouping import discover_groups


def test_discovers_and_numerically_sorts_channel_groups(tmp_path):
    for channel in (10, 2, 0):
        tifffile.imwrite(tmp_path / f"sample_ch{channel:02}.tif", np.zeros((8, 9), np.uint16))
    groups = discover_groups(tmp_path)
    assert [group.name for group in groups] == ["sample"]
    assert [channel.index for channel in groups[0].channels] == [0, 2, 10]


def test_multichannel_ome_tiff_is_one_group(tmp_path):
    tifffile.imwrite(tmp_path / "sample.tiff", np.zeros((3, 8, 9), np.uint16), ome=True,
                     metadata={"axes": "CYX", "Channel": {"Name": ["A", "B", "C"]}})
    group = discover_groups(tmp_path)[0]
    assert group.name == "sample"
    assert [channel.marker for channel in group.channels] == ["A", "B", "C"]

