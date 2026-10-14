
import numpy as np
import pytest

from quality import (
    decode_packed_values,
    summarize_values,
    summarize_quality_flags,
)


def test_fill_values_are_removed_before_scaling():
    raw = np.array([2500, 2600, -9999, 2800], dtype=np.int16)
    attrs = {
        "_FillValue": -9999,
        "scale_factor": 0.01,
        "add_offset": 150.0,
    }

    decoded, valid = decode_packed_values(raw, attrs)

    assert valid.tolist() == [True, True, False, True]
    assert decoded[0] == pytest.approx(175.0)
    assert decoded[1] == pytest.approx(176.0)
    assert np.isnan(decoded[2])
    assert decoded[3] == pytest.approx(178.0)


def test_statistics_ignore_nan_and_infinity():
    result = summarize_values([10.0, 20.0, np.nan, np.inf])

    assert result["total_elements"] == 4
    assert result["valid_elements"] == 2
    assert result["missing_or_nonfinite"] == 2
    assert result["mean"] == pytest.approx(15.0)


def test_enumerated_quality_flags():
    flags = np.array([0, 1, 0, 2, 1, 0], dtype=np.int8)
    attrs = {
        "flag_values": [0, 1, 2],
        "flag_meanings": "good suspect invalid",
    }

    result = summarize_quality_flags(flags, attrs)

    assert result["flag_counts"] == {
        "good": 3,
        "suspect": 2,
        "invalid": 1,
    }
    assert result["unrecognized_elements"] == 0


def test_bit_mask_quality_flags():
    flags = np.array([0, 1, 2, 3, 4], dtype=np.int16)
    attrs = {
        "flag_masks": [1, 2, 4],
        "flag_meanings": "cloud calibration geolocation",
    }

    result = summarize_quality_flags(flags, attrs)

    assert result["flag_counts"] == {
        "cloud": 2,
        "calibration": 2,
        "geolocation": 1,
    }


def test_invalid_flag_metadata_is_rejected():
    flags = np.array([0, 1], dtype=np.int8)
    attrs = {
        "flag_values": [0, 1],
        "flag_meanings": "good",
    }

    with pytest.raises(ValueError):
        summarize_quality_flags(flags, attrs)
