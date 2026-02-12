"""Parse GRIB2 files using cfgrib/xarray and extract precipitation + wind speed.

Relevant GRIB2 shortNames for HRRR surface-level fields:
  - tp   : Total precipitation (kg m⁻² ≡ mm)
  - 10si : 10-metre wind speed (m s⁻¹)  (or gust / u/v components)
"""

import logging
from pathlib import Path

import xarray as xr

from app.pipeline.h3_indexer import GridPoint

logger = logging.getLogger(__name__)


def parse_precipitation(grib_path: Path) -> list[GridPoint]:
    """Extract total precipitation (tp) from a GRIB2 file.

    Returns a list of GridPoint with value in mm.
    """
    return _extract_field(grib_path, short_name="tp", type_of_level="surface")


def parse_wind_speed(grib_path: Path) -> list[GridPoint]:
    """Extract 10-metre wind speed from a GRIB2 file.

    Attempts '10si' first; falls back to computing magnitude from u10/v10.
    Returns a list of GridPoint with value in m/s.
    """
    try:
        return _extract_field(grib_path, short_name="10si", type_of_level="heightAboveGround")
    except (KeyError, ValueError):
        logger.info("10si not found, computing from u10/v10 components")
        return _extract_wind_from_components(grib_path)


def _extract_field(
    grib_path: Path,
    short_name: str,
    type_of_level: str,
) -> list[GridPoint]:
    """Open a GRIB2 dataset filtered by shortName and level type, flatten to GridPoints."""
    ds = xr.open_dataset(
        grib_path,
        engine="cfgrib",
        backend_kwargs={
            "filter_by_keys": {
                "shortName": short_name,
                "typeOfLevel": type_of_level,
            },
            "indexpath": "",
        },
    )
    # The data variable name varies; take the first one
    var_name = list(ds.data_vars)[0]
    da = ds[var_name]

    lats = da.latitude.values
    lons = da.longitude.values
    vals = da.values

    points: list[GridPoint] = []
    for i in range(lats.shape[0]):
        for j in range(lats.shape[1]):
            lon = float(lons[i, j])
            # Normalize longitude from 0..360 → -180..180
            if lon > 180:
                lon -= 360
            points.append(
                GridPoint(
                    latitude=float(lats[i, j]),
                    longitude=lon,
                    value=float(vals[i, j]),
                )
            )
    ds.close()
    return points


def _extract_wind_from_components(grib_path: Path) -> list[GridPoint]:
    """Compute wind speed from u10 and v10 components."""
    import numpy as np

    ds_u = xr.open_dataset(
        grib_path,
        engine="cfgrib",
        backend_kwargs={
            "filter_by_keys": {"shortName": "10u", "typeOfLevel": "heightAboveGround"},
            "indexpath": "",
        },
    )
    ds_v = xr.open_dataset(
        grib_path,
        engine="cfgrib",
        backend_kwargs={
            "filter_by_keys": {"shortName": "10v", "typeOfLevel": "heightAboveGround"},
            "indexpath": "",
        },
    )

    u_var = list(ds_u.data_vars)[0]
    v_var = list(ds_v.data_vars)[0]

    u = ds_u[u_var].values
    v = ds_v[v_var].values
    speed = np.sqrt(u**2 + v**2)

    lats = ds_u[u_var].latitude.values
    lons = ds_u[u_var].longitude.values

    points: list[GridPoint] = []
    for i in range(lats.shape[0]):
        for j in range(lats.shape[1]):
            lon = float(lons[i, j])
            if lon > 180:
                lon -= 360
            points.append(
                GridPoint(
                    latitude=float(lats[i, j]),
                    longitude=lon,
                    value=float(speed[i, j]),
                )
            )
    ds_u.close()
    ds_v.close()
    return points
