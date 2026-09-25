#!/usr/bin/env python3
"""hub の振り分けと送信箱を、偽の API と使い捨ての 2 作業場で確かめる。"""
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
import dashboard_watch
import hub
import inbox
from bridge import telegram


def message(update_id, text, chat=42, sender=None):
    return {"update_id": update_id, "message": {"chat": {"id": chat, "type": "private"},
                                               "from": {"id": sender or chat}, "text": text}}


def test_topics(tmp):
    config_home = tmp / "config"
    config_home.mkdir()
    workspaces = {name: {"path": str(tmp / name)} for name in ("a", "b")}
    for name in workspaces:
        (tmp / name / ".loop").mkdir(parents=True)
    (config_home / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
    (config_home / "hub.json").write_text(json.dumps({"workspaces": workspaces, "current": "a", "chat_id": -100}), encoding="utf-8")
    updates = [
        {"update_id": 1, "message": {"chat": {"id": -100, "type": "supergroup"}, "from": {"id": 42}, "text": "B の話", "message_thread_id": 102}},
        {"update_id": 2, "message": {"chat": {"id": -100, "type": "supergroup"}, "from": {"id": 42}, "text": "General の話"}},
        {"update_id": 3, "message": {"chat": {"id": -100, "type": "supergroup"}, "from": {"id": 42}, "text": "/dash", "message_thread_id": 102}},
        {"update_id": 4, "message": {"chat": {"id": -100, "type": "supergroup"}, "from": {"id": 99}, "text": "許可外", "message_thread_id": 102}},
    ]
    calls = []

    def fake_api(method, params, token):
        calls.append((method, dict(params)))
        if method == "createForumTopic":
            return {"ok": True, "result": {"message_thread_id": {"a": 101, "b": 102, "c": 103}[params["name"]]}}
        if method == "getUpdates":
            return {"ok": True, "result": updates}
        return {"ok": True, "result": {}}

    env = {"HARNESS_TESTING": "1", "HARNESS_CONFIG_HOME": str(config_home), "HARNESS_LOOP_DIR": str(tmp / "hub-loop")}
    with patch.dict(os.environ, env), patch.object(telegram, "_api", side_effect=fake_api):
        assert hub.main(["--once"]) == 0
        assert hub.load()["topics"] == {"a": 101, "b": 102}
        assert [r["text"] for r in inbox.all_rows(tmp / "b/.loop")] == ["B の話"]
        assert [r["text"] for r in inbox.all_rows(tmp / "a/.loop")] == ["General の話"]
        assert inbox.outbox_pending(tmp / "b/.loop", kinds=("dash",))[0]["thread_id"] == 102
        inbox.outbox_append({"kind": "text", "text": "[b] 返事"}, tmp / "b/.loop")
        inbox.outbox_append({"kind": "text", "text": "[b] 細工先", "thread_id": 777}, tmp / "b/.loop")
        (tmp / "a/.loop/dashboard").mkdir()
        inbox.outbox_append({"kind": "document", "path": str(tmp / "a/.loop/dashboard/index.html")}, tmp / "a/.loop")
        (tmp / "a/.loop/dashboard/index.html").write_text("<html></html>", encoding="utf-8")
        inbox.outbox_append({"kind": "text", "text": "画面への返事", "chat_id": "web"}, tmp / "b/.loop")
        assert hub.flush_outbox() == 3
        assert not any("画面への返事" in str(params) for _, params in calls), calls   # グループがあっても画面の返事は送らない
        assert ("sendMessage", {"chat_id": -100, "text": "返事", "message_thread_id": 102}) in calls
        assert ("sendMessage", {"chat_id": -100, "text": "細工先", "message_thread_id": 102}) in calls   # 行の thread_id は信じない
        assert not any(params.get("message_thread_id") == 777 for _, params in calls), calls
        assert any(method == "sendDocument" and params["chat_id"] == -100 and params["message_thread_id"] == 101
                   for method, params in calls)
        assert hub.main(["--once"]) == 0
        assert len([method for method, _ in calls if method == "createForumTopic"]) == 2
        (tmp / "c/.loop").mkdir(parents=True)
        config = hub.load()
        config["workspaces"]["c"] = {"path": str(tmp / "c")}
        hub.save(config)
        assert hub.main(["--once"]) == 0
        assert hub.load()["topics"]["c"] == 103
        with redirect_stdout(output := io.StringIO()):
            assert hub.main(["whoami"]) == 0
        assert "chat_id=-100  type=supergroup" in output.getvalue()
        assert "message_thread_id=102" in output.getvalue()


def test_once_isolates_bridges(tmp):
    """--once: 1 つの橋の例外で、後の橋の受信と送信箱が止まらない。"""
    (tmp / "hub.json").write_text(json.dumps({"workspaces": {"a": {"path": str(tmp / "a")}}, "current": "a",
                                              "transports": {"discord": {}, "slack": {}}}), encoding="utf-8")
    polled = []

    def fake_poll(name, *, timeout=25):
        polled.append(name)
        if name == "discord":
            raise RuntimeError("discord 落ちた")
        return 0

    with patch.dict(os.environ, {"HARNESS_TESTING": "1", "HARNESS_CONFIG_HOME": str(tmp)}), \
            patch.object(hub, "setup_channels"), patch.object(hub, "poll_transport", side_effect=fake_poll), \
            patch.object(hub, "flush_outbox", side_effect=lambda: polled.append("flush")), redirect_stdout(io.StringIO()):
        hub.run(hours=1, once=True)
    assert polled == ["discord", "slack", "flush"], polled


def test_outbox_ignores_row_destination(tmp):
    """送信箱の行の thread_id / target / transport で、hub.json の外へ送れない。"""
    for name in ("alpha", "beta"):
        (tmp / name / ".loop").mkdir(parents=True)
    (tmp / "hub.json").write_text(json.dumps({
        "workspaces": {name: {"path": str(tmp / name)} for name in ("alpha", "beta")}, "chat_id": -100,
        "topics": {"alpha": 101, "beta": 102},
        "transports": {"telegram": {}, "discord": {"channels": {"alpha": "555", "beta": "666"}}}}), encoding="utf-8")
    loop = tmp / "alpha/.loop"
    inbox.outbox_append({"kind": "text", "text": "話題", "chat_id": 99999, "thread_id": 102}, loop)
    inbox.outbox_append({"kind": "text", "text": "橋", "transport": "discord", "target": "999attack", "thread": "t"}, loop)
    inbox.outbox_append({"kind": "text", "text": "無い橋", "transport": "slack", "target": "999attack"}, loop)
    sent = []

    class Fake:
        def __init__(self, name):
            self.name = name

        def send(self, text, **destination):
            sent.append((self.name, text, destination))

    with patch.dict(os.environ, {"HARNESS_TESTING": "1", "HARNESS_CONFIG_HOME": str(tmp)}), \
            patch.dict(hub.TRANSPORTS, {"telegram": Fake("telegram"), "discord": Fake("discord")}):
        assert hub.flush_outbox() == 3
    assert sent == [("telegram", "話題", {"chat_id": -100, "thread_id": 101}),
                    ("discord", "[alpha] 橋", {"target": "555", "thread": None}),
                    ("telegram", "無い橋", {"chat_id": -100, "thread_id": 101})], sent
    logged = [json.loads(line) for line in (tmp / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert [row["action"] for row in logged].count("ignored-destination") == 3, logged


def main():
    with tempfile.TemporaryDirectory() as tmp:
        test_topics(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        config, a, b, c = tmp / "config", tmp / "a", tmp / "b", tmp / "c"
        for p in (config, a / ".loop", b / ".loop", c / ".loop"):
            p.mkdir(parents=True)
        env = {"HARNESS_TESTING": "1", "HARNESS_CONFIG_HOME": str(config), "HARNESS_LOOP_DIR": str(tmp / "hub-loop"),
               "HARNESS_JUDGMENT_HOME": str(tmp / "judgment")}
        with patch.dict(os.environ, env):
            with redirect_stderr(err := io.StringIO()):
                assert hub.main(["--once"]) == 1
            assert "hub.json が無い" in err.getvalue()

            (config / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_IDS=42\n", encoding="utf-8")
            (config / "hub.json").write_text(json.dumps({"workspaces": {"a": {"path": str(a)}, "b": {"path": str(b)}},
                                                         "current": "a"}), encoding="utf-8")
            calls, updates = [], [[
                message(1, "/ws"), message(2, "/ws b"), message(3, "こんにちは"), message(4, "@a 急ぎ"),
                message(5, "侵入", chat=99), message(6, "/dash"), message(7, "@a /status"),
            ]]

            def fake_api(method, params, token):
                assert token == "test-token"
                calls.append((method, dict(params)))
                if method == "getUpdates":
                    return {"ok": True, "result": updates.pop(0) if updates else []}
                return {"ok": True, "result": {}}

            with patch.object(telegram, "_api", side_effect=fake_api):
                assert hub.poll_once(timeout=0) == 6
                replies = [p["text"] for m, p in calls if m == "sendMessage"]
                assert replies == ["作業場:\n▶ a\n・b", "今の相手: b"], replies
                assert hub.load()["current"] == "b"
                assert [r["text"] for r in inbox.all_rows(b / ".loop")] == ["こんにちは"]
                assert [r["text"] for r in inbox.all_rows(a / ".loop")] == ["急ぎ"]
                assert "侵入" not in (config / "hub.log").read_text(encoding="utf-8")
                assert '"action": "dropped"' in (config / "hub.log").read_text(encoding="utf-8")
                assert [r["kind"] for r in inbox.outbox_pending(b / ".loop", kinds=("dash", "status"))] == ["dash"]
                assert [r["kind"] for r in inbox.outbox_pending(a / ".loop", kinds=("dash", "status"))] == ["status"]
                calls.clear()
                hub.poll_once(timeout=0)
                assert calls[0][1]["offset"] == 8, calls

            # 見張りは hub があるとき Telegram を呼ばず、送信箱に書く（telegram.env が有っても）。
            (a / ".loop/telegram.env").write_text("TELEGRAM_BOT_TOKEN=x\nTELEGRAM_CHAT_IDS=1\n", encoding="utf-8")
            inbox.outbox_append({"kind": "dash", "chat_id": 42}, a / ".loop")
            clock = [0.0]
            with patch.object(telegram, "_api", side_effect=AssertionError("見張りが Telegram を呼んだ")), \
                    patch.object(dashboard_watch.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(dashboard_watch.time, "sleep", side_effect=lambda s: clock.__setitem__(0, clock[0] + s)):
                assert hub.attached(a / ".loop") == "a" and hub.attached(tmp / "hub-loop") is None
                dashboard_watch.watch(a / ".loop", interval=1, hours=1 / 3600)
            pending = inbox.outbox_pending(a / ".loop")
            assert [r["kind"] for r in pending] == ["text", "text", "document"], pending
            assert inbox.outbox_pending(a / ".loop", kinds=("dash", "status")) == []

            calls.clear()
            with patch.object(telegram, "_api", side_effect=fake_api):
                assert hub.flush_outbox() == 3
                assert hub.flush_outbox() == 0
            texts = [(m, p.get("text") or p.get("caption"), p["chat_id"]) for m, p in calls]
            assert texts[0][0] == "sendMessage" and texts[0][1].startswith("[a] 依頼:") and texts[0][2] == 42, texts
            assert texts[1][1].startswith("[a] 依頼:") and texts[1][2] == 42, texts
            assert texts[2] == ("sendDocument", "[a] ダッシュボード", 42), texts
            assert inbox.outbox_pending(a / ".loop") == []
            assert (a / ".loop/outbox.jsonl").read_text(encoding="utf-8").count('"type": "sent"') == 5

            # 偽の指示役で、起動・同時実行の制限・終了通知を実際の子プロセスで確かめる。
            fake = tmp / "fake_leader.py"
            fake.write_text("""import json, os, pathlib, sys, time
root = pathlib.Path.cwd()
prompt = sys.stdin.read() if '--stdin' in sys.argv else sys.argv[-1]
(root / 'seen.json').write_text(json.dumps({'cwd': str(root), 'role': os.getenv('HARNESS_ROLE'),
    'unattended': os.getenv('HARNESS_UNATTENDED'), 'prompt': prompt}, ensure_ascii=False))
while (root / 'hold').exists():
    time.sleep(0.02)
if '--fail' in sys.argv:
    print('one\\ntwo\\nthree\\nfour\\nfive\\nsix', file=sys.stderr)
    sys.exit(3)
print(json.dumps({'result': '指示役の要点'}))
""", encoding="utf-8")
            clis = tmp / "clis.json"
            clis.write_text(json.dumps({"clis": {
                "fake-stdin": {"leader": [sys.executable, str(fake), "--stdin", "{prompt}"], "prompt": "stdin"},
                "fake-argv": {"leader": [sys.executable, str(fake), "{prompt}"]},
                "fake-fail": {"leader": [sys.executable, str(fake), "--fail", "{prompt}"]},
            }}), encoding="utf-8")
            cfg = hub.load()
            cfg["workspaces"]["a"]["leader"] = {"cli": "fake-stdin", "model": ""}
            cfg["workspaces"]["b"]["leader"] = {"cli": "fake-argv", "model": ""}
            cfg["workspaces"]["c"] = {"path": str(c), "leader": {"cli": "fake-fail", "model": ""}}
            hub.save(cfg)
            (a / "hold").touch()
            payload = f"調べる; $(touch {tmp / 'shell-ran'})"
            with patch.dict(os.environ, {"HARNESS_CLIS": str(clis), "HARNESS_ROLE": "worker", "HARNESS_ATTENDED": "1"}), \
                    patch.object(telegram, "_api", side_effect=fake_api):
                action, _ = hub.route(cfg, "/run a " + payload, chat_id=42)
                assert action == "run"
                for _ in range(100):
                    if (a / "seen.json").exists():
                        break
                    time.sleep(0.02)
                seen = json.loads((a / "seen.json").read_text(encoding="utf-8"))
                assert seen["cwd"] == str(a) and seen["role"] is None and seen["unattended"] == "1", seen
                assert seen["prompt"].endswith("依頼: " + payload), seen
                assert not (tmp / "shell-ran").exists()
                assert hub.route(cfg, "/run a 二本目", chat_id=42)[0] == "running"
                (a / "hold").unlink()
                for _ in range(100):
                    if inbox.outbox_pending(a / ".loop"):
                        break
                    time.sleep(0.02)
                assert any("[a] 指示役の要点" in r["text"] for r in inbox.outbox_pending(a / ".loop"))
                calls.clear()
                assert hub.flush_outbox() == 1
                assert any(m == "sendMessage" and p["text"] == "[a] 指示役の要点" for m, p in calls)
                assert "二本目" not in (a / "seen.json").read_text(encoding="utf-8")
                assert any(r.get("action") == "run" and r.get("chat_id") == 42 and r.get("text") == payload[:80]
                           for r in (json.loads(line) for line in (config / "hub.log").read_text(encoding="utf-8").splitlines()))

                updates.append([message(8, "/run b 許可外", chat=99)])
                assert hub.poll_once(timeout=0) == 0
                assert not (b / "seen.json").exists()
                assert '"action": "dropped"' in (config / "hub.log").read_text(encoding="utf-8")

                (b / "hold").touch()
                assert hub.route(cfg, "/run b argv そのまま; $(touch " + str(tmp / "shell-ran") + ")", chat_id=42)[0] == "run"
                for _ in range(100):
                    if (b / "seen.json").exists():
                        break
                    time.sleep(0.02)
                assert "argv そのまま; $(touch " in json.loads((b / "seen.json").read_text(encoding="utf-8"))["prompt"]
                assert not (tmp / "shell-ran").exists()
                assert hub.route(cfg, "/stop b", chat_id=42)[0] == "stop"
                for _ in range(100):
                    if any("落ちた（exit" in r["text"] for r in inbox.outbox_pending(b / ".loop")):
                        break
                    time.sleep(0.02)
                assert any("落ちた（exit" in r["text"] for r in inbox.outbox_pending(b / ".loop"))

                assert hub.route(cfg, "/run c 失敗例", chat_id=42)[0] == "run"
                for _ in range(100):
                    if inbox.outbox_pending(c / ".loop"):
                        break
                    time.sleep(0.02)
                failure = inbox.outbox_pending(c / ".loop")[0]["text"]
                assert failure == "[c] 落ちた（exit 3）\ntwo\nthree\nfour\nfive\nsix", failure

                # /run の第 1 語が無い名前なら、今の相手（b）への依頼。返事に作業場名が出る。
                for _ in range(100):
                    if not hub._running("b"):
                        break
                    time.sleep(0.02)
                (b / "seen.json").unlink()
                (b / "hold").unlink()
                calls.clear()
                assert hub.route(cfg, "/run ghost 文", chat_id=42, update_id=500) == ("run", "b")
                assert ("sendMessage", {"chat_id": 42, "text": "[b] 起動しました（作業場 b）"}) in calls, calls
                for _ in range(100):
                    if (b / "seen.json").exists() and not hub._running("b"):
                        break
                    time.sleep(0.02)
                assert json.loads((b / "seen.json").read_text(encoding="utf-8"))["prompt"].endswith("依頼: ghost 文")
                # 同じ update_id の再配送（offset を戻す）では二度起動しない。別の update_id なら起動する。
                (b / "seen.json").unlink()
                (config / "hub.offset").write_text("500", encoding="utf-8")
                updates.append([message(500, "/run ghost 文")])
                hub.poll_once(timeout=0)
                time.sleep(0.3)
                assert not (b / "seen.json").exists() and not hub._running("b")
                assert hub.route(cfg, "/run ghost 文", chat_id=42, update_id=501)[0] == "run"
                for _ in range(100):
                    if (b / "seen.json").exists() and not hub._running("b"):
                        break
                    time.sleep(0.02)
                assert (b / "seen.json").exists()

            # 転送された文は、許可した人からでも捨てて dropped だけ記録する。
            before = len(inbox.all_rows(b / ".loop"))
            # 欄は forward_ で始まる物なら何でも（forward_date だけでも）、is_automatic_forward も同じ。/run も起動しない。
            marks = [{"forward_from": {"id": 7}},
                     {"forward_origin": {"type": "hidden_user", "sender_user_name": "x", "date": 0}},
                     {"forward_date": 1}, {"forward_sender_name": "x", "forward_date": 1},
                     {"forward_from_chat": {"id": -5}, "forward_date": 1}, {"is_automatic_forward": True}]
            forwarded = [message(600 + i, f"/run b 転送の本文{i}") for i in range(len(marks))]
            for update, mark in zip(forwarded, marks):
                update["message"].update(mark)
            updates.append(forwarded + [message(620, "転送でない本文")])
            with patch.dict(os.environ, {"HARNESS_CLIS": str(clis)}), patch.object(telegram, "_api", side_effect=fake_api):
                assert hub.poll_once(timeout=0) == 1
            time.sleep(0.3)
            assert [r["text"] for r in inbox.all_rows(b / ".loop")[before:]] == ["転送でない本文"]
            assert not (b / "seen.json").exists() or "転送の本文" not in (b / "seen.json").read_text(encoding="utf-8")
            hub_log = (config / "hub.log").read_text(encoding="utf-8")
            assert "転送の本文" not in hub_log and hub_log.count('"action": "dropped"') >= 8, hub_log

            # 送信箱の文書は、その作業場の .loop/dashboard/ の下だけ送る（外や .. 抜けは送らず失敗の印）。
            secret = tmp / "secret.env"
            secret.write_text("TOKEN=x", encoding="utf-8")
            (a / ".loop/dashboard").mkdir(exist_ok=True)
            with patch.object(telegram, "_api", side_effect=fake_api):
                hub.flush_outbox()   # 前の段の返事を先に送り切る
            outside = [inbox.outbox_append({"kind": "document", "path": str(secret)}, a / ".loop"),
                       inbox.outbox_append({"kind": "document", "path": str(a / ".loop/dashboard/../../../secret.env")}, a / ".loop")]
            calls.clear()
            with patch.object(telegram, "_api", side_effect=fake_api):
                assert hub.flush_outbox() == 0
            assert not any(m == "sendDocument" for m, _ in calls), calls
            marks = [json.loads(line) for line in (a / ".loop/outbox.jsonl").read_text(encoding="utf-8").splitlines()]
            assert all(any(r.get("type") == "sent" and r["id"] == row["id"] and r.get("error") == "ValueError" for r in marks)
                       for row in outside), marks
            # dashboard の dir 自体が外への symlink なら、その中の文書も送らない。
            outer = tmp / "outer"
            outer.mkdir()
            (outer / "index.html").write_text("TOK-DIR-SYMLINK", encoding="utf-8")
            (c / ".loop/dashboard").symlink_to(outer, target_is_directory=True)
            linked = inbox.outbox_append({"kind": "document", "path": str(c / ".loop/dashboard/index.html")}, c / ".loop")
            calls.clear()
            with patch.object(telegram, "_api", side_effect=fake_api):
                hub.flush_outbox()
            assert not any(m == "sendDocument" for m, _ in calls), calls
            assert '"error": "ValueError"' in next(line for line in (c / ".loop/outbox.jsonl").read_text(encoding="utf-8").splitlines()
                                                   if linked["id"] in line and '"type": "sent"' in line)
            # 本物の dir の中の文書は送る（通る形）。
            (a / ".loop/dashboard/index.html").write_text("<html></html>", encoding="utf-8")
            inbox.outbox_append({"kind": "document", "path": str(a / ".loop/dashboard/index.html")}, a / ".loop")
            calls.clear()
            with patch.object(telegram, "_api", side_effect=fake_api):
                assert hub.flush_outbox() == 1
            assert [m for m, _ in calls] == ["sendDocument"], calls

            # hub 画面: 一覧と会話を配り、同じ host からの返事だけを受信箱に入れる。
            for unspecified in ("0.0.0.0:0", "::ffff:0.0.0.0:0", ":::0"):
                try:
                    hub.start_server(unspecified)
                    raise AssertionError(f"{unspecified} を受けた")
                except ValueError:
                    pass
            inbox.append("<b>人の文</b>", loop=b / ".loop", chat_id=42)
            server = hub.start_server("127.0.0.1:0")
            base = f"http://127.0.0.1:{server.server_port}"

            with urllib.request.urlopen(base + "/ws/b", timeout=5) as response:
                csrf = re.search(r'name="csrf" value="([^"]+)"', response.read().decode("utf-8")).group(1)

            def post(path, text, origin=base, token=None, host=None):
                data = urllib.parse.urlencode({"text": text, "csrf": csrf if token is None else token}).encode("utf-8")
                headers = {"Origin": origin} if origin else {}
                if host:
                    headers["Host"] = host
                request = urllib.request.Request(base + path, data=data, headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        return response.status
                except urllib.error.HTTPError as error:
                    return error.code

            try:
                with urllib.request.urlopen(base + "/", timeout=5) as response:
                    page = response.read().decode("utf-8")
                    assert response.status == 200 and 'href="/ws/a"' in page and 'href="/ws/c"' in page, page
                with urllib.request.urlopen(base + "/ws/b", timeout=5) as response:
                    page = response.read().decode("utf-8")
                    assert response.status == 200 and "&lt;b&gt;人の文&lt;/b&gt;" in page and "<b>人の文" not in page, page
                    assert 'class="m a"' in page and 'method="post"' in page and 'http-equiv="refresh"' in page, page
                assert post("/ws/b/reply", "画面から; $(touch " + str(tmp / "shell-ran") + ")") == 200
                row = inbox.all_rows(b / ".loop")[-1]
                assert row["text"].startswith("画面から; ") and row["chat_id"] == "web", row
                assert not (tmp / "shell-ran").exists()
                assert post("/ws/b/reply", "/status") == 200
                assert [r["chat_id"] for r in inbox.outbox_pending(b / ".loop", kinds=("status",))] == ["web"]
                assert post("/ws/b/reply", "/stop") == 200
                assert any(r.get("text") == "[b] 実行中の指示役はありません" for r in inbox.outbox_pending(b / ".loop", kinds=("note",)))
                before = len(inbox.all_rows(b / ".loop"))
                assert post("/ws/b/reply", "よそから", origin="http://evil.example") == 403
                assert post("/ws/b/reply", "Origin 無し", origin=None) == 403
                # 比べる相手は要求の Host ではなく --serve の host:port。印（csrf）が無い・違うも 403。
                assert post("/ws/b/reply", "Host 合わせ", origin="http://evil.example", host="evil.example") == 403
                assert post("/ws/b/reply", "印なし", token="") == 403
                assert post("/ws/b/reply", "印違い", token=csrf + "x") == 403
                assert post("/ws/b/reply", "あ" * 4001) == 413
                assert post("/ws/zzz/reply", "無い作業場") == 404
                assert len(inbox.all_rows(b / ".loop")) == before
                # 画面から頼んだ返事は Telegram に送らず、印だけ付ける。
                inbox.outbox_append({"kind": "text", "text": "画面への返事", "chat_id": "web"}, b / ".loop")
                calls.clear()
                with patch.object(telegram, "_api", side_effect=fake_api):
                    hub.flush_outbox()
                assert not any("画面への返事" in str(p) for _, p in calls), calls
                assert not any(r["text"] == "画面への返事" for r in inbox.outbox_pending(b / ".loop"))
            finally:
                server.shutdown()
                server.server_close()
    with tempfile.TemporaryDirectory() as tmp:
        test_once_isolates_bridges(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_outbox_ignores_row_destination(Path(tmp))
    print("ok  test_hub: /ws 切り替え・@名前・許可外を捨てる・送信箱の送信と印・hub ありの見張りは Telegram を呼ばない・hub 画面の GET/POST/403/413")


if __name__ == "__main__":
    main()
