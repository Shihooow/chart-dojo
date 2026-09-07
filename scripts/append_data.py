#!/usr/bin/env python3
"""
data.json に、新しく取得した実際の日足データを追記するスクリプト。

使い方:
    python3 scripts/append_data.py scripts/tmp_new.json

scripts/tmp_new.json の形式(証券コードごとに新しい行の配列。1行以上、複数日分まとめてもOK):
{
  "7203": [
    {"date": "2026-09-08", "o": 3100, "h": 3150, "l": 3090, "c": 3130, "v": 21000000}
  ],
  "6758": [
    {"date": "2026-09-08", "o": 3900, "h": 3950, "l": 3880, "c": 3920, "v": 12000000}
  ]
}

- 既に data.json に存在する date は上書きせずスキップする(重複追記を防止)。
- turnover (取引代金の概算 = close * volume) はこのスクリプトが自動計算する。
- 銘柄ごとに date 昇順を維持する。
- watchlist.json にあるがまだ data.json に無い銘柄コードは、新規セクションとして追加できる。
"""
import json, sys, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE, "data.json")
WATCHLIST_PATH = os.path.join(BASE, "watchlist.json")

def main():
    if len(sys.argv) < 2:
        print("usage: python3 scripts/append_data.py <new_rows.json>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        new_rows = json.load(f)

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        watchlist = {w["code"]: w["name"] for w in json.load(f)}

    by_code = {s["code"]: s for s in data["stocks"]}
    added_total = 0

    for code, rows in new_rows.items():
        if code not in by_code:
            by_code[code] = {"code": code, "name": watchlist.get(code, code), "candles": []}
            data["stocks"].append(by_code[code])
        stock = by_code[code]
        existing_dates = {c["date"] for c in stock["candles"]}
        added = 0
        for r in rows:
            if r["date"] in existing_dates:
                continue
            candle = {
                "date": r["date"],
                "o": float(r["o"]),
                "h": float(r["h"]),
                "l": float(r["l"]),
                "c": float(r["c"]),
                "v": int(r["v"]),
            }
            candle["turnover"] = round(candle["c"] * candle["v"])
            stock["candles"].append(candle)
            existing_dates.add(r["date"])
            added += 1
        stock["candles"].sort(key=lambda c: c["date"])
        if added:
            print(f"{code} {stock['name']}: +{added}件 (合計 {len(stock['candles'])}件)")
        added_total += added

    if added_total == 0:
        print("追加された行はありませんでした(すべて既存の日付と重複)。")
    else:
        from datetime import date
        data["generated"] = date.today().isoformat()
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"data.json を更新しました(合計 +{added_total}件)。")

if __name__ == "__main__":
    main()
