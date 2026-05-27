#!/usr/bin/env python3
"""Plot Processing input CSV logs."""
# pylint: disable=duplicate-code

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

NUMERIC_COLUMNS = (
    "elapsed_ms",
    "microbit_runtime_ms",
    "serial_valid",
    "serial_column_count",
    "serial_valid_count",
    "serial_invalid_count",
    "ax_raw",
    "ay_raw",
    "az_raw",
    "light_raw",
    "temp_raw",
    "shake_raw",
    "pitch_raw",
    "roll_raw",
    "btnA_raw",
    "btnB_raw",
    "control_x_raw",
    "control_y_raw",
    "input_x_smooth",
    "input_y_smooth",
    "tilt_x",
    "speed_modifier",
    "btnA_pressed",
    "btnB_pressed",
    "shake_event",
    "light_shield",
)
BOUNDED_COLUMNS = {
    "serial_valid": (0.0, 1.0),
    "light_raw": (0.0, 255.0),
    "shake_raw": (0.0, 1.0),
    "btnA_raw": (0.0, 1.0),
    "btnB_raw": (0.0, 1.0),
    "btnA_pressed": (0.0, 1.0),
    "btnB_pressed": (0.0, 1.0),
    "shake_event": (0.0, 1.0),
    "light_shield": (0.0, 1.0),
}
DISPLAY_NAMES = {
    "elapsed_ms": "elapsed",
    "microbit_runtime_ms": "microbit ms",
    "serial_valid": "serial ok",
    "serial_column_count": "cols",
    "serial_valid_count": "valid rows",
    "serial_invalid_count": "bad rows",
    "ax_raw": "ax raw",
    "ay_raw": "ay raw",
    "az_raw": "az raw",
    "light_raw": "light",
    "temp_raw": "temp",
    "shake_raw": "shake",
    "pitch_raw": "pitch",
    "roll_raw": "roll",
    "control_x_raw": "control x",
    "control_y_raw": "control y",
    "input_x_smooth": "smooth x",
    "input_y_smooth": "smooth y",
    "tilt_x": "tilt x",
    "speed_modifier": "speed",
    "btnA_raw": "A raw",
    "btnB_raw": "B raw",
    "btnA_pressed": "A press",
    "btnB_pressed": "B press",
    "shake_event": "shake event",
    "light_shield": "light flag",
}
DEFAULT_LOG_DIR = (
    Path(__file__).resolve().parents[1]
    / "processing"
    / "logs"
)


Row = dict[str, float | None]


@dataclass(frozen=True)
class PlotSeries:
    """One plotted series."""

    column: str
    color: str
    alpha: float
    linewidth: float


@dataclass(frozen=True)
class TimeSeriesPanel:
    """One time-series panel."""

    series: list[PlotSeries]
    title: str
    ylabel: str
    step: bool = False


@dataclass(frozen=True)
class PanelBounds:
    """Panel bounds on a Tk canvas."""

    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class TkPanel:
    """Data needed to draw one Tk panel."""

    bounds: PanelBounds
    x_values: list[float]
    series: list[tuple[str, str]]
    rows: list[Row]
    label: str


@dataclass(frozen=True)
class PanelScale:
    """Scale data coordinates into Tk canvas coordinates."""

    bounds: PanelBounds
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def sx(self, value: float) -> float:
        """Convert an x value into a canvas coordinate."""
        width = self.bounds.right - self.bounds.left
        return (
            self.bounds.left
            + ((value - self.x_min) / (self.x_max - self.x_min)) * width
        )

    def sy(self, value: float) -> float:
        """Convert a y value into a canvas coordinate."""
        height = self.bounds.bottom - self.bounds.top
        return (
            self.bounds.bottom
            - ((value - self.y_min) / (self.y_max - self.y_min)) * height
        )


def display_name(column: str) -> str:
    """Return a short display label for a CSV column."""
    return DISPLAY_NAMES.get(column, column)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Plot a Processing micro:bit input CSV log."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help=(
            "CSV file to plot. Defaults to the latest "
            "session_*_input.csv in processing/logs."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output image path. Requires matplotlib.",
    )
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
    """Return the latest input CSV log."""
    for pattern in ("session_*_input.csv", "session_*_sensor.csv"):
        candidates = list(DEFAULT_LOG_DIR.glob(pattern))
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
    raise FileNotFoundError(f"CSV log not found: {DEFAULT_LOG_DIR}")


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


def normalize_value(column: str, value: float | None) -> float | None:
    """Drop out-of-range values for bounded columns."""
    if value is None:
        return None

    bounds = BOUNDED_COLUMNS.get(column)
    if bounds is not None:
        low, high = bounds
        if value < low or value > high:
            return None

    return value


def load_rows(csv_path: Path) -> list[Row]:
    """Load normalized numeric rows from a CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not csv_path.is_file():
        raise ValueError(f"CSV path is not a file: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV header not found: {csv_path}")
        if "elapsed_ms" not in reader.fieldnames:
            raise ValueError("CSV column missing: elapsed_ms")

        rows: list[Row] = []
        for csv_row in reader:
            row = {
                column: normalize_value(column, to_float(csv_row.get(column)))
                for column in NUMERIC_COLUMNS
            }
            if row["elapsed_ms"] is not None:
                rows.append(row)

    if not rows:
        raise ValueError(f"No usable elapsed_ms rows: {csv_path}")
    return rows


def values(rows: Iterable[Row], column: str) -> list[float | None]:
    """Return one column from rows."""
    return [row.get(column) for row in rows]


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


def print_summary(csv_path: Path, rows: list[Row]) -> None:
    """Print a short CSV summary."""
    present = [
        column
        for column in NUMERIC_COLUMNS
        if any(row.get(column) is not None for row in rows)
    ]
    print(f"CSV: {csv_path}")
    print(f"Rows: {len(rows)}")
    print("Columns: " + ", ".join(display_name(column) for column in present))


def configure_matplotlib(plt: Any) -> None:
    """Apply small matplotlib defaults."""
    plt.rcParams["axes.unicode_minus"] = False


def plot_csv(
    csv_path: Path, output: Path | None, show: bool, milliseconds: bool
) -> None:
    """Load and plot a CSV file."""
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
        if show:
            plot_csv_tk(csv_path, rows, milliseconds)
        return

    configure_matplotlib(plt)
    time_values, time_label = time_axis(rows, milliseconds)

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=False)
    fig.suptitle(csv_path.name)

    plot_time_series(
        axes[0],
        time_values,
        rows,
        TimeSeriesPanel(
            [
                PlotSeries("ax_raw", "tab:blue", 0.45, 1.0),
                PlotSeries("ay_raw", "tab:orange", 0.45, 1.0),
                PlotSeries("az_raw", "tab:gray", 0.45, 1.0),
                PlotSeries("control_x_raw", "tab:brown", 1.0, 1.4),
                PlotSeries("control_y_raw", "tab:purple", 1.0, 1.4),
            ],
            "Raw",
            "value",
        ),
    )

    plot_time_series(
        axes[1],
        time_values,
        rows,
        TimeSeriesPanel(
            [
                PlotSeries("control_x_raw", "tab:brown", 0.8, 1.2),
                PlotSeries("control_y_raw", "tab:purple", 0.8, 1.2),
                PlotSeries("input_x_smooth", "tab:brown", 1.0, 1.6),
                PlotSeries("input_y_smooth", "tab:purple", 1.0, 1.6),
                PlotSeries("tilt_x", "tab:blue", 1.0, 1.6),
                PlotSeries("speed_modifier", "tab:green", 1.0, 1.6),
            ],
            "Input",
            "value",
        ),
    )

    plot_time_series(
        axes[2],
        time_values,
        rows,
        TimeSeriesPanel(
            [
                PlotSeries("btnA_pressed", "tab:red", 1.0, 1.8),
                PlotSeries("btnB_raw", "tab:green", 1.0, 1.8),
                PlotSeries("shake_event", "tab:orange", 1.0, 1.8),
                PlotSeries("light_shield", "tab:cyan", 1.0, 1.8),
            ],
            "Buttons",
            "state",
            step=True,
        ),
    )

    plot_time_series(
        axes[3],
        time_values,
        rows,
        TimeSeriesPanel(
            [
                PlotSeries("light_raw", "tab:green", 1.0, 1.6),
                PlotSeries("temp_raw", "tab:red", 1.0, 1.6),
                PlotSeries("shake_raw", "tab:orange", 1.0, 1.6),
                PlotSeries("az_raw", "tab:gray", 0.8, 1.2),
            ],
            "Extra",
            "value",
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


def plot_time_series(
    axis: Any,
    time_values: list[float],
    rows: list[Row],
    panel: TimeSeriesPanel,
) -> None:
    """Draw one matplotlib panel."""
    plotted = False
    for series in panel.series:
        pairs = clean_pairs(time_values, values(rows, series.column))
        if not pairs:
            continue

        x_values = [x for x, _y in pairs]
        y_values = [y for _x, y in pairs]
        if panel.step:
            axis.step(
                x_values,
                y_values,
                where="post",
                label=display_name(series.column),
                color=series.color,
                linewidth=series.linewidth,
            )
        else:
            axis.plot(
                x_values,
                y_values,
                label=display_name(series.column),
                color=series.color,
                alpha=series.alpha,
                linewidth=series.linewidth,
            )
        plotted = True

    axis.set_title(panel.title)
    axis.set_ylabel(panel.ylabel)
    axis.grid(True, alpha=0.3)
    if plotted:
        axis.legend(loc="upper right", ncols=3)


def plot_csv_tk(csv_path: Path, rows: list[Row], milliseconds: bool) -> None:
    """Show a simple Tk plot when matplotlib is unavailable."""
    # pylint: disable=import-outside-toplevel
    import tkinter as tk
    from tkinter import ttk

    time_values, time_label = time_axis(rows, milliseconds)

    root = tk.Tk()
    root.title(f"CSV plot - {csv_path.name}")
    root.geometry("1100x800")

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    title = ttk.Label(frame, text=csv_path.name, font=("", 16, "bold"))
    title.pack(anchor=tk.W)

    subtitle = ttk.Label(
        frame,
        text=f"{len(rows)} rows / x: {time_label}",
    )
    subtitle.pack(anchor=tk.W, pady=(2, 10))

    canvas = tk.Canvas(frame, background="white", highlightthickness=1)
    canvas.pack(fill=tk.BOTH, expand=True)

    legend = ttk.Label(
        frame,
        text=(
            "raw: ax/ay/az/control  input: x/y/tilt  "
            "state: A/B/shake"
        ),
    )
    legend.pack(anchor=tk.W, pady=(8, 0))

    def redraw(_event: object | None = None) -> None:
        """Redraw the Tk canvas after resize."""
        canvas.delete("all")
        width = max(canvas.winfo_width(), 600)
        height = max(canvas.winfo_height(), 420)
        panel_height = (height - 48) // 3

        draw_panel(
            canvas,
            TkPanel(
                PanelBounds(58, 20, width - 24, 20 + panel_height),
                time_values,
                [
                    ("ax_raw", "#1f77b4"),
                    ("ay_raw", "#ff7f0e"),
                    ("az_raw", "#7f7f7f"),
                    ("control_x_raw", "#8c564b"),
                    ("control_y_raw", "#9467bd"),
                ],
                rows,
                "Raw",
            ),
        )
        draw_panel(
            canvas,
            TkPanel(
                PanelBounds(58, 34 + panel_height, width - 24, 34 + panel_height * 2),
                time_values,
                [
                    ("input_x_smooth", "#8c564b"),
                    ("input_y_smooth", "#9467bd"),
                    ("tilt_x", "#1f77b4"),
                    ("speed_modifier", "#2ca02c"),
                ],
                rows,
                "Input",
            ),
        )
        draw_panel(
            canvas,
            TkPanel(
                PanelBounds(58, 48 + panel_height * 2, width - 24, height - 26),
                time_values,
                [
                    ("light_raw", "#2ca02c"),
                    ("temp_raw", "#d62728"),
                    ("shake_raw", "#ff7f0e"),
                    ("az_raw", "#7f7f7f"),
                ],
                rows,
                "Extra",
            ),
        )

    canvas.bind("<Configure>", redraw)
    root.mainloop()


def draw_panel(
    canvas: Any,
    panel: TkPanel,
) -> None:
    """Draw one line chart on a Tk canvas."""
    all_y_values = [
        y
        for column, _color in panel.series
        for y in values(panel.rows, column)
        if y is not None
    ]
    if not all_y_values or not panel.x_values:
        return

    scale = build_panel_scale(panel.bounds, panel.x_values, all_y_values)
    draw_panel_frame(canvas, panel, scale)

    for column, color in panel.series:
        points = clean_pairs(panel.x_values, values(panel.rows, column))
        if len(points) < 2:
            continue
        coords = [coord for x, y in points for coord in (scale.sx(x), scale.sy(y))]
        canvas.create_line(*coords, fill=color, width=2)


def build_panel_scale(
    bounds: PanelBounds, x_values: list[float], y_values: list[float]
) -> PanelScale:
    """Build axis bounds for a Tk panel."""
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)
    if x_min == x_max:
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    y_padding = (y_max - y_min) * 0.08
    return PanelScale(bounds, x_min, x_max, y_min - y_padding, y_max + y_padding)


def draw_panel_frame(canvas: Any, panel: TkPanel, scale: PanelScale) -> None:
    """Draw a Tk panel frame and y-axis labels."""
    bounds = panel.bounds
    canvas.create_rectangle(
        bounds.left,
        bounds.top,
        bounds.right,
        bounds.bottom,
        outline="#cccccc",
    )
    canvas.create_text(
        bounds.left,
        bounds.top - 8,
        text=panel.label,
        anchor="sw",
        fill="#333333",
    )
    for i in range(6):
        ratio = i / 5
        y = bounds.top + ratio * (bounds.bottom - bounds.top)
        value = scale.y_max - ratio * (scale.y_max - scale.y_min)
        canvas.create_line(bounds.left, y, bounds.right, y, fill="#eeeeee")
        canvas.create_text(
            bounds.left - 8,
            y,
            text=f"{value:.0f}",
            anchor="e",
            fill="#666666",
        )


def main() -> None:
    """Run the CLI."""
    args = parse_args()
    csv_path = args.csv_path or latest_csv_path()
    plot_csv(
        csv_path=csv_path,
        output=args.output,
        show=not args.no_show,
        milliseconds=args.milliseconds,
    )


if __name__ == "__main__":
    main()
