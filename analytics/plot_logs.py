#!/usr/bin/env python3
"""Open input and game log plots together."""
# pylint: disable=duplicate-code

from __future__ import annotations

import argparse
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

import plot_game_csv as game_plot
import plot_input_csv as input_plot

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = SCRIPT_DIR.parent / "processing" / "logs"


@dataclass(frozen=True)
class LogPair:
    """Input and game logs from the same run."""

    input_path: Path
    game_path: Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Open input and game plots in one wide window."
    )
    parser.add_argument(
        "--session",
        help="Session id, with or without the session_ prefix.",
    )
    parser.add_argument("--input", dest="input_path", type=Path, help="Input CSV")
    parser.add_argument("--game", dest="game_path", type=Path, help="Game CSV")
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Log directory. Defaults to processing/logs.",
    )
    parser.add_argument(
        "--milliseconds",
        action="store_true",
        help="Use milliseconds on the x-axis.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open the graph window.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for combined.png. Requires matplotlib.",
    )
    return parser.parse_args()


def resolve_log_pair(args: argparse.Namespace) -> LogPair:
    """Resolve the input and game log pair from arguments."""
    log_dir = args.log_dir

    if args.session:
        return pair_from_session(log_dir, args.session)

    input_path = args.input_path
    game_path = args.game_path

    if input_path is None and game_path is None:
        input_path = latest_input_log(log_dir)
        game_path = matching_game_log(input_path) or latest_game_log(log_dir)
    elif input_path is not None and game_path is None:
        game_path = matching_game_log(input_path) or latest_game_log(log_dir)
    elif input_path is None and game_path is not None:
        input_path = matching_input_log(game_path) or latest_input_log(log_dir)

    assert input_path is not None
    assert game_path is not None
    ensure_file(input_path)
    ensure_file(game_path)
    return LogPair(input_path.resolve(), game_path.resolve())


def pair_from_session(log_dir: Path, session: str) -> LogPair:
    """Find logs by session id."""
    session_name = session if session.startswith("session_") else f"session_{session}"
    input_path = first_existing(
        log_dir / f"{session_name}_input.csv",
        log_dir / f"{session_name}_sensor.csv",
    )
    game_path = log_dir / f"{session_name}_game.csv"
    if input_path is None:
        raise FileNotFoundError(f"Input log not found: {session_name}")
    ensure_file(game_path)
    return LogPair(input_path.resolve(), game_path.resolve())


def first_existing(*paths: Path) -> Path | None:
    """Return the first existing path."""
    for path in paths:
        if path.exists():
            return path
    return None


def latest_input_log(log_dir: Path) -> Path:
    """Return the latest input log."""
    candidates = list(log_dir.glob("session_*_input.csv"))
    candidates.extend(log_dir.glob("session_*_sensor.csv"))
    if not candidates:
        raise FileNotFoundError(f"Input log not found: {log_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def latest_game_log(log_dir: Path) -> Path:
    """Return the latest game log."""
    candidates = list(log_dir.glob("session_*_game.csv"))
    if not candidates:
        raise FileNotFoundError(f"Game log not found: {log_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def matching_game_log(input_path: Path) -> Path | None:
    """Return the game log for the same session as an input log."""
    name = input_path.name
    if name.endswith("_input.csv"):
        candidate = input_path.with_name(name.replace("_input.csv", "_game.csv"))
    elif name.endswith("_sensor.csv"):
        candidate = input_path.with_name(name.replace("_sensor.csv", "_game.csv"))
    else:
        return None
    return candidate if candidate.exists() else None


def matching_input_log(game_path: Path) -> Path | None:
    """Return the input log for the same session as a game log."""
    name = game_path.name
    if not name.endswith("_game.csv"):
        return None
    input_path = game_path.with_name(name.replace("_game.csv", "_input.csv"))
    sensor_path = game_path.with_name(name.replace("_game.csv", "_sensor.csv"))
    return first_existing(input_path, sensor_path)


def ensure_file(path: Path) -> None:
    """Validate a CSV file path."""
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not path.is_file():
        raise ValueError(f"CSV path is not a file: {path}")


def run_plotters(pair: LogPair, args: argparse.Namespace) -> None:
    """Draw input and game plots in one figure."""
    print(f"Input: {pair.input_path}", flush=True)
    print(f"Game: {pair.game_path}", flush=True)

    input_rows = input_plot.load_rows(pair.input_path)
    game_rows = game_plot.load_rows(pair.game_path)
    input_plot.print_summary(pair.input_path, input_rows)
    game_plot.print_summary(pair.game_path, game_rows)
    print_learning_summary(game_rows)

    try:
        # pylint: disable=import-outside-toplevel,import-error
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "plot_logs.py requires matplotlib. "
            "Install: python3 -m pip install matplotlib"
        ) from exc

    input_plot.configure_matplotlib(plt)
    fig, axes = plt.subplots(4, 2, figsize=(18, 10), sharex=False)
    fig.suptitle(pair.input_path.name.replace("_input.csv", ""), fontsize=14)

    plot_input_column(axes[:, 0], input_rows, args.milliseconds)
    plot_game_column(axes[:, 1], game_rows, args.milliseconds)

    axes[0, 0].text(
        0.0,
        1.18,
        "INPUT / SENSOR",
        transform=axes[0, 0].transAxes,
        fontsize=12,
        fontweight="bold",
    )
    axes[0, 1].text(
        0.0,
        1.18,
        "GAME",
        transform=axes[0, 1].transAxes,
        fontsize=12,
        fontweight="bold",
    )
    axes[0, 1].text(
        0.14,
        1.18,
        shot_hit_label(game_rows),
        transform=axes[0, 1].transAxes,
        fontsize=10,
        color="#333333",
    )

    fig.tight_layout(rect=(0, 0, 1, 0.96))

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = args.output_dir / "combined.png"
        fig.savefig(output_path, dpi=160)
        print(f"Saved: {output_path}")

    if args.no_show:
        plt.close(fig)
    else:
        plt.show()


def plot_input_column(axes: object, rows: list[input_plot.Row], milliseconds: bool) -> None:
    """Draw the left input/sensor column."""
    time_values, time_label = input_plot.time_axis(rows, milliseconds)
    panels = [
        input_plot.TimeSeriesPanel(
            [
                input_plot.PlotSeries("ax_raw", "tab:blue", 0.45, 1.0),
                input_plot.PlotSeries("ay_raw", "tab:orange", 0.45, 1.0),
                input_plot.PlotSeries("az_raw", "tab:gray", 0.45, 1.0),
                input_plot.PlotSeries("control_x_raw", "tab:brown", 1.0, 1.4),
                input_plot.PlotSeries("control_y_raw", "tab:purple", 1.0, 1.4),
            ],
            "Raw",
            "value",
        ),
        input_plot.TimeSeriesPanel(
            [
                input_plot.PlotSeries("input_x_smooth", "tab:brown", 1.0, 1.4),
                input_plot.PlotSeries("input_y_smooth", "tab:purple", 1.0, 1.4),
                input_plot.PlotSeries("tilt_x", "tab:blue", 1.0, 1.4),
                input_plot.PlotSeries("speed_modifier", "tab:green", 1.0, 1.4),
            ],
            "Control",
            "value",
        ),
        input_plot.TimeSeriesPanel(
            [
                input_plot.PlotSeries("btnA_pressed", "tab:red", 1.0, 1.6),
                input_plot.PlotSeries("btnB_raw", "tab:green", 1.0, 1.6),
                input_plot.PlotSeries("shake_event", "tab:orange", 1.0, 1.6),
                input_plot.PlotSeries("light_shield", "tab:cyan", 1.0, 1.6),
            ],
            "Buttons",
            "state",
            step=True,
        ),
        input_plot.TimeSeriesPanel(
            [
                input_plot.PlotSeries("serial_valid", "tab:blue", 1.0, 1.4),
                input_plot.PlotSeries("serial_invalid_count", "tab:red", 1.0, 1.4),
                input_plot.PlotSeries("serial_valid_count", "tab:green", 1.0, 1.4),
            ],
            "Serial",
            "count",
        ),
    ]
    for axis, panel in zip(axes, panels):
        input_plot.plot_time_series(axis, time_values, rows, panel)
        axis.set_xlabel(time_label)


def plot_game_column(axes: object, rows: list[game_plot.Row], milliseconds: bool) -> None:
    """Draw the right game column."""
    time_values, time_label = game_plot.time_axis(rows, milliseconds)
    panels = [
        game_plot.GamePanel(["player_x", "target_x", "bullet_x"], "X", "x"),
        game_plot.GamePanel(["player_y", "target_y", "bullet_y"], "Y", "y"),
        game_plot.GamePanel(
            ["player_vx", "target_distance", "target_dx"],
            "Target",
            "value",
        ),
        game_plot.GamePanel(
            ["score", "miss_count", "bullet_active", "shield_active"],
            "Score",
            "state",
            step=True,
        ),
    ]
    for axis, panel in zip(axes, panels):
        game_plot.plot_panel(axis, time_values, rows, panel)
        axis.set_xlabel(time_label)


def print_learning_summary(rows: list[game_plot.Row]) -> None:
    """Print simple skill/progress metrics from the game log."""
    duration_s = session_duration_s(rows)
    score = last_number(rows, "score")
    misses = last_number(rows, "miss_count")
    shots = event_count(rows, "shot")
    hits = event_count(rows, "hit")
    hit_rate = hits / shots if shots else 0.0
    shots_per_hit = shots / hits if hits else math.inf
    first_dx, last_dx = tracking_error_by_half(rows)
    shot_dx = median_abs_at_event(rows, "shot", "target_dx")

    print("Learning:")
    print(f"  duration: {duration_s:.1f}s")
    print(f"  score/miss: {score}/{misses}")
    print(f"  shots/hits: {shots}/{hits} ({hit_rate:.1%})")
    print(f"  shots per hit: {format_number(shots_per_hit)}")
    print(f"  tracking dx median: {format_number(first_dx)} -> {format_number(last_dx)}")
    print(f"  shot dx median: {format_number(shot_dx)}")


def shot_hit_label(rows: list[game_plot.Row]) -> str:
    """Return a short shot/hit label for the game heading."""
    shots = event_count(rows, "shot")
    hits = event_count(rows, "hit")
    hit_rate = hits / shots if shots else 0.0
    return f"shots {shots} / hits {hits} / {hit_rate:.1%}"


def session_duration_s(rows: list[game_plot.Row]) -> float:
    """Return log duration in seconds."""
    elapsed = numeric_values(rows, "elapsed_ms")
    if len(elapsed) < 2:
        return 0.0
    return (elapsed[-1] - elapsed[0]) / 1000.0


def event_count(rows: list[game_plot.Row], event_type: str) -> int:
    """Count game event rows."""
    return sum(row.get("event_type") == event_type for row in rows)


def last_number(rows: list[game_plot.Row], column: str) -> int:
    """Return the last integer value from a numeric column."""
    for row in reversed(rows):
        value = row.get(column)
        if isinstance(value, float) and math.isfinite(value):
            return int(value)
    return 0


def tracking_error_by_half(rows: list[game_plot.Row]) -> tuple[float | None, float | None]:
    """Return median abs target_dx for the first and second half."""
    visible_rows = [
        row
        for row in rows
        if is_number(row.get("target_y")) and 0 <= float(row["target_y"]) <= 600
    ]
    if len(visible_rows) < 2:
        return None, None

    midpoint = len(visible_rows) // 2
    return (
        median_abs(visible_rows[:midpoint], "target_dx"),
        median_abs(visible_rows[midpoint:], "target_dx"),
    )


def median_abs_at_event(
    rows: list[game_plot.Row], event_type: str, column: str
) -> float | None:
    """Return median absolute column value on a given event."""
    event_rows = [row for row in rows if row.get("event_type") == event_type]
    return median_abs(event_rows, column)


def median_abs(rows: list[game_plot.Row], column: str) -> float | None:
    """Return median absolute numeric value for a column."""
    values = [abs(value) for value in numeric_values(rows, column)]
    return statistics.median(values) if values else None


def numeric_values(rows: list[game_plot.Row], column: str) -> list[float]:
    """Return finite numeric values from a column."""
    result = []
    for row in rows:
        value = row.get(column)
        if isinstance(value, float) and math.isfinite(value):
            result.append(value)
    return result


def is_number(value: object) -> bool:
    """Return whether a value is a finite number."""
    return isinstance(value, float) and math.isfinite(value)


def format_number(value: float | None) -> str:
    """Format a nullable metric."""
    if value is None:
        return "n/a"
    if math.isinf(value):
        return "n/a"
    return f"{value:.1f}"


def main() -> None:
    """Run the CLI."""
    args = parse_args()
    run_plotters(resolve_log_pair(args), args)


if __name__ == "__main__":
    main()
