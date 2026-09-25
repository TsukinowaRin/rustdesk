#!/usr/bin/env python3
"""この案件（ハーネス V3.1.0 の開発）のダッシュボード 1 枚。材料は harness/dashboard_data.py の JSON。

見た目はこの案件のためだけに書く（テンプレにしない）。決まりは 3 つだけ:
数字は札に / 状態は色に / 長文は要点に。外部の JS・CSS は読み込まない。
  python3 docs/dashboard/build.py [<data.json>] [<出力.html>]
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E = lambda v: html.escape(str(v), quote=True)

CSS = """
:root{--bg:#f7f5f0;--card:#fffdf9;--ink:#22201c;--dim:#645d54;--line:#dcd6cc;--ok:#1f7a4d;--ng:#a8322a;--wait:#9a6b12;--run:#345c7d;--accent:#345c7d}
@media (prefers-color-scheme:dark){:root{--bg:#16171a;--card:#1f2024;--ink:#ebe8e2;--dim:#a7a19a;--line:#34363b;--ok:#63c893;--ng:#f08a80;--wait:#e0b34d;--run:#8fb8de;--accent:#8fb8de}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,system-ui,sans-serif;line-height:1.7;font-size:15px}
.wrap{max-width:1100px;margin:0 auto;padding:22px 18px 70px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;border-bottom:3px solid var(--ink);padding-bottom:10px;margin-bottom:18px}
h1{font-size:1.45rem;margin:0}.stamp{color:var(--dim);font-size:.85rem}
h2{font-size:1.05rem;margin:30px 0 10px;padding-left:10px;border-left:5px solid var(--accent)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi .l{color:var(--dim);font-size:.8rem}.kpi .v{font-size:1.9rem;font-weight:700;line-height:1.2}.kpi .s{color:var(--dim);font-size:.8rem}
.kpi.warn .v{color:var(--ng)}
.bar{height:6px;background:var(--line);border-radius:3px;margin-top:8px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;font-size:.9rem}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:.8rem;white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;padding:1px 9px;border-radius:999px;font-size:.78rem;font-weight:600;border:1px solid;white-space:nowrap}
.ok{color:var(--ok);border-color:var(--ok)}.ng{color:var(--ng);border-color:var(--ng)}.run{color:var(--run);border-color:var(--run)}.wait{color:var(--wait);border-color:var(--wait)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--wait);border-radius:10px;padding:12px 14px}
.card h3{margin:0 0 6px;font-size:.95rem}.card dl{margin:0;display:grid;grid-template-columns:5.5em 1fr;gap:2px 8px;font-size:.88rem}
.card dt{color:var(--dim)}.card dd{margin:0}.card .rec{margin-top:8px;padding:6px 10px;border-radius:6px;background:color-mix(in srgb,var(--wait) 12%,transparent);font-size:.9rem}
details{margin-top:6px}summary{cursor:pointer;color:var(--dim);font-size:.82rem}pre{white-space:pre-wrap;font-size:.82rem;margin:6px 0 0}
.empty{color:var(--dim);padding:10px 0}
.reply{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0}.reply b{font-family:ui-monospace,Consolas,monospace}
blockquote{margin:4px 0 0;padding-left:10px;border-left:3px solid var(--line);color:var(--dim)}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:10px;color:var(--dim);font-size:.8rem}
"""

STATUS = {  # 材料の「状態」の言葉 → 色と短い言葉
    "終了": ("ok", "終了"), "成功": ("ok", "成功"), "失敗": ("ng", "失敗"), "実行中": ("run", "実行中"), "開始": ("run", "実行中"),
    "未実行": ("wait", "未実行"), "報告なし": ("ng", "報告なし"),
}


def pill(status: str, exit_code=None) -> str:
    cls, label = STATUS.get(status, ("wait", status or "不明"))
    if status == "終了" and exit_code not in (None, 0):
        cls, label = "ng", f"終了 {exit_code}"
    return f'<span class="pill {cls}">{E(label)}</span>'


def card_fields(text: str) -> tuple[str, dict, str]:
    """上流の型（approval_queue.md）の 1 枚を、題・欄・推奨に分ける。読めない行は details に残す。"""
    title, fields, rest = "", {}, []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## ") and not title:
            title = s[3:]
        elif s.startswith("- ") and ": " in s:
            k, v = s[2:].split(": ", 1)
            fields[k.strip()] = v.strip()
        elif s:
            rest.append(s)
    return title, fields, "\n".join(rest)


def build(data: dict) -> str:
    tasks = data.get("tasks", [])
    cards = data.get("cards", [])
    unread = [r for r in data.get("inbox", []) if not r.get("read")]
    costs = data.get("costs", {})

    done = sum(1 for t in tasks if t.get("status") == "終了" and (t.get("exit") in (None, 0)))
    failed = sum(1 for t in tasks if t.get("status") in ("失敗", "報告なし") or (t.get("exit") not in (None, 0)))
    running = sum(1 for t in tasks if t.get("status") in ("実行中", "開始"))
    secs = [t["seconds"] for t in tasks if isinstance(t.get("seconds"), (int, float))]
    known_cost = {k: v for k, v in costs.items() if v}
    total_tokens = sum(known_cost.values())

    kpis = [
        ("依頼", f"{done} / {len(tasks)}", f"終了 {done} · 実行中 {running} · 落ちた {failed}", "", done / len(tasks) if tasks else 0),
        ("未回答のカード", str(len(cards)), "人の裁定待ち", "warn" if cards else "", None),
        ("受信箱の未読", str(len(unread)), "スマホからの返事", "warn" if unread else "", None),
        ("費用（トークン）", f"{total_tokens:,}" if total_tokens else "不明", "取れた担い手: " + (", ".join(sorted(known_cost)) or "なし"), "", None),
        ("1 件の平均", f"{int(sum(secs) / len(secs))} 秒" if secs else "—", f"{len(secs)} 件の実測", "", None),
    ]
    kpi_html = ""
    for label, value, sub, cls, ratio in kpis:
        bar = f'<div class="bar"><i style="width:{int(ratio * 100)}%"></i></div>' if ratio is not None else ""
        kpi_html += f'<div class="kpi {cls}"><div class="l">{E(label)}</div><div class="v">{E(value)}</div><div class="s">{E(sub)}</div>{bar}</div>'

    rows = ""
    for t in sorted(tasks, key=lambda t: t.get("id", ""), reverse=True):
        tok = f'{t["tokens"]:,}' if isinstance(t.get("tokens"), int) else "—"
        sec = str(t["seconds"]) if t.get("seconds") is not None else "—"
        rows += (f'<tr><td><code>{E(t.get("id", ""))}</code></td><td>{pill(t.get("status", ""), t.get("exit"))}</td>'
                 f'<td>{E(t.get("title", ""))}</td><td>{E(t.get("member", ""))}</td><td class="num">{E(sec)}</td><td class="num">{E(tok)}</td></tr>')
    task_table = (f'<div class="scroll"><table><thead><tr><th>ID</th><th>状態</th><th>題</th><th>担い手</th><th>秒</th><th>トークン</th></tr></thead>'
                  f'<tbody>{rows}</tbody></table></div>') if rows else '<p class="empty">まだ依頼が無い</p>'

    card_html = ""
    for c in cards:
        title, f, rest = card_fields(c.get("text", ""))
        dl = "".join(f"<dt>{E(k)}</dt><dd>{E(f[k])}</dd>" for k in ("種別", "内容", "現物", "取り消し可能性", "無回答時") if k in f)
        rec = f'<div class="rec">推奨: {E(f["推奨"])}</div>' if "推奨" in f else ""
        more = f"<details><summary>全文</summary><pre>{E(c.get('text', ''))}</pre></details>"
        card_html += f'<div class="card"><h3>{E(title or c.get("id", ""))}</h3><dl>{dl}</dl>{rec}{more}</div>'
    cards_block = f'<div class="cards">{card_html}</div>' if card_html else '<p class="empty">なし。人の裁定待ちは 0 枚</p>'

    reply_html = "".join(
        f'<div class="reply"><b>{E(r.get("ref") or "ID なし")}</b> <span class="stamp">{E(r.get("ts", ""))}</span>'
        f'<blockquote>{E(r.get("text", ""))}</blockquote></div>' for r in unread) or '<p class="empty">未読なし</p>'

    cost_rows = ""
    top = max(known_cost.values()) if known_cost else 1
    for name, v in sorted(costs.items(), key=lambda kv: -(kv[1] or 0)):
        n = sum(1 for t in tasks if t.get("member") == name)
        bar = f'<div class="bar"><i style="width:{int((v or 0) / top * 100)}%"></i></div>'
        cost_rows += f'<tr><td>{E(name)}</td><td class="num">{n}</td><td class="num">{f"{v:,}" if v else "不明"}</td><td style="min-width:160px">{bar if v else ""}</td></tr>'
    cost_table = f'<div class="scroll"><table><thead><tr><th>担い手</th><th>件数</th><th>トークン</th><th></th></tr></thead><tbody>{cost_rows}</tbody></table></div>'

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><meta http-equiv="refresh" content="30"><title>ハーネス V3.1.0 の案件</title><style>{CSS}</style></head>
<body><div class="wrap">
<header><h1>ハーネス V3.1.0 の案件</h1><span class="stamp">{E(stamp)} に作り直した · 材料は .loop/dashboard/data.json</span></header>
<div class="kpis">{kpi_html}</div>
<h2>未回答のカード（人の裁定待ち）</h2>{cards_block}
<h2>受信箱の未読（スマホからの返事）</h2>{reply_html}
<h2>依頼（新しい順）</h2>{task_table}
<h2>担い手ごとの費用</h2>{cost_table}
<footer>この 1 枚はこの案件のためだけに書いた（テンプレではない）。材料の作り方は harness/dashboard_data.py、返事の道は harness/bridge/telegram.py。</footer>
</div></body></html>"""


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".loop/dashboard/data.json"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / ".loop/dashboard/index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build(json.loads(source.read_text(encoding="utf-8"))), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
