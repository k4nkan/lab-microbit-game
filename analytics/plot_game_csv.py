#!/usr/bin/env python3
"""Processingで記録したゲームCSVログをグラフ表示する。"""

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
    "elapsed_ms": "経過時間",
    "frame_count": "フレーム",
    "player_x": "プレイヤーX",
    "player_y": "プレイヤーY",
    "player_vx": "プレイヤー速度",
    "target_x": "ターゲットX",
    "target_y": "ターゲットY",
    "target_dx": "ターゲットDX",
    "target_dy": "ターゲットDY",
    "target_distance": "距離",
    "bullet_active": "弾あり",
    "bullet_x": "弾X",
    "bullet_y": "弾Y",
    "score": "スコア",
    "miss_count": "ミス",
    "shield_active": "シールド",
}

Row = dict[str, float | str | None]


@dataclass(frozen=True)
class GamePanel:
    """matplotlibのゲームログ用パネル設定。"""

    columns: list[str]
    title: str
    ylabel: str
    step: bool = False


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="Processingで保存したゲームログCSVをグラフ表示します。"
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        help="分析するCSVファイル。省略すると processing/logs/ 内の最新 session_*_game.csv を使います。",
    )
    parser.add_argument("-o", "--output", type=Path, help="グラフ画像の保存先。")
    parser.add_argument("--no-show", action="store_true", help="グラフ画面を開きません。")
    parser.add_argument(
        "--milliseconds",
        action="store_true",
        help="横軸を秒ではなくミリ秒で表示します。",
    )
    return parser.parse_args()


def latest_csv_path() -> Path:
    """ログフォルダから最新のゲームCSVを返す。"""
    candidates = list(DEFAULT_LOG_DIR.glob("session_*_game.csv"))
    if not candidates:
        raise FileNotFoundError(f"ゲームログが見つかりません: {DEFAULT_LOG_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def to_float(value: str | None) -> float | None:
    """文字列を有限のfloatへ変換し、不正値はNoneにする。"""
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
    """CSVファイルを読み込み、グラフ用の行リストを返す。"""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"CSVにヘッダー行がありません: {csv_path}")
        if "elapsed_ms" not in reader.fieldnames:
            raise ValueError("CSVに必要な列 elapsed_ms がありません")

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
        raise ValueError(f"elapsed_msを読める行がありません: {csv_path}")
    return rows


def values(rows: Iterable[Row], column: str) -> list[float | None]:
    """指定列の数値を取り出す。"""
    result: list[float | None] = []
    for row in rows:
        value = row.get(column)
        result.append(value if isinstance(value, float) else None)
    return result


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


def display_name(column: str) -> str:
    """CSV列名を表示名に変換する。"""
    return DISPLAY_NAMES.get(column, column)


def print_summary(csv_path: Path, rows: list[Row]) -> None:
    """読み込んだゲームログの概要を標準出力に表示する。"""
    event_counts: dict[str, int] = {}
    for row in rows:
        event_type = row.get("event_type")
        if isinstance(event_type, str) and event_type and event_type != "none":
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

    print(f"読み込んだCSV: {csv_path}")
    print(f"使用できる行数: {len(rows)}")
    print(f"最終score: {last_number(rows, 'score')}")
    print(f"最終miss_count: {last_number(rows, 'miss_count')}")
    if event_counts:
        print(
            "イベント: "
            + ", ".join(f"{key}={value}" for key, value in sorted(event_counts.items()))
        )


def last_number(rows: list[Row], column: str) -> str:
    """指定列の最後の数値を表示用文字列で返す。"""
    for row in reversed(rows):
        value = row.get(column)
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:.2f}"
    return ""


def configure_matplotlib_japanese(plt: Any) -> None:
    """matplotlibで日本語とマイナス記号を表示できるようにする。"""
    # pylint: disable=import-outside-toplevel,import-error
    from matplotlib import font_manager

    font_names = {font.name for font in font_manager.fontManager.ttflist}
    for font_name in (
        "Hiragino Sans",
        "Yu Gothic",
        "YuGothic",
        "Meiryo",
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAexGothic",
    ):
        if font_name in font_names:
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False


def plot_csv(
    csv_path: Path, output: Path | None, show: bool, milliseconds: bool
) -> None:
    """ゲームCSVを読み込み、matplotlibでグラフ表示する。"""
    rows = load_rows(csv_path)
    print_summary(csv_path, rows)

    try:
        # pylint: disable=import-outside-toplevel,import-error
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        if output:
            raise SystemExit(
                "--output で画像保存するには matplotlib が必要です。"
                "インストール: python3 -m pip install matplotlib"
            ) from exc
        return

    configure_matplotlib_japanese(plt)
    time_values, time_label = time_axis(rows, milliseconds)

    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=False)
    fig.suptitle(csv_path.name)

    plot_panel(
        axes[0],
        time_values,
        rows,
        GamePanel(["player_x", "target_x", "bullet_x"], "X位置", "x"),
    )
    plot_panel(
        axes[1],
        time_values,
        rows,
        GamePanel(["player_y", "target_y", "bullet_y"], "Y位置", "y"),
    )
    plot_panel(
        axes[2],
        time_values,
        rows,
        GamePanel(
            ["player_vx", "target_distance", "target_dx"],
            "操作とターゲット距離",
            "値",
        ),
    )
    plot_panel(
        axes[3],
        time_values,
        rows,
        GamePanel(
            ["score", "miss_count", "bullet_active", "shield_active"],
            "結果と状態",
            "状態",
            step=True,
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


def plot_panel(
    axis: Any,
    time_values: list[float],
    rows: list[Row],
    panel: GamePanel,
) -> None:
    """matplotlibの1パネルに複数系列の時系列データを描く。"""
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
    """コマンドライン実行時の入口。"""
    args = parse_args()
    plot_csv(
        csv_path=args.csv_path or latest_csv_path(),
        output=args.output,
        show=not args.no_show,
        milliseconds=args.milliseconds,
    )


if __name__ == "__main__":
    main()
