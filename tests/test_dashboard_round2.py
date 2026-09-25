#!/usr/bin/env python3
"""2 周目の境界試験。網を使わず、一時フォルダと偽 API で確かめる。"""
import json
import os
import sys
import tempfile
import contextlib
import io
import shlex
import subprocess
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "harness"), str(ROOT / "docs/dashboard")]
import inbox
import dashboard_data
import judgment
import build
import dashboard_watch
from bridge import telegram


def test_global_telegram_config():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        loop = base / "sample-workspace/.loop"
        loop.mkdir(parents=True)
        config_home = base / "config"
        config_home.mkdir()
        (config_home / "telegram.env").write_text(
            "TELEGRAM_BOT_TOKEN=global-token\nTELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
        sent = []
        def fake_api(method, params, token):
            sent.append((method, params, token))
            return {"ok": True, "result": [] if method == "getUpdates" else {}}
        with patch.dict(os.environ, {"HARNESS_LOOP_DIR": str(loop), "HARNESS_CONFIG_HOME": str(config_home)}), \
                patch.object(telegram, "_api", side_effect=fake_api):
            telegram.send("質問")
            assert sent == [("sendMessage", {"chat_id": 42, "text": "質問"}, "global-token")], sent
            assert telegram.configured()
            assert dashboard_watch.status(loop).startswith("[sample-workspace] 依頼:")
            clock = [0.0]
            with patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(dashboard_watch.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                    patch.dict(os.environ, {"HARNESS_TESTING": "1"}):
                dashboard_watch.watch(loop, interval=1, hours=1 / 3600)
            assert sent[1][0] == "sendMessage" and sent[1][1]["text"].startswith("[sample-workspace] 依頼:"), sent
            assert sent[2][0] == "getUpdates", sent
            dashboard_watch.handle_replies(loop, [{"text": "/status", "chat_id": 42}, {"text": "/dash", "chat_id": 42}])
            assert sent[3][1]["text"].startswith("[sample-workspace] 依頼:"), sent
            assert sent[4][1]["caption"] == "[sample-workspace] ダッシュボード", sent
            result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/setup.py"), "status"],
                                    env=os.environ.copy(), capture_output=True, text=True)
            assert result.returncode == 0 and "Telegram の橋: あり（全体）" in result.stdout, result
            (loop / "telegram.env").write_text(
                "TELEGRAM_BOT_TOKEN=local-token\nTELEGRAM_CHAT_IDS=99\n", encoding="utf-8")
            telegram.send("作業場")
            assert sent[5] == ("sendMessage", {"chat_id": 99, "text": "作業場"}, "local-token"), sent
            telegram.whoami()
            assert [token for _, _, token in sent[-3:]] == ["local-token"] * 3, sent
            result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/setup.py"), "status"],
                                    env=os.environ.copy(), capture_output=True, text=True)
            assert result.returncode == 0 and "Telegram の橋: あり（この作業場）" in result.stdout, result
            (loop / "telegram.env").write_text("TELEGRAM_CHAT_IDS=99\n", encoding="utf-8")
            try:
                telegram.send("混ぜない")
                raise AssertionError("local の不足分を global で補った")
            except ValueError:
                pass
            (loop / "telegram.env").unlink()
            telegram.whoami()
            assert [token for _, _, token in sent[-3:]] == ["global-token"] * 3, sent


def test_finishing():
    with tempfile.TemporaryDirectory() as tmp:
        loop = Path(tmp)
        env = dict(os.environ, HARNESS_LOOP_DIR=str(loop), HARNESS_CONFIG_HOME=str(loop / "config"), HARNESS_JUDGMENT_HOME=str(loop / "missing-home"), HARNESS_TESTING="1")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/setup.py"), "status"],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0 and "Telegram の橋: なし（cp harness/telegram.env.example ~/.config/harness/telegram.env → 値を入れる）" in result.stdout, result
        for args in (["poll", "--timeout", "0"], ["send", "質問"]):
            result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/bridge/telegram.py"), *args],
                                    env=env, capture_output=True, text=True)
            assert result.returncode != 0
            assert result.stdout == "" and result.stderr.splitlines() == [
                "Telegram の設定が無い: .loop/telegram.env または ~/.config/harness/telegram.env。cp harness/telegram.env.example ~/.config/harness/telegram.env を打ち、TELEGRAM_BOT_TOKEN と TELEGRAM_CHAT_IDS を書く"], result.stderr

        row = inbox.append("最新の返事", loop=loop)
        result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/judgment.py"), "brief"],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert result.returncode != 0
        assert result.stdout.index("> 最新の返事") < result.stdout.index("先に: python3 harness/judgment.py init"), result.stdout

        before = (loop / "inbox.jsonl").read_text(encoding="utf-8").count("\n")
        for _ in range(2):
            result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/inbox.py"), "read", row["id"]],
                                    env=env, capture_output=True, text=True)
            assert result.returncode == 0 and result.stdout == f"既読: {row['id']}\n" and result.stderr == ""
            assert (loop / "inbox.jsonl").read_text(encoding="utf-8").count("\n") == before + 1

        home = loop / "missing-home"
        home.mkdir()
        (home / "config.env").write_text("", encoding="utf-8")
        (home / "judgment_model.md").write_text("## 判断原則\n\n## 鮮度\n", encoding="utf-8")
        (home / "approval_queue.md").write_text("## 未処理\n---\n## 処理済み\n", encoding="utf-8")
        inbox.append("画面に出る返事", loop=loop)
        hook = loop / "dashboard/build"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text("#!/bin/sh\nexec python3 " + shlex.quote(str(ROOT / "docs/dashboard/build.py")) + " \"$@\"\n", encoding="utf-8")
        hook.chmod(0o755)
        result = subprocess.run([sys.executable, "-B", str(ROOT / "harness/judgment.py"), "brief"],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        data, index = loop / "dashboard/data.json", loop / "dashboard/index.html"
        assert "画面に出る返事" in data.read_text(encoding="utf-8")
        assert "画面に出る返事" in index.read_text(encoding="utf-8")
        assert index.stat().st_mtime_ns >= data.stat().st_mtime_ns


def main():
    test_global_telegram_config()
    with tempfile.TemporaryDirectory() as tmp:
        loop = Path(tmp)
        for name in ("T-0924-02", "V-1"):
            d = loop / "tasks" / name
            d.mkdir(parents=True)
            (d / "task.md").write_text(f"# {name}\n", encoding="utf-8")
        (loop / "judgment").mkdir()
        (loop / "judgment/approval_queue.md").write_text(
            "## 未処理\n<!-- ### Q-FAKE -->\n### Q-2026-09-25-01 🔴\n- 内容: 確認\n---\n## 処理済み\n", encoding="utf-8")
        with patch.dict(os.environ, {"HARNESS_LOOP_DIR": str(loop), "HARNESS_CONFIG_HOME": str(loop / "config"), "HARNESS_TESTING": "1"}):
            refs = [inbox.append(s, loop=loop)["ref"] for s in (
                "Q-2026-09-25-01 OK", "T-0924-02 ダメ", "V-1 見た", "Q-FAKE いいえ", "T-NO 不明")]
            assert refs == ["Q-2026-09-25-01", "T-0924-02", "V-1", None, None], refs
            other_cards = loop / "other-judgment"
            other_cards.mkdir()
            (other_cards / "approval_queue.md").write_text("## 未処理\n### Q-ALT 🔴\n- 内容: 別置き場\n---\n## 処理済み\n", encoding="utf-8")
            with patch.dict(os.environ, {"HARNESS_JUDGMENT_HOME": str(other_cards)}):
                assert inbox.append("Q-ALT OK", loop=loop)["ref"] == "Q-ALT"
                assert [c["id"] for c in dashboard_data.collect(loop)["cards"]] == ["Q-ALT"]
            row = inbox.append("V-1 \x1b[31m\x00改行\nタブ\t", loop=loop)
            assert "\x1b" not in row["text"] and "\x00" not in row["text"]
            assert "\n" in row["text"] and "\t" in row["text"]
            assert inbox.append("V-1 重複", loop=loop, update_id=70)
            assert inbox.append("V-1 重複", loop=loop, update_id=70) is None
            assert inbox.main(["read", row["id"]]) == 0
            assert row["id"] not in [r["id"] for r in inbox.unread(loop)]
            assert inbox.main(["read", "--all"]) == 0 and not inbox.unread(loop)
            data = dashboard_data.collect(loop)
            assert "events" not in data and [c["id"] for c in data["cards"]] == ["Q-2026-09-25-01"]
            assert "Content-Security-Policy" in build.build(data)
            assert "default-src 'none'" in build.build(data)
            source = loop / "data.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(sys, "argv", ["build.py", str(source)]), patch.object(build, "ROOT", loop):
                assert build.main() == 0
            assert (loop / ".loop/dashboard/index.html").exists()
            assert not (loop / "docs/dashboard/index.html").exists()

            (loop / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
            def fake_api(method, params, token):
                assert token == "test-token"
                if method == "getUpdates":
                    assert params["timeout"] == 0
                    return {"ok": True, "result": [
                        {"update_id": 10, "message": {"chat": {"id": 42, "type": "group"}, "from": {"id": 42}, "text": "V-1 group"}},
                        {"update_id": 11, "message": {"chat": {"id": 42, "type": "private"}, "from": {"id": 99}, "text": "V-1 other"}},
                        {"update_id": 12, "message": {"chat": {"id": 42, "type": "private"}, "from": {"id": 42}, "text": "V-1 OK test-token"}},
                    ]}
                return {"ok": True, "result": {"message_id": 1}}
            with patch.object(telegram, "_api", fake_api):
                assert telegram.main(["send", "質問"]) == 0
                assert telegram.main(["poll", "--timeout", "0"]) == 0
                assert telegram.poll(timeout=0) == []
            (loop / "judgment/config.env").write_text("", encoding="utf-8")
            (loop / "judgment/judgment_model.md").write_text("## 判断原則\n\n## 鮮度\n", encoding="utf-8")
            queue = loop / "judgment/approval_queue.md"
            queue.write_text(queue.read_text(encoding="utf-8").replace("---\n## 処理済み", "### Q-SECOND 🟡\n- 内容: 後で書いたカード\n---\n## 処理済み"), encoding="utf-8")
            with patch.dict(os.environ, {"HARNESS_JUDGMENT_HOME": str(loop / "judgment")}):
                with patch.object(telegram, "_api", fake_api), contextlib.redirect_stdout(io.StringIO()) as output:
                    assert judgment.cmd_brief(None) == 0
                assert "> V-1 OK [REDACTED]" in output.getvalue()
            assert {c["id"] for c in json.loads((loop / "dashboard/data.json").read_text(encoding="utf-8"))["cards"]} == {"Q-2026-09-25-01", "Q-SECOND"}
            saved = [r for r in inbox.all_rows(loop) if r.get("update_id") == 12]
            assert len(saved) == 1 and "test-token" not in saved[0]["text"]
            assert all("group" not in r["text"] and "other" not in r["text"] for r in inbox.all_rows(loop))
            assert (loop / "telegram.offset").read_text(encoding="utf-8") == "13"
            dash = inbox.append("/dash", loop=loop, chat_id=42, update_id=13)
            status = inbox.append("/status", loop=loop, chat_id=42, update_id=14)
            assert dash["ref"] is None and status["ref"] is None
            assert all(r["id"] not in {dash["id"], status["id"]} for r in inbox.unread(loop))
            html = loop / "dashboard/index.html"
            html.write_text("<html>phone</html>", encoding="utf-8")
            requests = []
            def fake_urlopen(request, timeout):
                requests.append(request)
                return io.BytesIO(b'{"ok":true,"result":{}}')
            with patch.dict(os.environ, {"HARNESS_TESTING": "0"}), patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
                telegram.send_document(html, "画面", chat_id=42, thread_id=101)
            assert len(requests) == 1
            assert requests[0].get_header("Content-type").startswith("multipart/form-data; boundary=")
            assert b'name="document"; filename="index.html"' in requests[0].data
            assert b'name="message_thread_id"\r\n\r\n101\r\n' in requests[0].data
            assert b"<html>phone</html>" in requests[0].data
            with patch.object(telegram, "_api") as api:
                try:
                    telegram.send_document(html, "画面", chat_id=99)
                    raise AssertionError("unallowed chat accepted")
                except ValueError:
                    pass
                api.assert_not_called()
            (loop / "telegram.env").write_text("TELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
            try:
                telegram.send("質問")
                raise AssertionError("missing token accepted")
            except ValueError:
                pass
            (loop / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=test-token\n", encoding="utf-8")
            try:
                telegram.send("質問")
                raise AssertionError("missing chat accepted")
            except ValueError:
                pass
    test_finishing()
    print("ok  test_dashboard_round2: 実在 ID・重複・既読・私信・秘密・CSP・出力先・multipart・許可 chat")


if __name__ == "__main__":
    main()
