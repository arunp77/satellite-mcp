
from pathlib import Path

import numpy as np
import xarray as xr

output = Path("data/sample.nc")
output.parent.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(42)

temperature = 280 + 5 * rng.standard_normal((100, 200))
quality_flag = rng.choice(
    [0, 1, 2],
    size=(100, 200),
    p=[0.95, 0.03, 0.02],
).astype("int8")

# Insert a few missing temperature values.
temperature[0, 0] = np.nan
temperature[1, 1] = np.nan

ds = xr.Dataset(
    data_vars={
        "brightness_temperature": (
            ("scanline", "pixel"),
            temperature,
            {"units": "K", "long_name": "Brightness temperature"},
        ),
        "quality_flag": (
            ("scanline", "pixel"),
            quality_flag,
            {"flag_meanings": "good suspect invalid"},
        ),
    },
    attrs={
        "platform": "Synthetic satellite",
        "product_level": "L1",
        "processing_version": "1.0",
    },
)

ds.to_netcdf(output)
print(f"Created {output}")

