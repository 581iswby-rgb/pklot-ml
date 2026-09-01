#!/usr/bin/env python3
"""Convert prediction JSON into SQL inserts for a backend import step."""
import json
import sys
from pathlib import Path


def main(source, output):
    data = json.loads(source.read_text(encoding="utf-8"))
    generated_at = int(data["generated_at_epoch"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        file.write(
            "CREATE TABLE IF NOT EXISTS ml_station_predictions (\n"
            "  station_id INTEGER NOT NULL,\n"
            "  horizon_hours INTEGER NOT NULL,\n"
            "  predicted_load_kw REAL NOT NULL,\n"
            "  predicted_occupied_piles INTEGER NOT NULL,\n"
            "  predicted_available_piles INTEGER NOT NULL,\n"
            "  congestion_ratio REAL NOT NULL,\n"
            "  generated_at_epoch INTEGER NOT NULL,\n"
            "  PRIMARY KEY (station_id, horizon_hours, generated_at_epoch)\n"
            ");\n"
        )
        for item in data["predictions"]:
            file.write(
                "INSERT OR REPLACE INTO ml_station_predictions VALUES "
                f"({int(item['station_id'])}, {int(item['horizon_hours'])}, "
                f"{float(item['predicted_load_kw']):.4f}, "
                f"{int(item['predicted_occupied_piles'])}, "
                f"{int(item['predicted_available_piles'])}, "
                f"{float(item['congestion_ratio']):.4f}, {generated_at});\n"
            )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: export_predictions_sql.py PREDICTIONS_JSON OUTPUT_SQL")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
