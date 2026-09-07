#!/usr/bin/env python3
"""
data.json に、新しく取得した実際の日足データを追記し、
週足・月足を日足データから自動集計して更新するスクリプト。

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
- 日足データが更新されるたびに、週足(月曜始まり)・月足(月初)を日足から自動集計して
  weekly / monthly を更新する。過去にシードした週足・月足のうち、現在の日足カバー範囲
  より古いものはそのまま保持する(上書きしない)。
"""
import json, sys, os
from datetime import date as _date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE, "data.json")
WATCHLIST_PATH = os.path.join(BASE, "watchlist.json")


def week_start(iso_date):
    y, m, d = map(int, iso_date.split("-"))
    dt = _date(y, m, d)
    monday = dt - timedelta(days=dt.weekday())
    return monday.isoformat()


def month_start(iso_date):
    y, m, _ = iso_date.split("-")
    return f"{y}-{m}-01"


def aggregate(daily, key_fn):
    groups = {}
    order = []
    for c in sorted(daily, key=lambda r: r["date"]):
        k = key_fn(c["date"])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(c)
    out = []
    for k in order:
        rows = groups[k]
        o = rows[0]["o"]
        c_ = rows[-1]["c"]
        h = max(r["h"] for r in rows)
        l = min(r["l"] for r in rows)
        v = sum(r["v"] for r in rows)
        turnover = sum(r.get("turnover", round(r["c"] * r["v"])) for r in rows)
        out.append({"date": k, "o": o, "h": h, "l": l, "c": c_, "v": v, "turnover": turnover})
    return out


def upsert(existing, computed):
    by_date = {r["date"]: r for r in existing}
    for r in computed:
        by_date[r["date"]] = r  # 集計対象期間は日足ベースで再計算した値に更新
    return sorted(by_date.values(), key=lambda r: r["date"])


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
            by_code[code] = {"code": code, "name": watchlist.get(code, code), "daily": [], "weekly": [], "monthly": []}
            data["stocks"].append(by_code[code])
        stock = by_code[code]
        stock.setdefault("daily", stock.pop("candles", []) if "candles" in stock else [])
        stock.setdefault("weekly", [])
        stock.setdefault("monthly", [])
        existing_dates = {c["date"] for c in stock["daily"]}
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
            stock["daily"].append(candle)
            existing_dates.add(r["date"])
            added += 1
        stock["daily"].sort(key=lambda c: c["date"])

        if added:
            # 日足から週足・月足を再集計し、対応する期間だけ更新する
            weekly_computed = aggregate(stock["daily"], week_start)
            monthly_computed = aggregate(stock["daily"], month_start)
            stock["weekly"] = upsert(stock["weekly"], weekly_computed)
            stock["monthly"] = upsert(stock["monthly"], monthly_computed)
            print(f"{code} {stock['name']}: +{added}件 (日足合計 {len(stock['daily'])}件 / 週足 {len(stock['weekly'])}件 / 月足 {len(stock['monthly'])}件)")
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
