
import numpy as np


def decode_packed_values(raw_values, attrs):
    """Decode packed numeric values using fill and scale metadata.

    Returns decoded floating-point values and a validity mask.
    The input must contain raw, undecoded stored values.
    """
    raw = np.asarray(raw_values)

    if not np.issubdtype(raw.dtype, np.number):
        raise ValueError("Values must be numeric.")

    # Identify missing values BEFORE scaling.
    valid = np.isfinite(raw)

    for key in ("_FillValue", "missing_value"):
        if key not in attrs:
            continue

        missing_values = np.atleast_1d(attrs[key])

        for missing in missing_values:
            if np.issubdtype(raw.dtype, np.floating):
                if np.isnan(missing):
                    valid &= ~np.isnan(raw)
                else:
                    valid &= raw != missing
            else:
                valid &= raw != missing

    # Work in floating point to avoid integer overflow.
    decoded = raw.astype(np.float64)
    decoded[~valid] = np.nan

    scale = float(attrs.get("scale_factor", 1.0))
    offset = float(attrs.get("add_offset", 0.0))

    decoded[valid] = decoded[valid] * scale + offset

    return decoded, valid


def summarize_values(values):
    """Calculate statistics for already-decoded values."""
    values = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(values)
    valid_values = values[finite]

    return {
        "total_elements": int(values.size),
        "valid_elements": int(finite.sum()),
        "missing_or_nonfinite": int((~finite).sum()),
        "minimum": (
            float(valid_values.min()) if valid_values.size else None
        ),
        "maximum": (
            float(valid_values.max()) if valid_values.size else None
        ),
        "mean": (
            float(valid_values.mean()) if valid_values.size else None
        ),
    }



def summarize_quality_flags(raw_values, attrs):
    """Count quality flag meanings using CF-style flag metadata."""
    raw = np.asarray(raw_values)

    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("Quality flags must use an integer dtype.")

    valid = np.ones(raw.shape, dtype=bool)

    for key in ("_FillValue", "missing_value"):
        if key in attrs:
            for missing in np.atleast_1d(attrs[key]):
                valid &= raw != missing

    meanings = str(attrs.get("flag_meanings", "")).split()
    flag_values = attrs.get("flag_values")
    flag_masks = attrs.get("flag_masks")

    values = (
        np.atleast_1d(flag_values)
        if flag_values is not None else None
    )
    masks = (
        np.atleast_1d(flag_masks)
        if flag_masks is not None else None
    )

    if meanings and values is None and masks is None:
        raise ValueError("flag_meanings requires flag_values or flag_masks.")

    if values is not None and len(values) != len(meanings):
        raise ValueError("flag_values and flag_meanings lengths differ.")

    if masks is not None and len(masks) != len(meanings):
        raise ValueError("flag_masks and flag_meanings lengths differ.")

    if values is not None and masks is not None:
        if any((int(v) & int(m)) != int(v)
               for v, m in zip(values, masks)):
            raise ValueError("A flag value sets bits outside its mask.")

    # Signed flag values may contain negative numbers, so preserve
    # their integer representation for comparisons.
    result = {
        "total_elements": int(raw.size),
        "missing_elements": int((~valid).sum()),
        "flag_counts": {},
        "unrecognized_elements": 0,
    }

    recognized = np.zeros(raw.shape, dtype=bool)

    for i, meaning in enumerate(meanings):
        if values is not None and masks is not None:
            matched = (raw & int(masks[i])) == int(values[i])
        elif masks is not None:
            matched = (raw & int(masks[i])) != 0
        else:
            matched = raw == int(values[i])

        matched &= valid
        recognized |= matched

        result["flag_counts"][meaning] = int(matched.sum())

    if values is not None or masks is not None:
        result["unrecognized_elements"] = int(
            (valid & ~recognized).sum()
        )

    return result
