#!/usr/bin/env python3
"""見張りの更新条件と停止条件を一時 .loop/ で確かめる。"""
import json
import io
import os
import sys
import tempfile
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import dashboard_watch
import dashboard_data
import inbox
from bridge import telegram


def main():
    with tempfile.TemporaryDirectory() as tmp:
        loop = Path(tmp)
        task = loop / "tasks/T-1/task.md"
        task.parent.mkdir(parents=True)
        task.write_text("# 最初\n", encoding="utf-8")
        clock = [0.0]
        calls_after_sleep = []
        def sleep(seconds):
            clock[0] += seconds
            calls_after_sleep.append(refresher.call_count)
            if clock[0] == 60:
                task.write_text("# 更新後\n", encoding="utf-8")

        with patch.dict(os.environ, {"HARNESS_TESTING": "1", "HARNESS_CONFIG_HOME": str(loop / "config")}), \
                patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(dashboard_watch.time, "sleep", side_effect=sleep), \
                patch.object(dashboard_watch.telegram, "poll", side_effect=AssertionError("telegram.env が無い")), \
                patch.object(dashboard_data, "refresh", wraps=dashboard_data.refresh) as refresher:
            dashboard_watch.watch(loop, interval=30, hours=90 / 3600)
            assert refresher.call_count == 2, refresher.call_count
        assert calls_after_sleep == [1, 1, 2], calls_after_sleep
        data = loop / "dashboard/data.json"
        assert json.loads(data.read_text(encoding="utf-8"))["tasks"][0]["title"] == "更新後"

        data.write_text("sentinel", encoding="utf-8")
        with patch.dict(os.environ, {"HARNESS_TESTING": "1"}), \
                patch.object(dashboard_watch.telegram, "poll", side_effect=AssertionError("once で受信しない")), \
                patch.object(dashboard_data, "refresh", wraps=dashboard_data.refresh) as refresher:
            dashboard_watch.watch(loop, interval=30, hours=8, once=True)
            assert refresher.call_count == 1
        assert json.loads(data.read_text(encoding="utf-8"))["tasks"][0]["title"] == "更新後"

        (loop / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
        clock[0] = 0
        def fake_api(method, params, token):
            assert (method, params["timeout"], token) == ("getUpdates", 0, "test-token")
            return {"ok": True, "result": [{"update_id": 1, "message": {
                "chat": {"id": 42, "type": "private"}, "from": {"id": 42}, "text": "T-1 返事"}}]}
        with patch.dict(os.environ, {"HARNESS_TESTING": "1", "HARNESS_LOOP_DIR": str(loop)}), \
                patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(dashboard_watch.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                patch.object(telegram, "_api", side_effect=fake_api):
            dashboard_watch.watch(loop, interval=1, hours=2 / 3600, digest_minutes=0)
        assert [r["text"] for r in inbox.all_rows(loop)] == ["T-1 返事"]
        assert json.loads(data.read_text(encoding="utf-8"))["inbox"][0]["text"] == "T-1 返事"

        clock[0] = 0
        output = io.StringIO()
        with patch.dict(os.environ, {"HARNESS_TESTING": "1"}), redirect_stdout(output), \
                patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(dashboard_watch.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                patch.object(telegram, "poll", side_effect=RuntimeError("失敗\n詳細")) as polling:
            dashboard_watch.watch(loop, interval=1, hours=2 / 3600, digest_minutes=0)
            assert polling.call_count == 2
        assert output.getvalue().splitlines() == ["Telegram 受信失敗: 失敗"] * 2
        # 同じ要点は重ねず、変化があっても 10 分は待つ。
        clock[0] = 0
        (loop / "events.jsonl").write_text('', encoding="utf-8")
        task.write_text("# 通知対象\n", encoding="utf-8")
        sent = []
        def tick(seconds):
            clock[0] += seconds
            if clock[0] == 60:
                (loop / "events.jsonl").write_text('{"task":"T-1","member":"a","event":"end","exit":0}\n', encoding="utf-8")
            if clock[0] == 120:
                task.write_text("# 通知対象の改題\n", encoding="utf-8")
            if clock[0] == 600:
                (loop / "events.jsonl").write_text('{"task":"T-1","member":"a","event":"end","exit":1}\n', encoding="utf-8")
        with patch.dict(os.environ, {"HARNESS_TESTING": "1"}), \
                patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(dashboard_watch.time, "sleep", side_effect=tick), \
                patch.object(telegram, "poll", return_value=[]), \
                patch.object(telegram, "send", side_effect=lambda text, **kw: sent.append((clock[0], text))):
            dashboard_watch.watch(loop, interval=60, hours=720 / 3600)
        assert len(sent) == 2, sent
        assert sent[0][0] == 0 and "未回答" in sent[0][1], sent
        assert sent[1][0] == 600 and "失敗" in sent[1][1], sent

        signals = [{"text": "/dash", "chat_id": 42}, {"text": "/status", "chat_id": 42}]
        clock[0] = 0
        (loop / "dashboard/index.html").write_text("<html>latest</html>", encoding="utf-8")
        with patch.dict(os.environ, {"HARNESS_TESTING": "1", "HARNESS_CONFIG_HOME": str(loop / "config")}), \
                patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(dashboard_watch.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                patch.object(telegram, "poll", return_value=signals), \
                patch.object(telegram, "send_document") as document, patch.object(telegram, "send") as message:
            dashboard_watch.watch(loop, interval=1, hours=1 / 3600, digest_minutes=0)
        document.assert_called_once_with(loop / "dashboard/index.html", f"[{loop.parent.name}] ダッシュボード", chat_id=42)
        assert message.call_count == 1 and message.call_args.kwargs == {"chat_id": 42}
        server = dashboard_watch.start_server(loop, "127.0.0.1:0")
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            assert urllib.request.urlopen(base + "/").read() == b"<html>latest</html>"
            assert json.loads(urllib.request.urlopen(base + "/data.json").read())["tasks"][0]["id"] == "T-1"
            for path in ("/../", "/other", "/%2e%2e/"):
                try:
                    urllib.request.urlopen(base + path)
                    raise AssertionError(path)
                except urllib.error.HTTPError as error:
                    assert error.code == 404, (path, error.code)
        finally:
            server.shutdown()
            server.server_close()
        try:
            dashboard_watch.start_server(loop, "0.0.0.0:1")
            raise AssertionError("public bind accepted")
        except ValueError as error:
            assert "私設の網の住所か 127.0.0.1" in str(error)
        with patch.object(sys, "argv", ["dashboard_watch.py", "--serve", "0.0.0.0:1", "--once"]), redirect_stdout(output := io.StringIO()):
            assert dashboard_watch.main() == 1
        assert output.getvalue().splitlines() == ["私設の網の住所か 127.0.0.1 を指定してください"]
    print("ok  test_dashboard_watch: 更新・要点の間隔・合図・HTTP 200/404・公開 bind 拒否")


if __name__ == "__main__":
    main()
