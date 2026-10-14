
import os
from pathlib import Path

import h5py
import numpy as np
import xarray as xr
from mcp.server import MCPServer

from quality import decode_packed_values, summarize_values
from quality import summarize_quality_flags


DATA_DIR = Path(
    os.environ.get("SATELLITE_DATA_DIR", "./data")
).resolve()

SUPPORTED = {".nc", ".nc4", ".cdf", ".h5", ".hdf5"}

mcp = MCPServer("Satellite Data Quality Inspector")


def safe_file(filename: str) -> Path:
    """Allow access only to supported files inside DATA_DIR."""
    path = (DATA_DIR / filename).resolve()

    if not path.is_relative_to(DATA_DIR):
        raise ValueError("Path must stay inside the data directory.")

    if path.suffix.lower() not in SUPPORTED:
        raise ValueError("Unsupported file extension.")

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {filename}")

    return path


@mcp.tool()
def list_satellite_files() -> list[str]:
    """List supported satellite files in the configured data directory."""
    if not DATA_DIR.is_dir():
        return []

    return sorted(
        p.name for p in DATA_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )


@mcp.tool()
def inspect_satellite_file(filename: str) -> dict:
    """Inspect dimensions, variables, and metadata of a satellite file."""
    path = safe_file(filename)

    if path.suffix.lower() in {".h5", ".hdf5"}:
        with h5py.File(path, "r") as f:
            datasets = []

            def collect(name, obj):
                if isinstance(obj, h5py.Dataset):
                    datasets.append({
                        "name": name,
                        "shape": list(obj.shape),
                        "dtype": str(obj.dtype),
                        "attributes": {
                            str(k): str(v)
                            for k, v in obj.attrs.items()
                        },
                    })

            f.visititems(collect)

            return {
                "file": path.name,
                "format": "HDF5",
                "datasets": datasets,
                "global_attributes": {
                    str(k): str(v) for k, v in f.attrs.items()
                },
            }

    with xr.open_dataset(path) as ds:
        return {
            "file": path.name,
            "format": "NetCDF",
            "dimensions": {
                str(k): int(v) for k, v in ds.sizes.items()
            },
            "variables": {
                name: {
                    "dimensions": list(var.dims),
                    "shape": list(var.shape),
                    "dtype": str(var.dtype),
                    "attributes": {
                        str(k): str(v)
                        for k, v in var.attrs.items()
                    },
                }
                for name, var in ds.variables.items()
            },
            "global_attributes": {
                str(k): str(v) for k, v in ds.attrs.items()
            },
        }


@mcp.tool()
def summarize_variable(
    filename: str,
    variable: str,
    max_samples: int = 100_000,
) -> dict:
    """Summarize a bounded sample of a numeric NetCDF variable."""
    path = safe_file(filename)

    if path.suffix.lower() in {".h5", ".hdf5"}:
        raise ValueError(
            "This tool currently supports NetCDF variables only."
        )

    if not 1 <= max_samples <= 1_000_000:
        raise ValueError("max_samples must be between 1 and 1000000.")

    with xr.open_dataset(path) as ds:
        if variable not in ds.data_vars:
            raise ValueError(f"Unknown data variable: {variable}")

        var = ds[variable]

        if not np.issubdtype(var.dtype, np.number):
            raise ValueError("Variable must be numeric.")

        flat = var.data.reshape(-1)
        values = np.asarray(flat[:max_samples]).astype(float)
        total = int(var.size)
        sampled = int(values.size)

        finite = np.isfinite(values)
        valid = values[finite]

        return {
            "file": path.name,
            "variable": variable,
            "total_elements": total,
            "sampled_elements": sampled,
            "sampling_complete": sampled == total,
            "missing_or_nonfinite_in_sample": int((~finite).sum()),
            "minimum": float(valid.min()) if valid.size else None,
            "maximum": float(valid.max()) if valid.size else None,
            "mean": float(valid.mean()) if valid.size else None,
        }


@mcp.tool()
def quality_check_variable(filename: str, variable: str) -> dict:
    """Check missing values and physical statistics for a packed NetCDF variable."""
    path = safe_file(filename)

    if path.suffix.lower() in {".h5", ".hdf5"}:
        raise ValueError("Use a NetCDF file for this tool.")

    with xr.open_dataset(
        path,
        decode_cf=False,
        mask_and_scale=False,
    ) as ds:
        if variable not in ds.data_vars:
            raise ValueError(f"Unknown data variable: {variable}")

        var = ds[variable]
        attrs = dict(var.attrs)

        if not np.issubdtype(var.dtype, np.number):
            raise ValueError("Variable must be numeric.")

        raw = var.values
        decoded, valid = decode_packed_values(raw, attrs)

        result = summarize_values(decoded)
        result.update({
            "file": path.name,
            "variable": variable,
            "units": attrs.get("units"),
            "scale_factor": float(attrs.get("scale_factor", 1)),
            "add_offset": float(attrs.get("add_offset", 0)),
            "storage_dtype": str(var.dtype),
            "missing_fraction": (
                float((~valid).sum() / valid.size)
                if valid.size else None
            ),
        })

        return result


@mcp.tool()
def quality_check_flags(filename: str, variable: str) -> dict:
    """Count categories or conditions in a NetCDF quality flag."""
    path = safe_file(filename)

    if path.suffix.lower() in {".h5", ".hdf5"}:
        raise ValueError("Use a NetCDF file for this tool.")

    with xr.open_dataset(
        path,
        decode_cf=False,
        mask_and_scale=False,
    ) as ds:
        if variable not in ds.data_vars:
            raise ValueError(f"Unknown data variable: {variable}")

        var = ds[variable]

        return {
            "file": path.name,
            "variable": variable,
            **summarize_quality_flags(var.values, dict(var.attrs)),
        }


@mcp.tool()
def quality_check_hdf5_dataset(
    filename: str,
    dataset_path: str,
) -> dict:
    """Summarize a numeric HDF5 dataset using its packing metadata."""
    path = safe_file(filename)

    if path.suffix.lower() not in {".h5", ".hdf5"}:
        raise ValueError("Expected an HDF5 file.")

    with h5py.File(path, "r") as f:
        if dataset_path not in f:
            raise ValueError(f"Dataset not found: {dataset_path}")

        ds = f[dataset_path]

        if not isinstance(ds, h5py.Dataset):
            raise ValueError("Path does not identify a dataset.")

        if not np.issubdtype(ds.dtype, np.number):
            raise ValueError("Dataset must be numeric.")

        attrs = dict(ds.attrs)

        if "_FillValue" not in attrs and ds.fillvalue is not None:
            attrs["_FillValue"] = ds.fillvalue

        # Suitable for small datasets only.
        raw = ds[...]

        decoded, valid = decode_packed_values(raw, attrs)
        result = summarize_values(decoded)

        return {
            "file": path.name,
            "dataset": dataset_path,
            "shape": list(ds.shape),
            "storage_dtype": str(ds.dtype),
            "units": str(attrs.get("units", "")),
            "missing_fraction": (
                float((~valid).sum() / valid.size)
                if valid.size else None
            ),
            **result,
        }
