import numpy as np

from tootuft2count.measure import _measure_channel


def test_background_pixels_do_not_create_an_area_baseline():
    channel = np.array([[1, 1], [10, 10]], dtype=np.uint16)
    mask = np.array([[1, 1], [2, 2]], dtype=np.int32)
    integrated, normalized = _measure_channel(
        channel, mask, object_ids=np.array([1, 2]), areas=np.array([2, 2])
    )
    np.testing.assert_array_equal(integrated, [0, 20])
    np.testing.assert_array_equal(normalized, [0, 10])
