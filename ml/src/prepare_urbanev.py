#!/usr/bin/env python3
"""Convert UrbanEV hourly zone data into the pklot-ml CSV contract."""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main(source, output):
    with (source / "inf.csv").open(newline="") as file:
        piles = defaultdict(int)
        for row in csv.DictReader(file):
            piles[row["TAZID"]] += int(row["charge_count"])
    with (source / "volume-11kW.csv").open(newline="") as file:
        reader = csv.DictReader(file)
        zones = [name for name in reader.fieldnames if name != "time"]
        if set(zones) != set(piles):
            raise ValueError("volume zones and station capacities differ")
        rows = list(reader)
    times = [datetime.fromisoformat(row["time"]).replace(tzinfo=timezone(timedelta(hours=8)))
             for row in rows]
    if any(right - left != timedelta(hours=1) for left, right in zip(times, times[1:])):
        raise ValueError("UrbanEV has missing or duplicate hourly records")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp_epoch", "station_id", "total_piles", "load_kw"])
        for time, row in zip(times, rows):
            for zone in zones:
                # One row is one hour; kWh over one hour equals average kW.
                writer.writerow([int(time.timestamp()), zone, piles[zone], row[zone]])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: prepare_urbanev.py DATASET_DIR OUTPUT_CSV")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
