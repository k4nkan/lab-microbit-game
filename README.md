# lab-microbit

## 構成

```text
microbit/main.js
processing/TiltInvader.pde
processing/settings.pde
processing/game.pde
processing/log.pde
analytics/plot_input_csv.py
analytics/plot_game_csv.py
analytics/plot_logs.py
```

## 使い方

1. `microbit/main.js` の内容を MakeCode の JavaScript に貼り付けて、micro:bit に書き込みます。通常は操作用の `C,runtime,ax,ay,shake,A,B` だけを送信します。
2. micro:bit を USB でPCに接続します。
3. Processing で `processing/TiltInvader.pde` を開いて実行します。
4. micro:bitの左右傾きで移動、Aで発射、Bでシールドできます。移動は `ax/ay` を角度相当に変換して使います。
5. 汎用入力ログは `processing/logs/session_YYYYMMDD_HHMMSS_input.csv`、ゲームログは `processing/logs/session_YYYYMMDD_HHMMSS_game.csv` に毎フレーム保存されます。

画面右側の `serial` が `valid control`、`columns` が `7`、`valid rows` が増えていればmicro:bitの値を読めています。`waiting data` のままなら、micro:bit側がCSVを送っていません。`columns` が7以外でばらつく場合は、micro:bit側のプログラムとProcessing側の想定が合っていません。

`processing/client_id.txt` と `processing/logs/` は実行時に作成されるローカルデータなので、Git管理からは除外しています。

## Plot CSV logs

Open input and game logs in one wide window:

```bash
python3 analytics/plot_logs.py
```

Select a session:

```bash
python3 analytics/plot_logs.py --session 20260527_221115
```

Open each log separately:

```bash
python3 analytics/plot_input_csv.py
python3 analytics/plot_game_csv.py
```

Select files:

```bash
python3 analytics/plot_input_csv.py processing/logs/session_YYYYMMDD_HHMMSS_input.csv
python3 analytics/plot_game_csv.py processing/logs/session_YYYYMMDD_HHMMSS_game.csv
```

Saving an image requires `matplotlib`.

```bash
python3 -m pip install matplotlib
python3 analytics/plot_logs.py --session 20260527_221115 --output-dir graphs --no-show
```
