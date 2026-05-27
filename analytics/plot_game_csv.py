#!/usr/bin/env python3
"""Plot Processing game CSV logs."""
# pylint: disable=duplicate-code

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_LOG_DIR = Path(__file__).resolve().parents[1] / "processing" / "logs"

NUMERIC_COLUMNS = (
    "elapsed_ms",
    "frame_count",
    "player_x",
    "player_y",
    "player_vx",
    "target_x",
    "target_y",
    "target_dx",
    "target_dy",
    "target_distance",
    "bullet_active",
    "bullet_x",
    "bullet_y",
    "score",
    "miss_count",
    "shield_active",
)

DISPLAY_NAMES = {
    "elapsed_ms": "elapsed",
    "frame_count": "frame",
    "player_x": "player x",
    "player_y": "player y",
    "player_vx": "player vx",
    "target_x": "target x",
    "target_y": "target y",
    "target_dx": "target dx",
    "target_dy": "target dy",
    "target_distance": "distance",
    "bullet_active": "bullet",
    "bullet_x": "bullet x",
    "bullet_y": "bullet y",
    "score": "score",
    "miss_count": "miss",
    "shield_active": "B state",
}

Row = dict[str, float | str | None]


@dataclass(frozen=True)
class GamePanel:
    """One game-log plot panel."""

    columns: list[str]
    title: str
    ylabel: str
    step: bool = False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Plot a Processing game CSV log."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help="CSV file to plot. Defaults to the latest session_*_game.csv.",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output image path.")
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open a graph window.",
    )
    parser.add_argument(
        "--milliseconds",
        action="store_true",
        help="Use milliseconds on the x-axis.",
    )
    return parser.parse_args()


def latest_csv_path() -> Path:
    """Return the latest game CSV log."""
    candidates = list(DEFAULT_LOG_DIR.glob("session_*_game.csv"))
    if not candidates:
        raise FileNotFoundError(f"Game log not found: {DEFAULT_LOG_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def to_float(value: str | None) -> float | None:
    """Parse a finite float, returning None for invalid values."""
    if value is None:
        return None

    value = value.strip()
    if value == "":
        return None

    try:
        result = float(value)
    except ValueError:
        return None

    if not math.isfinite(result):
        return None
    return result


def load_rows(csv_path: Path) -> list[Row]:
    """Load rows for plotting."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV header not found: {csv_path}")
        if "elapsed_ms" not in reader.fieldnames:
            raise ValueError("CSV column missing: elapsed_ms")

        rows: list[Row] = []
        for csv_row in reader:
            row: Row = {
                column: to_float(csv_row.get(column)) for column in NUMERIC_COLUMNS
            }
            row["event_type"] = csv_row.get("event_type", "")
            row["event_value"] = csv_row.get("event_value", "")
            row["target_type"] = csv_row.get("target_type", "")
            if row["elapsed_ms"] is not None:
                rows.append(row)

    if not rows:
        raise ValueError(f"No usable elapsed_ms rows: {csv_path}")
    return rows


def values(rows: Iterable[Row], column: str) -> list[float | None]:
    """Return one numeric column from rows."""
    result: list[float | None] = []
    for row in rows:
        value = row.get(column)
        result.append(value if isinstance(value, float) else None)
    return result


def clean_pairs(
    x_values: Iterable[float | None], y_values: Iterable[float | None]
) -> list[tuple[float, float]]:
    """Return x/y pairs that have both values."""
    return [
        (x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None
    ]


def time_axis(rows: list[Row], milliseconds: bool) -> tuple[list[float], str]:
    """Build x-axis values from elapsed_ms."""
    elapsed_ms = [value or 0.0 for value in values(rows, "elapsed_ms")]
    start_ms = elapsed_ms[0]
    divisor = 1.0 if milliseconds else 1000.0
    label = "elapsed ms" if milliseconds else "elapsed sec"
    return [((value - start_ms) / divisor) for value in elapsed_ms], label


def display_name(column: str) -> str:
    """Return a short display label for a CSV column."""
    return DISPLAY_NAMES.get(column, column)


def print_summary(csv_path: Path, rows: list[Row]) -> None:
    """Print a short game-log summary."""
    event_counts: dict[str, int] = {}
    for row in rows:
        event_type = row.get("event_type")
        if isinstance(event_type, str) and event_type and event_type != "none":
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

    print(f"CSV: {csv_path}")
    print(f"Rows: {len(rows)}")
    print(f"Final score: {last_number(rows, 'score')}")
    print(f"Final miss: {last_number(rows, 'miss_count')}")
    if event_counts:
        print(
            "Events: "
            + ", ".join(f"{key}={value}" for key, value in sorted(event_counts.items()))
        )


def last_number(rows: list[Row], column: str) -> str:
    """Return the last numeric value for display."""
    for row in reversed(rows):
        value = row.get(column)
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:.2f}"
    return ""


def configure_matplotlib(plt: Any) -> None:
    """Apply small matplotlib defaults."""
    plt.rcParams["axes.unicode_minus"] = False


def plot_csv(
    csv_path: Path, output: Path | None, show: bool, milliseconds: bool
) -> None:
    """Load and plot a game CSV file."""
    rows = load_rows(csv_path)
    print_summary(csv_path, rows)

    try:
        # pylint: disable=import-outside-toplevel,import-error
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        if output:
            raise SystemExit(
                "--output requires matplotlib. "
                "Install: python3 -m pip install matplotlib"
            ) from exc
        return

    configure_matplotlib(plt)
    time_values, time_label = time_axis(rows, milliseconds)

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=False)
    fig.suptitle(csv_path.name)

    plot_panel(
        axes[0],
        time_values,
        rows,
        GamePanel(["player_x", "target_x", "bullet_x"], "X", "x"),
    )
    plot_panel(
        axes[1],
        time_values,
        rows,
        GamePanel(["player_y", "target_y", "bullet_y"], "Y", "y"),
    )
    plot_panel(
        axes[2],
        time_values,
        rows,
        GamePanel(
            ["player_vx", "target_distance", "target_dx"],
            "Target",
            "value",
        ),
    )
    plot_panel(
        axes[3],
        time_values,
        rows,
        GamePanel(
            ["score", "miss_count", "bullet_active", "shield_active"],
            "Score",
            "state",
            step=True,
        ),
    )

    for axis in axes:
        axis.set_xlabel(time_label)

    fig.tight_layout()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160)
        print(f"Saved: {output}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_panel(
    axis: Any,
    time_values: list[float],
    rows: list[Row],
    panel: GamePanel,
) -> None:
    """Draw one matplotlib panel."""
    plotted = False
    for column in panel.columns:
        pairs = clean_pairs(time_values, values(rows, column))
        if not pairs:
            continue
        x_values = [x for x, _y in pairs]
        y_values = [y for _x, y in pairs]
        if panel.step:
            axis.step(x_values, y_values, where="post", label=display_name(column))
        else:
            axis.plot(x_values, y_values, label=display_name(column), linewidth=1.4)
        plotted = True

    axis.set_title(panel.title)
    axis.set_ylabel(panel.ylabel)
    axis.grid(True, alpha=0.3)
    if plotted:
        axis.legend(loc="upper right", ncols=3)


def main() -> None:
    """Run the CLI."""
    args = parse_args()
    plot_csv(
        csv_path=args.csv_path or latest_csv_path(),
        output=args.output,
        show=not args.no_show,
        milliseconds=args.milliseconds,
    )


if __name__ == "__main__":
    main()
