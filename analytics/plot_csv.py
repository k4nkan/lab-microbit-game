#!/usr/bin/env python3
"""Processingで記録したmicro:bitのCSVログをグラフ表示する。"""

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
    "elapsed_ms": "経過時間",
    "microbit_runtime_ms": "micro:bit実行時間",
    "serial_valid": "シリアル有効",
    "serial_column_count": "受信列数",
    "serial_valid_count": "有効行数",
    "serial_invalid_count": "無効行数",
    "ax_raw": "左右加速度（生）",
    "ay_raw": "前後加速度（生）",
    "az_raw": "上下加速度（生）",
    "light_raw": "明るさ",
    "temp_raw": "温度",
    "shake_raw": "振った",
    "pitch_raw": "前後の角度（生）",
    "roll_raw": "左右の角度（生）",
    "input_x_smooth": "左右入力（ならし）",
    "input_y_smooth": "前後入力（ならし）",
    "tilt_x": "左右入力",
    "speed_modifier": "速度補正",
    "btnA_raw": "Aボタン",
    "btnB_raw": "Bボタン",
    "btnA_pressed": "A押下瞬間",
    "btnB_pressed": "B押下瞬間",
    "shake_event": "shakeイベント",
    "light_shield": "暗さシールド",
}
DEFAULT_LOG_DIR = (
    Path(__file__).resolve().parents[1]
    / "processing"
    / "logs"
)


Row = dict[str, float | None]


@dataclass(frozen=True)
class PlotSeries:
    """matplotlibで描く1系列分の表示設定。"""

    column: str
    color: str
    alpha: float
    linewidth: float


@dataclass(frozen=True)
class TimeSeriesPanel:
    """matplotlibの時系列パネル1枚分の設定。"""

    series: list[PlotSeries]
    title: str
    ylabel: str
    step: bool = False


@dataclass(frozen=True)
class PanelBounds:
    """Tkのキャンバス上で1パネルが占める範囲。"""

    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class TkPanel:
    """Tkで描く1パネル分の入力データ。"""

    bounds: PanelBounds
    x_values: list[float]
    series: list[tuple[str, str]]
    rows: list[Row]
    label: str


@dataclass(frozen=True)
class PanelScale:
    """データ座標をTkキャンバス座標に変換するための範囲情報。"""

    bounds: PanelBounds
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def sx(self, value: float) -> float:
        """X軸のデータ値をキャンバス座標に変換する。"""
        width = self.bounds.right - self.bounds.left
        return (
            self.bounds.left
            + ((value - self.x_min) / (self.x_max - self.x_min)) * width
        )

    def sy(self, value: float) -> float:
        """Y軸のデータ値をキャンバス座標に変換する。"""
        height = self.bounds.bottom - self.bounds.top
        return (
            self.bounds.bottom
            - ((value - self.y_min) / (self.y_max - self.y_min)) * height
        )


def display_name(column: str) -> str:
    """CSVの列名を画面表示用の日本語名に変換する。"""
    return DISPLAY_NAMES.get(column, column)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="Processingで保存したmicro:bitのCSVログをグラフ表示します。"
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help=(
            "分析するCSVファイル。省略すると "
            "processing/logs/ 内の最新 session_*_sensor.csv を使います。"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="グラフ画像の保存先。matplotlibが必要です。",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="グラフ画面を開きません。画像保存だけしたいときに使います。",
    )
    parser.add_argument(
        "--milliseconds",
        action="store_true",
        help="横軸を秒ではなくミリ秒で表示します。",
    )
    return parser.parse_args()


def latest_csv_path() -> Path:
    """ログフォルダから最新CSVを返す。"""
    for pattern in ("session_*_sensor.csv", "session_*.csv", "log_*.csv"):
        candidates = list(DEFAULT_LOG_DIR.glob(pattern))
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
    raise FileNotFoundError(f"CSVログが見つかりません: {DEFAULT_LOG_DIR}")


def to_float(value: str | None) -> float | None:
    """文字列を有限のfloatに変換し、空値や不正値はNoneにする。"""
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
    """列ごとの許容範囲を外れた値をNoneにする。"""
    if value is None:
        return None

    bounds = BOUNDED_COLUMNS.get(column)
    if bounds is not None:
        low, high = bounds
        if value < low or value > high:
            return None

    return value


def load_rows(csv_path: Path) -> list[Row]:
    """CSVファイルを読み込み、数値列だけを正規化した行リストで返す。"""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
    if not csv_path.is_file():
        raise ValueError(f"CSVのパスがファイルではありません: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"CSVにヘッダー行がありません: {csv_path}")
        if "elapsed_ms" not in reader.fieldnames:
            raise ValueError("CSVに必要な列 elapsed_ms がありません")

        rows: list[Row] = []
        for csv_row in reader:
            row = {
                column: normalize_value(column, to_float(csv_row.get(column)))
                for column in NUMERIC_COLUMNS
            }
            if row["elapsed_ms"] is not None:
                rows.append(row)

    if not rows:
        raise ValueError(f"elapsed_msを読める行がありません: {csv_path}")
    return rows


def values(rows: Iterable[Row], column: str) -> list[float | None]:
    """指定列の値を行リストから取り出す。"""
    return [row.get(column) for row in rows]


def clean_pairs(
    x_values: Iterable[float | None], y_values: Iterable[float | None]
) -> list[tuple[float, float]]:
    """X/Yのどちらかが欠けている点を除いたペアを返す。"""
    return [
        (x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None
    ]


def time_axis(rows: list[Row], milliseconds: bool) -> tuple[list[float], str]:
    """elapsed_ms列から横軸の値とラベルを作る。"""
    elapsed_ms = [value or 0.0 for value in values(rows, "elapsed_ms")]
    start_ms = elapsed_ms[0]
    divisor = 1.0 if milliseconds else 1000.0
    label = "経過時間（ミリ秒）" if milliseconds else "経過時間（秒）"
    return [((value - start_ms) / divisor) for value in elapsed_ms], label


def print_summary(csv_path: Path, rows: list[Row]) -> None:
    """読み込めたCSVの概要を標準出力に表示する。"""
    present = [
        column
        for column in NUMERIC_COLUMNS
        if any(row.get(column) is not None for row in rows)
    ]
    print(f"読み込んだCSV: {csv_path}")
    print(f"使用できる行数: {len(rows)}")
    print("読み込めたデータ: " + ", ".join(display_name(column) for column in present))


def configure_matplotlib_japanese(plt: Any) -> None:
    """matplotlibで日本語とマイナス記号が表示できるようにする。"""
    # pylint: disable=import-outside-toplevel
    from matplotlib import font_manager

    font_names = {font.name for font in font_manager.fontManager.ttflist}
    candidates = [
        "Hiragino Sans",
        "Hiragino Maru Gothic Pro",
        "Yu Gothic",
        "YuGothic",
        "Meiryo",
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAexGothic",
    ]

    for font_name in candidates:
        if font_name in font_names:
            plt.rcParams["font.family"] = font_name
            break

    plt.rcParams["axes.unicode_minus"] = False


def plot_csv(
    csv_path: Path, output: Path | None, show: bool, milliseconds: bool
) -> None:
    """CSVを読み込み、matplotlibまたはTkでグラフ表示する。"""
    rows = load_rows(csv_path)
    print_summary(csv_path, rows)

    try:
        # pylint: disable=import-outside-toplevel
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        if output:
            raise SystemExit(
                "--output で画像保存するには matplotlib が必要です。"
                "インストール: python3 -m pip install matplotlib"
            ) from exc
        if show:
            plot_csv_tk(csv_path, rows, milliseconds)
        return

    configure_matplotlib_japanese(plt)
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
            ],
            "加速度",
            "加速度",
        ),
    )

    plot_time_series(
        axes[1],
        time_values,
        rows,
        TimeSeriesPanel(
            [
                PlotSeries("input_x_smooth", "tab:brown", 1.0, 1.6),
                PlotSeries("input_y_smooth", "tab:purple", 1.0, 1.6),
                PlotSeries("tilt_x", "tab:blue", 1.0, 1.6),
                PlotSeries("speed_modifier", "tab:green", 1.0, 1.6),
            ],
            "加工済み入力",
            "値",
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
            "イベント",
            "状態",
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
            "追加センサー",
            "値",
        ),
    )

    for axis in axes:
        axis.set_xlabel(time_label)

    fig.tight_layout()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160)
        print(f"グラフ画像を保存しました: {output}")

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
    """matplotlibの1パネルに複数系列の時系列データを描く。"""
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
    """matplotlibが使えない環境向けにTkで簡易グラフを表示する。"""
    # pylint: disable=import-outside-toplevel
    import tkinter as tk
    from tkinter import ttk

    time_values, time_label = time_axis(rows, milliseconds)

    root = tk.Tk()
    root.title(f"CSVグラフ - {csv_path.name}")
    root.geometry("1100x800")

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    title = ttk.Label(frame, text=csv_path.name, font=("", 16, "bold"))
    title.pack(anchor=tk.W)

    subtitle = ttk.Label(
        frame,
        text=f"{len(rows)}行 / 横軸: {time_label}",
    )
    subtitle.pack(anchor=tk.W, pady=(2, 10))

    canvas = tk.Canvas(frame, background="white", highlightthickness=1)
    canvas.pack(fill=tk.BOTH, expand=True)

    legend = ttk.Label(
        frame,
        text=(
            "加速度: ax/ay/az  入力: x/y/tilt  "
            "状態: 発射/シールド/ボム  位置: player/target"
        ),
    )
    legend.pack(anchor=tk.W, pady=(8, 0))

    def redraw(_event: object | None = None) -> None:
        """ウィンドウサイズに合わせてTkキャンバスを描き直す。"""
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
                ],
                rows,
                "加速度",
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
                "加工済み入力",
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
                "追加センサー",
            ),
        )

    canvas.bind("<Configure>", redraw)
    root.mainloop()


def draw_panel(
    canvas: Any,
    panel: TkPanel,
) -> None:
    """Tkキャンバスに1枚分の折れ線グラフを描く。"""
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
    """Tkパネル用の軸範囲を計算する。"""
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
    """Tkパネルの枠、タイトル、横罫線、Y軸ラベルを描く。"""
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
    """コマンドライン実行時の入口。"""
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
