"""Register and list CSV records, and rank them by save rate."""

import csv
import json
import secrets
import sqlite3
from contextlib import closing
from decimal import Decimal
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs


DIRECTORY = Path(__file__).resolve().parent
SAMPLE = DIRECTORY / "sample_data.csv"
DATABASE = DIRECTORY / "records.sqlite3"
FORM_TOKEN = secrets.token_urlsafe(32)


def calculate_save_rate(fields, saves_index, reach_index):
    try:
        saves = int(fields[saves_index])
        reach = int(fields[reach_index])
    except ValueError:
        return None
    if saves < 0 or reach <= 0:
        return None
    return Decimal(saves) * 100 / reach


def render_ranking(rates):
    ranked = sorted(
        ((record_id, rate) for record_id, rate in rates.items() if rate is not None),
        key=lambda entry: entry[1],
        reverse=True,
    )
    if not ranked:
        return "<p>保存率を計算できるデータがありません。</p>"
    scale = max(Decimal(100), ranked[0][1])
    bars = "".join(
        f'<li><span>登録ID {record_id}</span> <strong>{rate:.2f}%</strong>'
        f'<div class="bar-track" aria-hidden="true">'
        f'<div class="bar" style="width: {rate / scale:.4%}"></div></div></li>'
        for record_id, rate in ranked
    )
    return f'<ol class="ranking">{bars}</ol>'


def build_analysis_summary(record_count, rates, has_rate_columns):
    lines = ["## 分析サマリー", "", f"- 登録件数: {record_count}件"]
    if not has_rate_columns:
        lines.append("- 保存率: 「保存数」と「リーチ数」の列が必要です。")
        return "\n".join(lines)

    valid_rates = {record_id: rate for record_id, rate in rates.items() if rate is not None}
    lines.append(f"- 保存率の算出件数: {len(valid_rates)}件 / {record_count}件")
    if valid_rates:
        average = sum(valid_rates.values()) / len(valid_rates)
        top_id, top_rate = max(valid_rates.items(), key=lambda entry: entry[1])
        lines.extend([
            f"- 平均保存率（登録ごとの単純平均）: {average:.2f}%",
            f"- 最高保存率: {top_rate:.2f}%（登録ID {top_id}）",
        ])
    else:
        lines.append("- 保存率を計算できるデータがありません。")
    return "\n".join(lines)


def initialize():
    with closing(sqlite3.connect(DATABASE)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS schema_info (columns TEXT NOT NULL)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS records "
            "(id INTEGER PRIMARY KEY, fields TEXT NOT NULL)"
        )
        saved = db.execute("SELECT columns FROM schema_info").fetchone()
        if saved:
            return json.loads(saved[0])

        with SAMPLE.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            columns = next(reader, [])
            if not columns or any(not name.strip() for name in columns):
                raise ValueError("CSVのヘッダーに空の列名があります。")
            if len(set(columns)) != len(columns):
                raise ValueError("CSVのヘッダーに重複した列名があります。")
            for row in reader:
                if not row:
                    continue
                if len(row) != len(columns):
                    raise ValueError(f"CSVの{reader.line_num}行目の列数が一致しません。")
                db.execute("INSERT INTO records (fields) VALUES (?)", (json.dumps(row),))
        db.execute("INSERT INTO schema_info VALUES (?)", (json.dumps(columns),))
        return columns


class App(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        columns = self.server.columns
        inputs = "".join(
            f'<label>{escape(name)}<input name="field_{index}" type="text"></label>'
            for index, name in enumerate(columns)
        )
        headings = "".join(f'<th scope="col">{escape(name)}</th>' for name in columns)
        column_indices = {name.strip(): index for index, name in enumerate(columns)}
        has_rate_columns = {"保存数", "リーチ数"} <= column_indices.keys()
        with closing(sqlite3.connect(DATABASE)) as db:
            records = [
                (record_id, json.loads(fields))
                for record_id, fields in db.execute("SELECT id, fields FROM records ORDER BY id")
            ]
        rates = {}
        ranking = "<p>保存率の計算には「保存数」と「リーチ数」の列が必要です。</p>"
        if has_rate_columns:
            rates = {
                record_id: calculate_save_rate(
                    fields, column_indices["保存数"], column_indices["リーチ数"]
                )
                for record_id, fields in records
            }
            headings = f'<th scope="col">登録ID</th>{headings}<th scope="col">保存率</th>'
            ranking = render_ranking(rates)

        rows = []
        for record_id, fields in records:
            cells = "".join(f"<td>{escape(value)}</td>" for value in fields)
            if has_rate_columns:
                rate = rates[record_id]
                label = f"{rate:.2f}%" if rate is not None else "算出不可"
                cells = f"<td>{record_id}</td>{cells}<td>{label}</td>"
            rows.append(f"<tr>{cells}</tr>")
        column_count = len(columns) + (2 if has_rate_columns else 0)
        table_body = "".join(rows) or (
            f'<tr><td colspan="{column_count}">登録データはありません。</td></tr>'
        )
        summary = escape(build_analysis_summary(len(records), rates, has_rate_columns))
        page = f"""<!doctype html>
<html lang="ja">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>データ登録</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; padding: 0 1rem;
          max-width: 64rem; color: #182423; background: #f6f8f7; }}
  form {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
          gap: 1rem; padding: 1rem; background: white; border: 1px solid #cddad6; }}
  label {{ display: grid; gap: .4rem; }}
  input, button {{ font: inherit; padding: .55rem; border: 1px solid #768c85; }}
  button {{ grid-column: 1 / -1; justify-self: start; background: #175e4e;
            color: white; cursor: pointer; padding-inline: 1.25rem; }}
  .table {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; background: white; }}
  th, td {{ border: 1px solid #cddad6; text-align: left; padding: .65rem;
            white-space: pre-wrap; }}
  th {{ background: #e3eeea; }}
  .ranking {{ padding-inline-start: 2rem; }}
  .ranking li {{ padding: .35rem 0; }}
  .bar-track {{ background: #e3eeea; margin-top: .25rem; }}
  .bar {{ height: .65rem; background: #175e4e; }}
  .summary {{ white-space: pre-wrap; padding: 1rem; background: white;
              border: 1px solid #cddad6; }}
</style>
<main>
  <h1>データ登録</h1>
  <form method="post" action="/">
    <input type="hidden" name="token" value="{FORM_TOKEN}">
    {inputs}
    <button type="submit">登録</button>
  </form>
  <h2>登録一覧</h2>
  <div class="table"><table><thead><tr>{headings}</tr></thead>
  <tbody>{table_body}</tbody></table></div>
  <h2>保存率ランキング</h2>
  {ranking}
  <section aria-label="分析サマリー">
    <pre class="summary"><code>{summary}</code></pre>
  </section>
</main>
</html>"""
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 <= length <= 1_000_000:
                raise ValueError
            form = parse_qs(
                self.rfile.read(length).decode("ascii"),
                keep_blank_values=True,
                errors="strict",
                max_num_fields=len(self.server.columns) + 1,
            )
        except ValueError:
            self.send_error(400)
            return
        if form.get("token") != [FORM_TOKEN]:
            self.send_error(403)
            return
        fields = [form.get(f"field_{index}", []) for index in range(len(self.server.columns))]
        if any(len(values) != 1 for values in fields):
            self.send_error(400)
            return
        with closing(sqlite3.connect(DATABASE)) as db, db:
            db.execute(
                "INSERT INTO records (fields) VALUES (?)",
                (json.dumps([value for (value,) in fields]),),
            )
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def main():
    try:
        columns = initialize()
    except FileNotFoundError:
        raise SystemExit(f"初期データのCSVを配置してください。 {SAMPLE}") from None
    except (csv.Error, UnicodeError, ValueError) as error:
        raise SystemExit(f"初期データの読み込みに失敗しました。 {error}") from None

    with HTTPServer(("127.0.0.1", 8000), App) as server:
        server.columns = columns
        print("ブラウザーで http://127.0.0.1:8000/ を開いてください。", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
