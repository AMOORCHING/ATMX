"""Fetch HRRR GRIB2 forecast files from NOAA Open Data Dissemination (NODD) on AWS S3.

NOAA HRRR data is stored in the `noaa-hrrr-bdp-pds` bucket (requester-pays disabled
for NODD) with the key pattern:

    hrrr.{YYYYMMDD}/conus/hrrr.t{HH}z.wrfsfcf{FF}.grib2

where HH is the model run hour and FF is the forecast hour.
"""

import logging
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3
from botocore import UNSIGNED
from botocore.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_s3_key(run_date: datetime, run_hour: int, forecast_hour: int) -> str:
    """Construct the S3 object key for a specific HRRR GRIB2 file."""
    date_str = run_date.strftime("%Y%m%d")
    return (
        f"hrrr.{date_str}/conus/"
        f"hrrr.t{run_hour:02d}z.wrfsfcf{forecast_hour:02d}.grib2"
    )


class GribFetcher:
    """Download GRIB2 files from NOAA's S3 bucket."""

    def __init__(self) -> None:
        self._s3 = boto3.client(
            "s3",
            region_name=settings.aws_region,
            config=Config(signature_version=UNSIGNED),  # public bucket
        )
        self._bucket = settings.noaa_s3_bucket

    def fetch(
        self,
        run_date: datetime,
        run_hour: int = 0,
        forecast_hour: int = 1,
        dest_dir: str | None = None,
    ) -> Path:
        """Download a single GRIB2 file and return the local path.

        Args:
            run_date: The model run date.
            run_hour: The model initialization hour (0-23).
            forecast_hour: The forecast lead time in hours (0-48 for HRRR).
            dest_dir: Optional directory to store the file. Uses a tempdir if None.

        Returns:
            Path to the downloaded .grib2 file.
        """
        key = build_s3_key(run_date, run_hour, forecast_hour)
        logger.info("Fetching s3://%s/%s", self._bucket, key)

        if dest_dir is None:
            dest_dir = TemporaryDirectory(prefix="grib_").name
            Path(dest_dir).mkdir(parents=True, exist_ok=True)

        local_path = Path(dest_dir) / key.split("/")[-1]
        self._s3.download_file(self._bucket, key, str(local_path))
        logger.info("Downloaded %s (%.1f MB)", local_path, local_path.stat().st_size / 1e6)
        return local_path
