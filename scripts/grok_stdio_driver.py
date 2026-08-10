#!/usr/bin/env python3
"""Run a complete Grok ACP turn over ``grok agent stdio``."""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import selectors
import subprocess
import sys
import tempfile
import time
import tomllib
from typing import Any, BinaryIO, NamedTuple, TextIO


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agent-shared"))
from hooks_core import DELEGATED_SHELL_ENV, evaluate_tool_use  # noqa: E402


class DriverError(RuntimeError):
    pass


# 部分文字列マッチだと Grok 0.2.118 の `kind` に含まれる語（例: agent）が
# シェル実行まで forbidden に巻き込むため、完全一致の明示リストで判定する。
FORBIDDEN_TOOL_NAMES = frozenset(
    {
        "agent",
        "subagent",
        "task",
        "spawn_agent",
        "web",
        "web_search",
        "websearch",
        "search_web",
        "web_fetch",
        "webfetch",
        "fetch",
        "browser",
        "browse",
        "open_url",
        "memory",
        "read_memory",
        "write_memory",
        "create_memory",
        "update_memory",
    }
)
FORBIDDEN_TOOL_KINDS = frozenset({"fetch", "memory"})
READ_TOOL_KINDS = frozenset({"read", "search"})
READ_TOOL_NAMES = frozenset(
    {"read", "read_file", "view", "view_file", "grep", "search", "glob", "list_dir"}
)
GREP_TOOL_NAMES = frozenset({"grep", "search", "glob"})
WRITE_TOOL_KINDS = frozenset({"edit", "write"})
WRITE_TOOL_NAMES = frozenset(
    {"edit", "edit_file", "write", "write_file", "create_file", "search_replace", "replace", "apply_patch"}
)
SHELL_TOOL_KINDS = frozenset({"execute", "shell", "bash"})
SHELL_TOOL_NAMES = frozenset(
    {
        "bash",
        "shell",
        "execute",
        "run",
        "run_command",
        "run_shell_command",
        "run_terminal_command",
        "run_terminal_cmd",
        "terminal",
    }
)


class JsonLinesPeer:
    def __init__(self, reader: BinaryIO, writer: BinaryIO, timeout: float) -> None:
        self.reader = reader
        self.writer = writer
        self.deadline = time.monotonic() + timeout
        self.selector = selectors.DefaultSelector()
        self.selector.register(reader, selectors.EVENT_READ)

    def send(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        self.writer.write((payload + "\n").encode())
        self.writer.flush()

    def receive(self) -> dict[str, Any]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0 or not self.selector.select(remaining):
            raise DriverError("timed out waiting for grok agent stdio")
        line = self.reader.readline()
        if not line:
            raise DriverError("grok agent stdio closed stdout unexpectedly")
        try:
            message = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DriverError(f"invalid JSON-RPC message: {exc}") from exc
        if not isinstance(message, dict):
            raise DriverError("JSON-RPC message must be an object")
        return message


class ToolDetails(NamedTuple):
    tool_name: str
    category: str
    tool_input: dict[str, Any]
    kind: str
    reported_name: str


def _tool_details(tool_call: dict[str, Any]) -> ToolDetails:
    if "rawInput" in tool_call:
        raw_input = tool_call["rawInput"]
    elif "input" in tool_call:
        raw_input = tool_call["input"]
    else:
        raw_input = {}
    kind = str(tool_call.get("kind") or "").lower()
    reported_name = str(tool_call.get("name") or tool_call.get("title") or kind or "unknown")
    lowered = reported_name.lower()
    if not isinstance(raw_input, dict):
        return ToolDetails(reported_name, "malformed", {}, kind, reported_name)

    def details(tool_name: str, category: str) -> ToolDetails:
        return ToolDetails(tool_name, category, raw_input, kind, reported_name)

    # 名前が明示的に禁止対象のときだけ先に落とす。ここは完全一致なので、
    # 後続の許可カテゴリ判定を巻き込まない。
    if lowered in FORBIDDEN_TOOL_NAMES:
        return details(reported_name, "forbidden")
    # 許可したい具体カテゴリを先に判定し、包括的な拒否は最後に置く。
    # 逆順にすると 1 つの誤判定で以降の分類が全部死ぬ（2026-08-04 の Execute 誤拒否）。
    if kind in READ_TOOL_KINDS or lowered in READ_TOOL_NAMES:
        hook_name = "grep" if kind == "search" or lowered in GREP_TOOL_NAMES else "read_file"
        return details(hook_name, "file")
    if kind in WRITE_TOOL_KINDS or lowered in WRITE_TOOL_NAMES:
        return details("write_file", "file")
    if kind in SHELL_TOOL_KINDS or lowered in SHELL_TOOL_NAMES:
        return details("run_terminal_command", "shell")
    if kind in FORBIDDEN_TOOL_KINDS:
        return details(reported_name, "forbidden")
    return details(reported_name, "unknown")


class Decision(NamedTuple):
    allowed: bool
    tool_name: str
    reason: str
    category: str
    kind: str
    input_keys: str
    reported_name: str


def _permission_decision(tool_call: dict[str, Any], allow_bash: bool) -> Decision:
    tool_name, category, tool_input, kind, reported_name = _tool_details(tool_call)
    # 判定の入力も1行で残す。値は認証情報を含み得るので key 名だけにする。
    context = {
        "tool_name": tool_name,
        "category": category,
        "kind": kind or "-",
        "input_keys": ",".join(sorted(tool_input)) or "-",
        "reported_name": reported_name,
    }
    hook_reason = evaluate_tool_use(tool_name, tool_input)
    if hook_reason:
        return Decision(False, reason=hook_reason, **context)
    if category == "file":
        return Decision(True, reason="hooks_core passed file operation", **context)
    if category == "shell":
        if allow_bash:
            return Decision(True, reason="hooks_core passed and --allow-bash is set", **context)
        return Decision(False, reason="shell tools require --allow-bash", **context)
    if category == "forbidden":
        return Decision(False, reason="subagent, web search, and memory tools are disabled", **context)
    if category == "malformed":
        return Decision(False, reason="tool input must be an object", **context)
    return Decision(False, reason="unknown tool kind", **context)


def _permission_response(params: dict[str, Any], allow_bash: bool) -> dict[str, Any]:
    tool_call = params.get("toolCall") or {}
    if not isinstance(tool_call, dict):
        tool_call = {}
    decision = _permission_decision(tool_call, allow_bash)
    options = params.get("options") or []
    wanted = (
        ("allow_once", "allow_always") if decision.allowed else ("reject_once", "reject_always")
    )
    selected: dict[str, Any] | None = None
    for kind in wanted:
        selected = next(
            (
                option
                for option in options
                if isinstance(option, dict) and option.get("kind") == kind and option.get("optionId")
            ),
            None,
        )
        if selected:
            break
    verdict = "allow" if decision.allowed else "deny"
    print(
        f"permission tool={decision.reported_name} mapped={decision.tool_name} kind={decision.kind} "
        f"category={decision.category} input_keys={decision.input_keys} "
        f"verdict={verdict} reason={decision.reason}",
        file=sys.stderr,
    )
    if not selected:
        return {"outcome": {"outcome": "cancelled"}}
    return {"outcome": {"outcome": "selected", "optionId": selected["optionId"]}}


def _raise_rpc_error(message: dict[str, Any]) -> None:
    error = message.get("error")
    if error is not None:
        raise DriverError(f"JSON-RPC error: {error}")


def _wait_for_response(
    peer: JsonLinesPeer,
    request_id: int,
    allow_bash: bool,
    assistant_chunks: list[str],
) -> dict[str, Any]:
    while True:
        message = peer.receive()
        if message.get("method") == "session/request_permission" and "id" in message:
            result = _permission_response(message.get("params") or {}, allow_bash)
            peer.send({"jsonrpc": "2.0", "id": message["id"], "result": result})
            continue
        if message.get("method") == "session/update":
            update = (message.get("params") or {}).get("update") or {}
            if update.get("sessionUpdate") == "agent_message_chunk":
                content = update.get("content") or {}
                if content.get("type") == "text":
                    assistant_chunks.append(str(content.get("text") or ""))
            continue
        if message.get("id") == request_id:
            _raise_rpc_error(message)
            result = message.get("result")
            if not isinstance(result, dict):
                raise DriverError(f"request {request_id} returned a non-object result")
            return result
        if "id" in message and "method" in message:
            peer.send(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": "unsupported agent request"},
                }
            )


def _auto_approve_source(cwd: pathlib.Path, home: pathlib.Path | None = None) -> str | None:
    """grokが権限を聞かずに自動承認する設定なら、その出所を返す。

    `permission_mode = "always-approve"`（または`yolo = true`）だとgrokはACP clientへ
    `session/request_permission`を送らないため、driver内のgateは動かない
    （2026-08-05実機確認: `--allow-bash`なしでshellが走った）。
    """
    home = home or pathlib.Path.home()
    for path in (cwd / ".grok" / "config.toml", home / ".grok" / "config.toml"):
        try:
            with path.open("rb") as handle:
                config = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        ui = config.get("ui")
        if not isinstance(ui, dict):
            continue
        if str(ui.get("permission_mode") or "").strip().lower() == "always-approve":
            return f'{path}: [ui] permission_mode = "always-approve"'
        if ui.get("yolo") is True:
            return f"{path}: [ui] yolo = true"
    return None


def _is_trusted_folder(cwd: pathlib.Path, home: pathlib.Path) -> bool:
    # hookはfolder trustが前提。未trustのcheckoutでは自動承認modeの歯止めが何も残らない。
    try:
        with (home / ".grok" / "trusted_folders.toml").open("rb") as handle:
            folders = tomllib.load(handle).get("folders")
    except (OSError, tomllib.TOMLDecodeError):
        return False
    if not isinstance(folders, dict):
        return False
    candidates = {cwd.resolve(), *cwd.resolve().parents}
    for name, entry in folders.items():
        if not isinstance(entry, dict) or entry.get("trusted") is not True:
            continue
        if pathlib.Path(name) in candidates:
            return True
    return False


def _has_project_hook(cwd: pathlib.Path) -> bool:
    hooks_dir = cwd / ".grok" / "hooks"
    if hooks_dir.is_dir() and any(hooks_dir.iterdir()):
        return True
    # grokはtrust後にClaude互換hookも発火する（`docs/HARNESS.md`のCLI別ルール）。
    settings_path = cwd / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return "pre_tool_use_policy" in json.dumps(settings.get("hooks") or {})


def _permission_preflight(cwd: pathlib.Path, home: pathlib.Path | None = None) -> str | None:
    """自動承認modeでも安全に委任できる構成かを確認し、駄目なら理由を返す。

    自動承認自体は禁止しない。承認プロンプトを止めてもhookは発火することを実測したので
    （2026-08-05, grok 0.2.118）、shellの可否はhook層（`AGENT_DELEGATED_SHELL`）が担う。
    ただしhookはfolder trustとproject hookの両方が揃って初めて動くため、片方でも欠けたら
    歯止めが無くなる。その場合だけfail-closedにする。userの設定は書き換えない。
    """
    home = home or pathlib.Path.home()
    auto_approve = _auto_approve_source(cwd, home)
    if not auto_approve:
        return None
    missing = []
    if not _is_trusted_folder(cwd, home):
        missing.append(f"the workspace is not trusted in {home}/.grok/trusted_folders.toml")
    if not _has_project_hook(cwd):
        missing.append(f"no project hook runs the shared policy under {cwd}")
    if not missing:
        return None
    return (
        f"grok auto-approves every tool ({auto_approve}) and the hook layer cannot take over: "
        + "; ".join(missing)
        + ". Trust the workspace and keep the project hook in place, or switch grok back to an "
        "asking permission mode before delegating."
    )


def run_driver(
    prompt: str,
    cwd: pathlib.Path,
    model: str | None,
    timeout: float,
    allow_bash: bool,
    agent_command: list[str] | None = None,
) -> str:
    command = agent_command or ["grok", "agent", "stdio"]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # 自動承認modeではACPのpermissionが来ないので、shellの可否をhook層へも伝える。
    # hookは自動承認でも発火するため、これが実質の最終防衛になる。
    env[DELEGATED_SHELL_ENV] = "allow" if allow_bash else "deny"
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        cwd=cwd,
        env=env,
        bufsize=0,
    )
    assert process.stdin is not None and process.stdout is not None
    peer = JsonLinesPeer(process.stdout, process.stdin, timeout)
    chunks: list[str] = []
    next_id = 1
    try:
        peer.send(
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "initialize",
                "params": {"protocolVersion": 1},
            }
        )
        _wait_for_response(peer, next_id, allow_bash, chunks)
        next_id += 1
        peer.send(
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "session/new",
                "params": {"cwd": str(cwd), "mcpServers": []},
            }
        )
        session = _wait_for_response(peer, next_id, allow_bash, chunks)
        session_id = session.get("sessionId")
        if not session_id:
            raise DriverError("session/new response omitted sessionId")
        if model:
            next_id += 1
            peer.send(
                {
                    "jsonrpc": "2.0",
                    "id": next_id,
                    "method": "session/set_model",
                    "params": {"sessionId": session_id, "modelId": model},
                }
            )
            _wait_for_response(peer, next_id, allow_bash, chunks)
        next_id += 1
        peer.send(
            {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": prompt}],
                },
            }
        )
        _wait_for_response(peer, next_id, allow_bash, chunks)
        return "".join(chunks)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def _fake_send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _fake_receive() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise SystemExit("fake agent: client closed stdin")
    return json.loads(line)


def _fake_reply(request: dict[str, Any], result: dict[str, Any]) -> None:
    _fake_send({"jsonrpc": "2.0", "id": request["id"], "result": result})


def run_fake_agent(hang: bool, expect_allow_bash: bool, expect_model: str | None) -> int:
    initialize = _fake_receive()
    if initialize.get("method") != "initialize" or (initialize.get("params") or {}).get(
        "protocolVersion"
    ) != 1:
        raise SystemExit("fake agent: invalid initialize request")
    _fake_reply(initialize, {"protocolVersion": 1})
    new_session = _fake_receive()
    if new_session.get("method") != "session/new" or new_session.get("params") != {
        "cwd": os.getcwd(),
        "mcpServers": [],
    }:
        raise SystemExit("fake agent: invalid session/new request")
    _fake_reply(new_session, {"sessionId": "selftest-session"})
    if expect_model:
        set_model = _fake_receive()
        if set_model.get("method") != "session/set_model" or set_model.get("params") != {
            "sessionId": "selftest-session",
            "modelId": expect_model,
        }:
            raise SystemExit("fake agent: invalid session/set_model request")
        _fake_reply(set_model, {})
    prompt = _fake_receive()
    prompt_params = prompt.get("params") or {}
    if (
        prompt.get("method") != "session/prompt"
        or prompt_params.get("sessionId") != "selftest-session"
        or prompt_params.get("prompt") != [{"type": "text", "text": "selftest prompt"}]
    ):
        raise SystemExit("fake agent: invalid session/prompt request")
    if hang:
        time.sleep(60)
        return 0

    cases = [
        ({"kind": "edit", "name": "search_replace", "rawInput": {"path": "probe.txt"}}, True),
        ({"kind": "execute", "name": "run_terminal_command", "rawInput": {"command": "git reset --hard HEAD"}}, False),
        (
            {"kind": "execute", "name": "run_terminal_command", "rawInput": {"command": "printf ok"}},
            expect_allow_bash,
        ),
        ({"kind": "read", "name": "read_file", "rawInput": {"path": ".env"}}, False),
        # 2026-08-04 の回帰: kind が未知でも名前でシェル判定へ到達する。
        ({"kind": "", "name": "Execute", "rawInput": {"command": "printf ok"}}, expect_allow_bash),
        # 2026-08-04 の回帰: kind に "agent" 等の語が含まれても forbidden にしない。
        (
            {"kind": "agentic_execute", "name": "run_terminal_command", "rawInput": {"command": "printf ok"}},
            expect_allow_bash,
        ),
        ({"kind": "fetch", "name": "web_search", "rawInput": {"query": "x"}}, False),
        ({"kind": "fetch", "name": "Fetch", "rawInput": {"url": "https://example.invalid"}}, False),
        ({"kind": "other", "name": "subagent", "rawInput": {}}, False),
        ({"kind": "other", "name": "mystery", "rawInput": {}}, False),
        ({"kind": "edit", "name": "search_replace", "rawInput": []}, False),
    ]
    options = [
        {"optionId": "yes", "kind": "allow_once", "name": "Allow"},
        {"optionId": "no", "kind": "reject_once", "name": "Reject"},
    ]
    for index, (tool_call, expected_allow) in enumerate(cases, start=100):
        _fake_send(
            {
                "jsonrpc": "2.0",
                "id": index,
                "method": "session/request_permission",
                "params": {"sessionId": "selftest-session", "toolCall": tool_call, "options": options},
            }
        )
        response = _fake_receive()
        selected = ((response.get("result") or {}).get("outcome") or {}).get("optionId")
        if selected != ("yes" if expected_allow else "no"):
            raise SystemExit(f"fake agent: wrong permission response for {tool_call['name']}")

    for text in ("SELFTEST: ", "PASS"):
        _fake_send(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "selftest-session",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": text},
                    },
                },
            }
        )
    _fake_reply(prompt, {"stopReason": "end_turn"})
    return 0


def run_selftest() -> int:
    script = str(pathlib.Path(__file__).resolve())
    with tempfile.TemporaryDirectory(prefix="grok-stdio-selftest-") as fixture:
        command = [sys.executable, script, "--fake-agent"]
        output = run_driver("selftest prompt", pathlib.Path(fixture), None, 5, False, command)
        if output != "SELFTEST: PASS":
            raise DriverError(f"selftest text mismatch: {output!r}")
        bash_command = [
            sys.executable,
            script,
            "--fake-agent",
            "--fake-expect-allow-bash",
            "--fake-expect-model",
            "selftest-model",
        ]
        output = run_driver(
            "selftest prompt",
            pathlib.Path(fixture),
            "selftest-model",
            5,
            True,
            bash_command,
        )
        if output != "SELFTEST: PASS":
            raise DriverError(f"selftest allow-bash/model text mismatch: {output!r}")
        argv_args = parse_args(["first", "second"])
        if _resolve_prompt(argv_args, sys.stdin) != "first second":
            raise DriverError("selftest argv prompt joining failed")
        stdin_args = parse_args(["--prompt-stdin"])
        if _resolve_prompt(stdin_args, io.StringIO("stdin prompt")) != "stdin prompt":
            raise DriverError("selftest stdin prompt failed")
        # 自動承認modeは、hookが引き継げる構成のときだけ通す。実機ではここでgateが無効化されていた。
        fake_home = pathlib.Path(fixture) / "home"
        workspace = fake_home / "workspace"
        (fake_home / ".grok").mkdir(parents=True)
        workspace.mkdir()
        config_path = fake_home / ".grok" / "config.toml"
        for text, label in (
            ('[ui]\npermission_mode = "always-approve"\n', "always-approve"),
            ("[ui]\nyolo = true\n", "yolo"),
        ):
            config_path.write_text(text, encoding="utf-8")
            if not _auto_approve_source(workspace, home=fake_home):
                raise DriverError(f"selftest failed to detect the {label} auto-approve setting")
            # trustもproject hookも無い状態はfail-closed。
            if not _permission_preflight(workspace, home=fake_home):
                raise DriverError(f"selftest allowed unprotected {label} delegation")
        trusted_path = fake_home / ".grok" / "trusted_folders.toml"
        trusted_path.write_text(
            f'[folders."{workspace}"]\ntrusted = true\n', encoding="utf-8"
        )
        if not _permission_preflight(workspace, home=fake_home):
            raise DriverError("selftest allowed auto-approve delegation without a project hook")
        claude_dir = workspace / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [
                                    {"type": "command", "command": "python3 .claude/hooks/pre_tool_use_policy.py"}
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        if _permission_preflight(workspace, home=fake_home):
            raise DriverError("selftest rejected auto-approve delegation that the hook can guard")
        config_path.write_text('[ui]\npermission_mode = "ask"\n', encoding="utf-8")
        if _auto_approve_source(workspace, home=fake_home):
            raise DriverError("selftest treated an asking permission mode as auto-approve")

        hang_command = [sys.executable, script, "--fake-agent", "--fake-hang"]
        try:
            run_driver("timeout prompt", pathlib.Path(fixture), None, 0.1, False, hang_command)
        except DriverError as exc:
            if "timed out" not in str(exc):
                raise
        else:
            raise DriverError("selftest expected timeout")
    print("grok stdio driver selftest: PASS")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=pathlib.Path)
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--allow-bash", action="store_true")
    parser.add_argument("--prompt-stdin", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--fake-agent", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fake-hang", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fake-expect-allow-bash", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fake-expect-model", help=argparse.SUPPRESS)
    parser.add_argument("prompt", nargs="*")
    return parser.parse_args(argv)


def _resolve_prompt(args: argparse.Namespace, stream: TextIO) -> str:
    if args.prompt_stdin:
        if args.prompt:
            raise DriverError("prompt argv cannot be combined with --prompt-stdin")
        prompt = stream.read()
    else:
        prompt = " ".join(args.prompt)
    if not prompt:
        raise DriverError("prompt must not be empty")
    return prompt


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.fake_agent:
        return run_fake_agent(args.fake_hang, args.fake_expect_allow_bash, args.fake_expect_model)
    try:
        if args.selftest:
            return run_selftest()
        if args.cwd is None or not args.cwd.is_absolute():
            raise DriverError("--cwd must be an absolute path")
        if args.timeout <= 0:
            raise DriverError("--timeout must be greater than zero")
        prompt = _resolve_prompt(args, sys.stdin)
        blocked = _permission_preflight(args.cwd)
        if blocked:
            raise DriverError(blocked)
        auto_approve = _auto_approve_source(args.cwd)
        if auto_approve:
            print(
                f"grok stdio driver: grok auto-approves tools ({auto_approve}); "
                f"shell policy is enforced by the project hook via {DELEGATED_SHELL_ENV}="
                f"{'allow' if args.allow_bash else 'deny'}",
                file=sys.stderr,
            )
        output = run_driver(prompt, args.cwd, args.model, args.timeout, args.allow_bash)
        sys.stdout.write(output)
        if output and not output.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    except (DriverError, OSError) as exc:
        print(f"grok stdio driver: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
