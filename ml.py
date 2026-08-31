"""Minimal charging-load forecasting pipeline for the PKLOT project."""

from __future__ import annotations

import argparse
import json
import pickle
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

HORIZONS = (1, 6, 24)
FEATURES = (
    "hour",
    "day_of_week",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "lag_1",
    "lag_24",
    "lag_168",
    "rolling_24",
)
REQUIRED_COLUMNS = {"timestamp", "station_id", "total_piles", "load_kw"}


def generate_data(output: Path, days: int = 90, stations: int = 3, seed: int = 42) -> Path:
    """Generate deterministic hourly station data until the backend supplies history."""
    if days < 10 or stations < 1:
        raise ValueError("days must be >= 10 and stations must be >= 1")

    rng = np.random.default_rng(seed)
    end = pd.Timestamp.now(tz="UTC").floor("h")
    timestamps = pd.date_range(end=end, periods=days * 24, freq="h")
    rows: list[dict[str, object]] = []

    for station_id in range(1, stations + 1):
        total_piles = 16 + station_id * 4
        station_factor = 0.85 + station_id * 0.12
        for timestamp in timestamps:
            hour = timestamp.hour
            weekend_factor = 0.88 if timestamp.dayofweek >= 5 else 1.0
            morning = 32 * np.exp(-((hour - 8) / 2.6) ** 2)
            evening = 48 * np.exp(-((hour - 18) / 3.2) ** 2)
            load_kw = (12 + morning + evening) * station_factor * weekend_factor
            load_kw = float(np.clip(load_kw + rng.normal(0, 4), 0, total_piles * 7))
            occupied = min(total_piles, int(np.ceil(load_kw / 7)))
            rows.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "station_id": station_id,
                    "total_piles": total_piles,
                    "load_kw": round(load_kw, 3),
                    "occupied_piles": occupied,
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False)
    return output


def build_features(data: pd.DataFrame, include_targets: bool) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

    frame = data.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    frame = frame.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    frame["hour"] = frame["timestamp"].dt.hour
    frame["day_of_week"] = frame["timestamp"].dt.dayofweek
    frame["is_weekend"] = (frame["day_of_week"] >= 5).astype(int)
    frame["hour_sin"] = np.sin(2 * np.pi * frame["hour"] / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * frame["hour"] / 24)

    grouped = frame.groupby("station_id", sort=False)
    for lag in (1, 24, 168):
        frame[f"lag_{lag}"] = grouped["load_kw"].shift(lag)
    frame["rolling_24"] = grouped["load_kw"].transform(
        lambda values: values.shift(1).rolling(24).mean()
    )

    if include_targets:
        for horizon in HORIZONS:
            frame[f"target_{horizon}"] = grouped["load_kw"].shift(-horizon)
    return frame


def train(input_csv: Path, model_path: Path, metrics_path: Path) -> dict[str, dict[str, float]]:
    frame = build_features(pd.read_csv(input_csv), include_targets=True)
    targets = [f"target_{horizon}" for horizon in HORIZONS]
    frame = frame.dropna(subset=[*FEATURES, *targets])
    timestamps = frame["timestamp"].drop_duplicates().sort_values().to_list()
    if len(timestamps) < 48:
        raise ValueError("not enough hourly history after feature construction")

    split_time = timestamps[int(len(timestamps) * 0.8)]
    train_rows = frame[frame["timestamp"] < split_time]
    test_rows = frame[frame["timestamp"] >= split_time]
    models: dict[int, HistGradientBoostingRegressor] = {}
    metrics: dict[str, dict[str, float]] = {}

    for horizon in HORIZONS:
        target = f"target_{horizon}"
        model = HistGradientBoostingRegressor(
            learning_rate=0.08,
            max_iter=150,
            max_leaf_nodes=15,
            random_state=42,
        )
        model.fit(train_rows[list(FEATURES)], train_rows[target])
        predicted = model.predict(test_rows[list(FEATURES)])
        models[horizon] = model
        persistence = test_rows["load_kw"]
        metrics[str(horizon)] = {
            "model_mae": round(float(mean_absolute_error(test_rows[target], predicted)), 4),
            "model_rmse": round(float(np.sqrt(mean_squared_error(test_rows[target], predicted))), 4),
            "persistence_mae": round(
                float(mean_absolute_error(test_rows[target], persistence)), 4
            ),
            "persistence_rmse": round(
                float(np.sqrt(mean_squared_error(test_rows[target], persistence))), 4
            ),
        }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as handle:
        pickle.dump({"features": FEATURES, "horizons": HORIZONS, "models": models}, handle)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def predict(input_csv: Path, model_path: Path, output: Path, kw_per_pile: float = 7.0) -> dict:
    if kw_per_pile <= 0:
        raise ValueError("kw_per_pile must be positive")

    frame = build_features(pd.read_csv(input_csv), include_targets=False)
    latest = frame.dropna(subset=list(FEATURES)).groupby("station_id", as_index=False).tail(1)
    if latest.empty:
        raise ValueError("not enough history to build prediction features")

    with model_path.open("rb") as handle:
        bundle = pickle.load(handle)  # Load only model files produced by this project.

    predictions: list[dict[str, object]] = []
    for _, row in latest.iterrows():
        station_features = pd.DataFrame([{name: row[name] for name in bundle["features"]}])
        for horizon in bundle["horizons"]:
            load_kw = max(0.0, float(bundle["models"][horizon].predict(station_features)[0]))
            total_piles = int(row["total_piles"])
            occupied = min(total_piles, int(np.ceil(load_kw / kw_per_pile)))
            predictions.append(
                {
                    "station_id": int(row["station_id"]),
                    "horizon_hours": int(horizon),
                    "predicted_load_kw": round(load_kw, 3),
                    "predicted_occupied_piles": occupied,
                    "predicted_available_piles": total_piles - occupied,
                    "congestion_ratio": round(occupied / total_piles, 4),
                }
            )

    recommendations = sorted(
        (item for item in predictions if item["horizon_hours"] == 1),
        key=lambda item: (item["congestion_ratio"], item["station_id"]),
    )
    result = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "predictions": predictions,
        "recommended_station_ids": [item["station_id"] for item in recommendations],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def demo() -> None:
    """Small end-to-end check; no test framework or committed generated files needed."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        data = generate_data(root / "history.csv", days=45, stations=2)
        metrics = train(data, root / "model.pkl", root / "metrics.json")
        result = predict(data, root / "model.pkl", root / "predictions.json")
        assert set(metrics) == {"1", "6", "24"}
        assert len(result["predictions"]) == 6
        assert len(result["recommended_station_ids"]) == 2
        print(json.dumps({"metrics": metrics, "sample": result["predictions"][:3]}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="create simulated hourly history")
    generate.add_argument("--output", type=Path, default=Path("data/history.csv"))
    generate.add_argument("--days", type=int, default=90)
    generate.add_argument("--stations", type=int, default=3)
    generate.add_argument("--seed", type=int, default=42)

    train_command = commands.add_parser("train", help="train direct 1/6/24-hour models")
    train_command.add_argument("--input", type=Path, default=Path("data/history.csv"))
    train_command.add_argument("--model", type=Path, default=Path("models/load_forecaster.pkl"))
    train_command.add_argument("--metrics", type=Path, default=Path("models/metrics.json"))

    predict_command = commands.add_parser("predict", help="write backend-ready prediction JSON")
    predict_command.add_argument("--input", type=Path, default=Path("data/history.csv"))
    predict_command.add_argument("--model", type=Path, default=Path("models/load_forecaster.pkl"))
    predict_command.add_argument("--output", type=Path, default=Path("outputs/predictions.json"))
    predict_command.add_argument("--kw-per-pile", type=float, default=7.0)

    commands.add_parser("demo", help="run the end-to-end self-check")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "generate":
        print(generate_data(args.output, args.days, args.stations, args.seed))
    elif args.command == "train":
        print(json.dumps(train(args.input, args.model, args.metrics), indent=2))
    elif args.command == "predict":
        print(json.dumps(predict(args.input, args.model, args.output), ensure_ascii=False, indent=2))
    else:
        demo()


if __name__ == "__main__":
    main()

