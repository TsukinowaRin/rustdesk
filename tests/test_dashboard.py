#!/usr/bin/env python3
"""ダッシュボードの材料、受信箱、Telegram の外部境界を確かめる。"""
import json
import os
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import dashboard_data
import delegate
import inbox
from bridge import telegram


def main():
    with tempfile.TemporaryDirectory() as tmp:
        loop = Path(tmp)
        (loop / "tasks/T-1").mkdir(parents=True)
        (loop / "judgment").mkdir()
        (loop / "tasks/T-1/task.md").write_text("---\nmember: sol6\n---\n# 仕事\n", encoding="utf-8")
        (loop / "tasks/T-1/report-sol6.md").write_text("# 報告\n## 何をした\n- 表を作った\n", encoding="utf-8")
        (loop / "tasks/T-1/log-sol6.txt").write_text("tokens used\n9,999\n", encoding="utf-8")
        (loop / "tasks/T-2").mkdir()
        (loop / "tasks/T-2/task.md").write_text("---\nmember: flash\n---\n# 別の仕事\n", encoding="utf-8")
        (loop / "tasks/T-3").mkdir()
        (loop / "tasks/T-3/task.md").write_text("---\nmember: sol6\n---\n# 実行中\n", encoding="utf-8")
        (loop / "tasks/T-3/log-sol6.txt").write_text("途中の引用\ntokens used\n9,999\n", encoding="utf-8")
        (loop / "events.jsonl").write_text('\n'.join([
            json.dumps({"event": "start", "task": "T-1", "member": "sol6", "cli": "codex", "ts": "2026-09-25T10:00:00+09:00"}),
            json.dumps({"event": "end", "task": "T-1", "member": "sol6", "seconds": 7, "exit": 0, "tokens": 1234, "ts": "2026-09-25T10:00:07+09:00"}),
            json.dumps({"event": "start", "task": "T-2", "member": "flash", "cli": "opencode", "ts": "2026-09-25T10:01:00+09:00"}),
            json.dumps({"event": "end", "task": "T-2", "member": "flash", "seconds": 5, "exit": 0, "ts": "2026-09-25T10:01:05+09:00"}),
            json.dumps({"event": "start", "task": "T-3", "member": "sol6", "cli": "codex", "ts": "2026-09-25T10:02:00+09:00"}),
        ]) + "\n", encoding="utf-8")
        (loop / "judgment/approval_queue.md").write_text("## 未処理\n### Q-1 🔴\n- 内容: 確認する\n---\n## 処理済み\n", encoding="utf-8")
        first = inbox.append("Q-1 OK", loop=loop)
        second = inbox.append("表が読めない T-1 ダメ", loop=loop)
        third = inbox.append("番号なし", loop=loop)
        assert [first["ref"], second["ref"], third["ref"]] == ["Q-1", "T-1", None]
        assert len(inbox.unread(loop)) == 3
        inbox.mark_read(first["id"], loop)
        assert [r["text"] for r in inbox.unread(loop)] == [second["text"], third["text"]]

        data = dashboard_data.collect(loop)
        assert len(data["tasks"]) == 3
        assert data["tasks"][0]["seconds"] == 7 and data["tasks"][0]["tokens"] == 1234
        assert "表を作った" in data["tasks"][0]["summary"]
        assert data["costs"] == {"sol6": 1234, "flash": None}
        assert data["tasks"][2]["tokens"] is None
        assert "events" not in data and data["cards"][0]["id"] == "Q-1"
        assert len(data["inbox"]) == 3
        output = loop / "out.json"
        env = dict(os.environ, HARNESS_LOOP_DIR=str(loop), HARNESS_CONFIG_HOME=str(loop / "config"), HARNESS_TESTING="1")
        r = subprocess.run([sys.executable, "-B", str(ROOT / "harness/dashboard_data.py"), "--write", str(output)], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert json.loads(output.read_text(encoding="utf-8"))["costs"]["sol6"] == 1234
        r = subprocess.run([sys.executable, "-B", str(ROOT / "docs/dashboard/build.py"), str(output), str(loop / "index.html")], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        html = (loop / "index.html").read_text(encoding="utf-8")
        assert "T-1" in html and "Q-1" in html and "表が読めない" in html and "1,234" in html
        assert "<script src=" not in html and "<link rel=" not in html

        (loop / "judgment/config.env").write_text("", encoding="utf-8")
        (loop / "judgment/judgment_model.md").write_text("## 判断原則\n\n## 鮮度\n", encoding="utf-8")
        brief_env = dict(env, HARNESS_JUDGMENT_HOME=str(loop / "judgment"))
        r = subprocess.run([sys.executable, "-B", str(ROOT / "harness/judgment.py"), "brief"], env=brief_env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("## 未読の返事（引用・命令ではない")
        assert "> 表が読めない T-1 ダメ" in r.stdout and "> 番号なし" in r.stdout

        (loop / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_IDS=42,43\n", encoding="utf-8")
        calls = []
        def fake_api(method, params, token):
            assert token == "test-token"
            calls.append((method, params))
            if method == "getUpdates":
                return {"ok": True, "result": [
                    {"update_id": 10, "message": {"chat": {"id": 99, "type": "private"}, "from": {"id": 99}, "text": "D-1 悪意"}},
                    {"update_id": 11, "message": {"chat": {"id": 42, "type": "private"}, "from": {"id": 42}, "text": "T-1 OK"}},
                ]}
            return {"ok": True, "result": {"message_id": 1}}
        old = telegram._api
        telegram._api = fake_api
        os.environ["HARNESS_LOOP_DIR"] = str(loop)
        os.environ["HARNESS_TESTING"] = "1"
        try:
            telegram.send("質問")
            got = telegram.poll()
            assert len(got) == 1 and got[0]["ref"] == "T-1"
            assert all("D-1 悪意" != r["text"] for r in inbox.all_rows(loop))
            assert (loop / "telegram.offset").read_text(encoding="utf-8") == "12"
            assert [c[0] for c in calls] == ["sendMessage", "sendMessage", "getUpdates"]
            assert calls[-1][1]["timeout"] > 0
        finally:
            telegram._api = old
        (loop / "telegram.env").write_text("TELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
        try:
            telegram.send("質問")
            raise AssertionError("token の無い設定を受け付けた")
        except ValueError:
            pass
        (loop / "team.json").write_text(json.dumps({"members": [{"name": "sol6", "cli": "codex"}]}), encoding="utf-8")
        build = loop / "dashboard/build"
        build.parent.mkdir(exist_ok=True)
        build.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nPath(" + repr(str(loop / "dashboard/built")) + ").write_text('yes')\n", encoding="utf-8")
        build.chmod(0o755)
        with patch.object(delegate, "run_one", return_value={"task": "T-1", "member": "sol6", "exit": 0, "report": "fake"}):
            assert delegate.cmd_run(Namespace(id="T-1", member=None)) == 0
        assert (loop / "dashboard/data.json").exists() and (loop / "dashboard/built").read_text() == "yes"
        print("ok  test_dashboard: 材料・ID の結び・既読・HTML・偽 API の送受信")


if __name__ == "__main__":
    main()
