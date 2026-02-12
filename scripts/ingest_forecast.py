#!/usr/bin/env python3
"""CLI script to ingest a HRRR forecast file into the database.

Usage:
    python scripts/ingest_forecast.py --date 2025-08-14 --hour 0 --forecast-hour 1

This script:
1. Downloads the GRIB2 file from NOAA's S3 bucket.
2. Parses precipitation and wind speed fields.
3. Maps grid points to H3 cells.
4. Prints summary statistics (database upsert is left for the full pipeline).
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add settlement-oracle service root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "settlement-oracle"))

from app.pipeline.grib_fetcher import GribFetcher
from app.pipeline.grib_parser import parse_precipitation, parse_wind_speed
from app.pipeline.h3_indexer import index_points_to_h3


def main():
    parser = argparse.ArgumentParser(description="Ingest HRRR forecast data")
    parser.add_argument("--date", required=True, help="Model run date (YYYY-MM-DD)")
    parser.add_argument("--hour", type=int, default=0, help="Model run hour (0-23)")
    parser.add_argument("--forecast-hour", type=int, default=1, help="Forecast hour (0-48)")
    parser.add_argument("--output-dir", default=None, help="Directory to save GRIB2 file")
    args = parser.parse_args()

    run_date = datetime.strptime(args.date, "%Y-%m-%d")

    print(f"Fetching HRRR forecast: date={args.date} hour={args.hour:02d} fhr={args.forecast_hour:02d}")
    fetcher = GribFetcher()
    grib_path = fetcher.fetch(run_date, args.hour, args.forecast_hour, args.output_dir)
    print(f"Downloaded: {grib_path}")

    print("\nParsing precipitation...")
    precip_points = parse_precipitation(grib_path)
    precip_cells = index_points_to_h3(precip_points)
    print(f"  {len(precip_points)} grid points → {len(precip_cells)} H3 cells")

    print("\nParsing wind speed...")
    wind_points = parse_wind_speed(grib_path)
    wind_cells = index_points_to_h3(wind_points)
    print(f"  {len(wind_points)} grid points → {len(wind_cells)} H3 cells")

    # Print top cells by value
    print("\nTop 10 cells by precipitation (mm):")
    for cell in sorted(precip_cells, key=lambda c: c.max_value, reverse=True)[:10]:
        print(f"  {cell.h3_cell}: max={cell.max_value:.2f} mean={cell.mean_value:.2f} (n={cell.point_count})")

    print("\nTop 10 cells by wind speed (m/s):")
    for cell in sorted(wind_cells, key=lambda c: c.max_value, reverse=True)[:10]:
        print(f"  {cell.h3_cell}: max={cell.max_value:.2f} mean={cell.mean_value:.2f} (n={cell.point_count})")


if __name__ == "__main__":
    main()
