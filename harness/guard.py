#!/usr/bin/env python3
"""守りの判定。全 CLI の hook がこの 1 本を呼ぶ。

止めるのは 5 つ:
  壊す命令 / 秘密のファイル / 管理者になる操作 / 各 CLI 標準の子エージェントの起動 → deny
  外へ出す操作                                   → ask（人がいない担い手では deny）
ほかに 2 つ deny がある（上の 5 つの言い換えではなく、別の理由で止める）:
  読めない命令（引用符や heredoc が閉じていない / 入れ子が深すぎる / xargs のように引数が実行前に決まらない）
  ギア「手なし」（HARNESS_HANDS=none）の担い手が使う、書く道具と shell（例外は報告 1 本だけ）
見るのは「実行する命令」と「触る場所」だけで、書き込む中身は見ない。
中身まで見ると、この一覧を説明する文書すら書けなくなるため。

使い方:  python3 harness/guard.py --dialect claude|cursor|agy|plain  < hook の入力 JSON
標準ライブラリだけで動かす（hook は CLI ごとに違う python 環境から呼ばれるため）。
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAX_DEPTH = 6


@dataclass(frozen=True)
class Decision:
    action: str  # "allow" | "ask" | "deny"
    reason: str = ""


ALLOW = Decision("allow")


def _worst(decisions: list[Decision]) -> Decision:
    for action in ("deny", "ask"):
        for d in decisions:
            if d.action == action:
                return d
    return ALLOW


# ---------------------------------------------------------------- 秘密のファイル

_SECRET_NAME = re.compile(
    r"""^(
        \.env(\..+)? | \.envrc | notify\.env | telegram\.env | discord\.env | slack\.env | worker\.env |
        .+\.(pem|key|p12|pfx|jks|keystore|gpg|asc|kdbx|token) |
        id_(rsa|dsa|ecdsa|ed25519)(_sk)? |
        \.netrc | \.pgpass | \.npmrc | \.pypirc | \.git-credentials |
        credentials(\.json)? | auth\.json | \.credentials\.(json|yaml) | hosts\.yml |
        shadow | gshadow | sudoers
    )$""",
    re.X,
)
_SECRET_NAME_OK = re.compile(r"^\.env\.(example|sample|template|dist)$|\.pub$")
# 置き場そのものが認証情報のためにあるディレクトリ
_SECRET_DIRS = (".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".config/gh", ".codex", ".claude", ".dsh",
                ".local/share/opencode", ".local/share/kilo")
# 上のディレクトリでも、秘密でないと分かっているもの
_SECRET_DIR_OK = re.compile(r"(^|/)(known_hosts|config\.toml|settings(\.local)?\.json|skills/.*|agents/.*|hooks/.*|commands/.*|projects/.*)$")


def secret_path(raw: str, cwd: Path) -> bool:
    if not raw or "\n" in raw:
        return False
    p = _resolve(raw, cwd)
    if p is None:
        return False
    s = p.as_posix()
    name = p.name
    if s in ("/etc/shadow", "/etc/gshadow") or s.startswith("/etc/sudoers") or re.match(r"^/etc/ssh/ssh_host_", s):
        return True
    if re.match(r"^/proc/[^/]+/environ$", s):
        return True
    if _SECRET_NAME_OK.search(name):
        return False
    if name in ("shadow", "gshadow", "sudoers", "hosts.yml", "auth.json", "credentials", "credentials.json"):
        # 一般的な名前は、置き場で判断する（プロジェクト内の auth.json 等を止めないため）
        return _in_secret_dir(s) or s.startswith("/etc/")
    if _SECRET_NAME.match(name):
        return True
    return _in_secret_dir(s)


def _in_secret_dir(s: str) -> bool:
    home = Path.home().as_posix()
    for d in _SECRET_DIRS:
        for base in (f"{home}/{d}/", f"/root/{d}/"):
            if s.startswith(base):
                rest = s[len(base):]
                if d in (".codex", ".claude", ".dsh", ".local/share/opencode", ".local/share/kilo"):
                    # CLI の置き場。止めるのは認証情報のファイルだけ（設定や skills は読めてよい）
                    return rest in ("auth.json", ".credentials.json", ".credentials.yaml") or rest.startswith("storages/")
                return not _SECRET_DIR_OK.search(rest)
    return False


# ---------------------------------------------------------------- 場所

def _resolve(raw: str, cwd: Path) -> Path | None:
    raw = raw.strip()
    if not raw or raw.startswith("-"):
        return None
    home = str(Path.home())
    if raw == "~" or raw.startswith("~/"):
        raw = home + raw[1:]
    raw = re.sub(r"^\$(HOME|\{HOME\})(?=/|$)", home, raw)
    raw = re.sub(r"^%USERPROFILE%", home, raw, flags=re.I)
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", raw)  # Windows の path を WSL の形へ
    if m:
        raw = f"/mnt/{m.group(1).lower()}/{m.group(2)}"
    raw = raw.replace("\\", "/")
    p = PurePosixPath(raw)
    if not p.is_absolute():
        p = PurePosixPath(cwd.as_posix()) / p
    parts: list[str] = []
    for part in p.parts[1:]:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return Path("/" + "/".join(parts))


def _harness_file(raw: str, cwd: Path, name: str) -> bool:
    """`./harness/x`・`harness/./x`・cd の後の `./x` など、綴りによらず harness/<name> を指すか。"""
    p = _resolve(raw, cwd)
    return p is not None and p.parts[-2:] == ("harness", name)


def _perl_inplace(args: list[str]) -> list[str] | None:
    """perl -i の書き先（-i が無ければ None）。-pi・-i.bak・-pie・-pe's///' のような旗のまとまりも読む。"""
    inplace = script = False
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        a = args[i]
        i += 1
        if a == "--":
            break
        k = 1
        while k < len(a):
            c = a[k]
            if c == "i":  # 残りは控えの拡張子
                inplace = True
                break
            if c in "eE":  # 残りか次の語がコード
                script = True
                i += k == len(a) - 1
                break
            if c in "CdDFIMmxV":  # 残りはこの旗の値
                break
            k += 1
            while c in "0l" and k < len(a) and a[k].isdigit():
                k += 1
    if not inplace:
        return None
    return args[i:] if script else args[i + 1:]


def _unsafe_delete_target(raw: str, cwd: Path, whole_ok: bool = False) -> str | None:
    """木ごと消してよい場所でなければ理由を返す。whole_ok は「作業場そのものを起点にしてよい」（find の絞り込み付き削除）。"""
    if re.search(r"[$`]|%[A-Za-z_]+%", raw) and not re.match(r"^\$(HOME|\{HOME\})(/|$)", raw):
        return f"ASK:消す場所 `{raw}` が変数を含み、実行前に決まりません"
    p = _resolve(raw, cwd)
    if p is None:
        return None
    s = p.as_posix()
    root = ROOT.as_posix()
    tmp_roots = ["/tmp/", "/var/tmp/"] + [os.environ[k].rstrip("/") + "/" for k in ("TMPDIR",) if os.environ.get(k)]
    if any(s.startswith(t) and len(s) > len(t) for t in tmp_roots):
        return None
    if s == root and whole_ok:
        return None
    if s == root or not s.startswith(root + "/"):
        return f"消す場所 `{raw}` が作業場の外か作業場全体です"
    if s == f"{root}/.git" or s.startswith(f"{root}/.git/"):
        return f"`{raw}` は git の履歴です"
    return None


# ---------------------------------------------------------------- 命令

_SEP = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&", ";;"}
_ESCAPED_SEMI = "\x00semicolon\x00"
_REDIR = re.compile(r"^\d*(>>?|<<?<?|&>>?|>&|<&|>\||<>|&>>?)$")
_WRAPPERS = {"nohup", "time", "nice", "ionice", "timeout", "stdbuf", "command", "builtin", "exec", "caffeinate", "unbuffer"}
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "pwsh", "powershell", "powershell.exe", "pwsh.exe", "cmd", "cmd.exe", "wsl", "wsl.exe"}
_ADMIN = {"sudo", "doas", "pkexec", "su", "runas", "gsudo", "run0"}
_INTERPRETERS = {"python", "python3", "python2", "node", "nodejs", "perl", "ruby", "php", "deno", "bun"}
_INLINE_FLAGS = {"-c", "-e", "-r", "--eval", "-p", "--print"}
_STRING_LITERAL = re.compile(r"""(['"])((?:(?!\1).){1,300})\1""")
_PUBLISH = {("npm", "publish"), ("pnpm", "publish"), ("yarn", "publish"), ("cargo", "publish"), ("twine", "upload"),
            ("docker", "push"), ("podman", "push"), ("gem", "push"), ("vsce", "publish"), ("poetry", "publish"), ("uv", "publish")}
_GH_READ = {
    ("repo", "view"), ("repo", "list"), ("pr", "list"), ("pr", "view"), ("pr", "diff"), ("pr", "checks"), ("pr", "status"),
    ("issue", "list"), ("issue", "view"), ("issue", "status"), ("run", "list"), ("run", "view"), ("run", "watch"),
    ("release", "list"), ("release", "view"), ("release", "download"), ("workflow", "list"), ("workflow", "view"),
    ("search", "repos"), ("search", "issues"), ("search", "prs"), ("search", "code"), ("search", "commits"),
    ("auth", "status"), ("status", ""), ("browse", ""), ("label", "list"), ("cache", "list"),
}
_GUARD_FILES = {"harness/guard.py", "harness/guard_bridge.mjs", ".claude/settings.json", ".codex/config.toml",
                ".agents/hooks.json", ".cursor/hooks.json", ".grok/hooks/guard.json", ".omp/extensions/guard.ts",
                ".opencode/plugins/guard.js", ".kilo/plugins/guard.js", ".dsh/guard.patch.yml"}
_WORKER_REASON = "担い手は担い手を起こさない。要るなら報告に書く"
_WORKER_MARKS = {"HARNESS_ROLE", "HARNESS_HANDS", "HARNESS_GUARD_EDIT", "HARNESS_WORKTREE"}


def _worker_target(raw: str, cwd: Path) -> Decision:
    """担い手の書き先だけを作業木内の保護対象と照らす。"""
    p = _resolve(raw, cwd)
    if p is None or re.search(r"[$`]", raw):
        return Decision("deny", f"書く場所 `{raw}` を確定できません")
    if p.as_posix() in ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"):
        return ALLOW
    try:
        worktree = os.environ.get("HARNESS_WORKTREE")
        root = Path(worktree or ROOT).resolve()
        target = p.resolve()
        rel = target.relative_to(root).as_posix()
    except (OSError, ValueError, subprocess.SubprocessError):
        return Decision("deny", f"書く場所 `{raw}` は自分の作業木の外です")
    if rel in _GUARD_FILES and os.environ.get("HARNESS_GUARD_EDIT", "") != "1":
        # HARNESS_GUARD_EDIT=1 は delegate.py が依頼書の guard: edit を見て付ける（守りを直す依頼だけの例外）
        return Decision("deny", f"守りのファイル `{raw}` は担い手が書き換えられません")
    return ALLOW


_HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def _heredocs(command: str) -> tuple[str, list[str]]:
    """heredoc の本文を外す。本文は書く中身なので見ないが、shell へ流すものだけは命令として返す。"""
    lines = command.split("\n")
    kept: list[str] = []
    to_shell: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for m in _HEREDOC.finditer(line):
            end, body = m.group(3), []
            while i < len(lines) and (lines[i].strip() if m.group(1) else lines[i]) != end:
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ValueError("heredoc is not closed")
            i += 1
            words = line[: m.start()].split("|")[-1].split()
            if words and os.path.basename(words[0]) in _SHELLS:
                to_shell.append("\n".join(body))
    return "\n".join(kept), to_shell


def _split(command: str) -> list[list[str]]:
    # 改行は命令の区切り。引用符の中の改行が「;」になっても、引用符の中なので判定は変わらない
    # `\;`（find -exec の終わり）は区切りではない。`\\;` は「\ の後の区切り」なのでそのまま
    command = re.sub(r"(?<!\\)((?:\\\\)*)\\;", "\\1" + _ESCAPED_SEMI, command)
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    out: list[list[str]] = [[]]
    for tok in lex:  # 引用符が閉じていなければ ValueError
        if tok in _SEP or (tok and set(tok) <= set(";&|")):
            out.append([])
        else:
            out[-1].append(tok.replace(_ESCAPED_SEMI, "\\;"))  # 入れ子の shell で読み直しても区切りにならないよう `\;` で戻す
    return [c for c in out if c]


def _substitutions(command: str) -> list[str]:
    inner = re.findall(r"\$\(([^()]*)\)", command) + re.findall(r"`([^`]*)`", command)
    inner += re.findall(r"<\(([^()]*)\)", command)
    return inner


def evaluate_command(command: str, cwd: Path, depth: int = 0) -> Decision:
    if depth > MAX_DEPTH:
        return Decision("deny", "命令の入れ子が深すぎて読めません")
    try:
        command, shell_bodies = _heredocs(command)
        simple = _split(command)
    except ValueError:
        return Decision("deny", "引用符か heredoc が閉じておらず、命令を読めません")
    decisions = [evaluate_command(s, cwd, depth + 1) for s in _substitutions(command) + shell_bodies]
    # 担い手は cd の先を追う。cd が失敗したときや `|`・`||`・( ) の中では元の場所のまま進むので、
    # 後の命令は通った場所すべてで判定する（cd 自体は止めない。先が読めない cd だけ止める）
    cwds = [cwd]
    for argv in simple:
        if os.environ.get("HARNESS_ROLE") == "worker" and argv[0] == "cd":
            dest = [a for a in argv[1:] if a == "-" or not a.startswith("-")]
            raw = dest[0] if dest else "~"
            nexts = [_resolve(raw, c) for c in cwds]
            if None in nexts or re.search(r"[$`*?]", raw.replace("$HOME", "").replace("${HOME}", "")):
                decisions.append(Decision("deny", f"cd の先 `{raw}` を確定できません"))
            else:
                cwds = list(dict.fromkeys(cwds + nexts))
        decisions += [_evaluate_argv(argv, c, depth) for c in cwds]
    return _worst(decisions)


def _evaluate_argv(argv: list[str], cwd: Path, depth: int) -> Decision:
    approved = False   # 管理者になる操作の OK（AGENT_ADMIN_APPROVED=1）
    ok_ask = False     # 「聞く」操作の OK（HARNESS_APPROVED=1）。担い手には人がいないので効かない
    worker = os.environ.get("HARNESS_ROLE") == "worker"
    # 前置きの代入・包みを外す
    while argv:
        head = argv[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", head):
            if worker and head.split("=", 1)[0] in _WORKER_MARKS:
                return Decision("deny", "担い手の印を変えられません")
            approved |= head == "AGENT_ADMIN_APPROVED=1"
            ok_ask |= head == "HARNESS_APPROVED=1"
            argv = argv[1:]
        elif head == "env":
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or "=" in argv[0]):
                if argv[0] in ("-u", "--unset") and len(argv) > 1:
                    if worker and argv[1] in _WORKER_MARKS:
                        return Decision("deny", "担い手の印を外せません")
                    argv = argv[2:]
                    continue
                if worker and (argv[0].split("=", 1)[0] in _WORKER_MARKS or
                               argv[0].removeprefix("--unset=") in _WORKER_MARKS and argv[0].startswith("--unset=")):
                    return Decision("deny", "担い手の印を変えられません")
                approved |= argv[0] == "AGENT_ADMIN_APPROVED=1"
                ok_ask |= argv[0] == "HARNESS_APPROVED=1"
                argv = argv[1:]
        elif head in _WRAPPERS or head == "busybox" and worker:
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or re.match(r"^\d+[smhd]?$", argv[0])):
                # exec -a <名前>: 名前は命令ではない
                argv = argv[2:] if head == "exec" and re.fullmatch(r"-[cl]*a", argv[0]) else argv[1:]
        else:
            break
    if not argv:
        return ALLOW
    decisions: list[Decision] = []
    # 触る場所（リダイレクト先を含む全引数）に秘密が無いか
    for i, a in enumerate(argv):
        if _REDIR.match(a):
            continue
        if i > 0 and _is_search_pattern(argv, i):
            continue
        if secret_path(a, cwd):
            decisions.append(Decision("deny", f"秘密のファイル `{a}` に触れます"))
    name = os.path.basename(argv[0]).lower()
    args = argv[1:]
    if worker:
        if _harness_file(argv[0], cwd, "dsh.sh"):
            decisions.append(Decision("deny", _WORKER_REASON))
        if name == "unset" and any(a in _WORKER_MARKS for a in args):
            decisions.append(Decision("deny", "担い手の印を外せません"))
        workers = {v["worker"][0] for v in json.loads((ROOT / "harness/clis.json").read_text(encoding="utf-8"))["clis"].values() if v.get("worker")}
        if name in workers and name != "bash":
            decisions.append(Decision("deny", _WORKER_REASON))
        if name in _SHELLS | {"source", "."} and any(_harness_file(a, cwd, "dsh.sh") for a in args):
            decisions.append(Decision("deny", _WORKER_REASON))
        if name in ("python", "python3"):
            i = 0
            while i < len(args) and args[i].startswith("-"):
                i += 2 if args[i] in ("-X", "-W") else 1
            if len(args) > i + 1 and _harness_file(args[i], cwd, "delegate.py") and args[i + 1] == "run":
                decisions.append(Decision("deny", _WORKER_REASON))
        writes: list[str] = []
        for j, a in enumerate(argv[:-1]):
            if a in (">", ">>", "1>", "1>>", "2>", "2>>", "&>", "&>>", ">|", "1>|", "2>|", "<>"):
                writes.append(argv[j + 1])
        if name == "tee":
            writes += [a for a in args if not a.startswith("-")]
        elif name == "sed" and any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args):
            script_seen = False
            i = 0
            while i < len(args):
                a = args[i]
                if a in ("-e", "--expression", "-f", "--file"):
                    script_seen = True
                    i += 2
                    continue
                if a.startswith(("--expression=", "--file=")):
                    script_seen = True
                elif not a.startswith("-"):
                    if script_seen:
                        writes.append(a)
                    else:
                        script_seen = True
                i += 1
        elif name == "install" and any(a in ("-d", "--directory") for a in args):
            writes += [a for a in args if not a.startswith("-")]
        elif name in ("cp", "mv", "rsync", "install") and args:
            target_dir = None
            sources = []
            short_t = name != "rsync"  # rsync の -t は「時刻を保つ」で、行き先ではない
            i = 0
            while i < len(args):
                a = args[i]
                if (a == "--target-directory" or short_t and a == "-t") and i + 1 < len(args):
                    target_dir = args[i + 1]
                    i += 2
                    continue
                if a.startswith("--target-directory="):
                    target_dir = a.split("=", 1)[1]
                elif short_t and a.startswith("-t") and len(a) > 2:
                    target_dir = a[2:]
                elif not a.startswith("-"):
                    sources.append(a)
                i += 1
            if target_dir is None and len(sources) >= 2:
                target_dir, sources = sources[-1], sources[:-1]
            if target_dir is not None:
                dest = _resolve(target_dir, cwd)
                if dest is not None and (target_dir.endswith("/") or dest.is_dir() or len(sources) > 1):
                    writes.extend(str(dest / Path(src).name) for src in sources)
                else:
                    writes.append(target_dir)
        elif name == "truncate":
            # truncate -s 0 <file>: 旗の値（-s 0 / --size=0 / -r <参照>）は書き先ではない
            skip = False
            for a in args:
                if skip:
                    skip = False
                elif a in ("-s", "-r", "--size", "--reference"):
                    skip = True
                elif not a.startswith("-"):
                    writes.append(a)
        elif name == "perl":
            writes += _perl_inplace(args) or []
        decisions += [_worker_target(p, cwd) for p in writes]

    if name in _ADMIN or (name in ("start-process", "saps") and any(a.lower() == "runas" for a in args)):
        if not approved:
            decisions.append(Decision("deny", "管理者になる操作です。人が直前に OK した 1 回だけ、先頭に AGENT_ADMIN_APPROVED=1 を付けて打ちます"))
        if name in _ADMIN:
            # 昇格する側の旗だけ外し、その先の命令は旗ごと判定する（OK があっても壊す命令と秘密は止める）
            i = 0
            while i < len(args) and args[i].startswith("-"):
                i += 2 if args[i] in ("-u", "-g", "-h", "-p", "-C", "-T", "-r", "-t", "-U", "-D", "-c") and name != "su" else 1
            if args[i:]:
                decisions.append(_evaluate_argv(args[i:], cwd, depth))
        return _ok_ask(_worst(decisions), ok_ask)

    if name == "wsl_to_win.sh":
        # このハーネスの橋（harness/tools/wsl_to_win.sh）。中で PowerShell か Windows の実行ファイルを 1 つ動かすので、
        # その中身を直接の `powershell -Command` と同じに読む（Opus 5.5 の引き継ぎの検証で見つかった抜け道、2026-09-23）
        decisions.append(_bridge(args, cwd, depth))
    elif name in _SHELLS:
        decisions.append(_shell(name, args, cwd, depth))
    elif name == "eval":
        decisions.append(evaluate_command(" ".join(args), cwd, depth + 1))
    elif name in _INTERPRETERS:
        # python3 -c 'open(".env")' のように、コードの中の文字列で秘密を開く形（2026-09-23 の独立の確認で
        # Grok 4.7 が見つけた穴）。コードは実行前に読めないが、引用符で囲まれた path らしい文字列だけは見る
        decisions.append(_interpreter_inline(args, cwd))
    elif name == "xargs":
        decisions.append(_xargs(args, cwd, depth))
    elif name in ("rm", "rmdir", "remove-item", "ri", "del", "erase", "rd"):
        decisions.append(_rm(name, args, cwd))
    elif name == "find":
        decisions.append(_find(args, cwd, depth))
    elif name == "git":
        decisions.append(_git(args, cwd))
    elif name == "gh":
        decisions.append(_gh(args))
    elif name == "curl":
        decisions.append(_curl(args))
    elif name == "wget":
        if any(a.startswith(("--post-", "--method", "--body-")) for a in args):
            decisions.append(Decision("ask", "wget で外へ送ります"))
    elif name in ("invoke-webrequest", "iwr", "invoke-restmethod", "irm"):
        if any(a.lower() in ("-body", "-infile") for a in args) or _pwsh_method(args):
            decisions.append(Decision("ask", "外へ送ります"))
    elif name in ("ssh", "scp", "sftp", "mosh"):
        decisions.append(Decision("ask", "遠隔の機械を操作します"))
    elif name == "rsync" and any(re.match(r"^[^/]*[^/\\]:", a) for a in args if not a.startswith("-")):
        decisions.append(Decision("ask", "rsync で遠隔の機械へ送ります"))
    elif name in ("mkfs", "wipefs", "shred", "diskpart", "format", "fdisk", "sfdisk", "parted") or name.startswith("mkfs."):
        decisions.append(Decision("deny", f"`{name}` はディスクや中身を消します"))
    elif name == "dd" and any(a.startswith("of=/dev/") for a in args):
        decisions.append(Decision("deny", "dd でデバイスへ書き込みます"))
    elif len(args) >= 1 and (name, args[0]) in _PUBLISH:
        decisions.append(Decision("ask", f"`{name} {args[0]}` で外へ公開します"))
    return _ok_ask(_worst(decisions), ok_ask)


def _ok_ask(d: Decision, ok: bool) -> Decision:
    """人が OK した「聞く」操作を 1 回だけ通す（先頭の HARNESS_APPROVED=1）。deny は OK があっても止まる。担い手には効かない。"""
    if ok and d.action == "ask" and os.environ.get("HARNESS_ROLE", "") != "worker":
        return Decision("allow", "人が OK した操作: " + d.reason)
    return d


def _interpreter_inline(args: list[str], cwd: Path) -> Decision:
    """-c / -e の中のコードから、引用符で囲まれた文字列だけ取り出して、秘密の path でないかを見る。"""
    for i, a in enumerate(args):
        if a in _INLINE_FLAGS and i + 1 < len(args):
            for _, s in _STRING_LITERAL.findall(args[i + 1]):
                # secret_path は名前を厳密に見る（".env is a file name" のような文は当たらない）
                if secret_path(s, cwd):
                    return Decision("deny", f"秘密のファイル `{s}` をコードの中で開きます")
    return ALLOW


def _is_search_pattern(argv: list[str], i: int) -> bool:
    """grep 系の検索語は場所ではないので、秘密の判定から外す。"""
    if os.path.basename(argv[0]) not in ("grep", "egrep", "fgrep", "rg", "ag", "ack", "git"):
        return False
    if argv[i - 1] in ("-e", "--regexp", "-g", "--glob"):
        return True
    positional = [j for j, a in enumerate(argv[1:], 1) if not a.startswith("-") and argv[j - 1] not in ("-e", "--regexp", "-g", "--glob", "-m", "-A", "-B", "-C")]
    if os.path.basename(argv[0]) == "git":
        return len(argv) > 1 and argv[1] == "grep" and positional[1:2] == [i]
    has_e = any(a in ("-e", "--regexp") or a.startswith("--regexp=") for a in argv)
    return not has_e and positional[:1] == [i]


def _shell(name: str, args: list[str], cwd: Path, depth: int) -> Decision:
    for flag in ("-c", "-lc", "-ic", "-Command", "-command", "-c:", "/c", "/C", "-e"):
        if flag in args:
            i = args.index(flag)
            if name.startswith(("pwsh", "powershell", "cmd")):
                # Windows の shell では \ は path の区切りで、次の文字を守る記号ではない
                body = " ".join(args[i + 1:]).replace("\\", "/")
            elif name.startswith("wsl"):
                body = " ".join(args[i + 1:])
            else:
                body = args[i + 1] if i + 1 < len(args) else ""
            return evaluate_command(body, cwd, depth + 1)
    if name.startswith("wsl") and args:
        rest = args[1:] if args[0] in ("--", "-e", "--exec") else args
        return evaluate_command(" ".join(rest), cwd, depth + 1) if rest else ALLOW
    if name.startswith(("pwsh", "powershell")) and any(a.lower() in ("-encodedcommand", "-enc", "-e") for a in args):
        return Decision("deny", "符号化された命令は読めません")
    # `bash script.sh` のように中身がファイルにある形は読めない（SECURITY.md の限界）。
    # ただし、このハーネス自身の橋だけは中身の形を知っているので読む
    rest = [a for a in args if not a.startswith("-")]
    if rest and os.path.basename(rest[0]) == "wsl_to_win.sh":
        return _bridge(rest[1:], cwd, depth)
    return ALLOW


def _bridge(args: list[str], cwd: Path, depth: int) -> Decision:
    if len(args) >= 2 and args[0] == "pwsh":
        return _shell("pwsh", ["-Command", *args[1:]], cwd, depth)
    if len(args) >= 2 and args[0] == "cli":
        return _evaluate_argv(args[1:], cwd, depth)
    return ALLOW


def _xargs(args: list[str], cwd: Path, depth: int) -> Decision:
    i = 0
    replace = None
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-I" and i + 1 < len(args):
            replace = args[i + 1]
        elif args[i].startswith(("-I", "--replace=")):
            replace = args[i].split("=", 1)[-1] if args[i].startswith("--") else args[i][2:]
        elif args[i] in ("-i", "--replace"):
            replace = "{}"
        i += 2 if args[i] in ("-I", "-n", "-P", "-d", "-L", "-s", "-E") else 1
    rest = args[i:]
    if not rest:
        return ALLOW
    head = os.path.basename(rest[0])
    reason = f"xargs が渡す引数は実行前に決まらず、`{head}` の中身を読めません"
    if head in _SHELLS or head in ("rm", "find", "git", "eval"):
        return Decision("deny", reason)
    plain = _evaluate_argv(rest, cwd, depth)
    if plain.action == "allow" and os.environ.get("HARNESS_ROLE") == "worker":
        # 担い手: 渡される引数を「作業木の外の path」と見なす。書く命令なら行き先が外になって止まる（ls・grep は通る）
        unknown = "/xargs-arg"
        filled = [a.replace(replace, unknown) for a in rest] if replace else rest + [unknown]
        if _evaluate_argv(filled, cwd, depth).action != "allow":
            return Decision("deny", reason)
    return plain


def _rm(name: str, args: list[str], cwd: Path) -> Decision:
    lower = [a.lower() for a in args]
    recursive = name in ("rmdir", "rd") or any(
        a in ("-recurse", "--recursive", "/s") or (re.match(r"^-[a-zA-Z]+$", a) and ("r" in a.lower()) and name == "rm")
        for a in args
    ) or (name in ("remove-item", "ri") and any(x.startswith("-r") for x in lower))
    if not recursive:
        return ALLOW
    targets = [a for a in args if not a.startswith("-") and not (name in ("rd", "rmdir", "del", "erase") and a.startswith("/"))]
    if name in ("remove-item", "ri"):
        targets = [a for i, a in enumerate(args) if not a.startswith("-") and not (i and args[i - 1].lower() in ("-filter", "-include", "-exclude"))]
    if not targets:
        return ALLOW
    for t in targets:
        reason = _unsafe_delete_target(t, cwd)
        if reason:
            return _delete_decision(reason)
    return ALLOW


def _delete_decision(reason: str) -> Decision:
    # 「変数を含む」は中身が読めないだけで、危ないと決まったわけではない → 聞く（2026-09-23、止めすぎの緩和）
    if reason.startswith("ASK:"):
        return Decision("ask", reason[4:])
    return Decision("deny", reason)


def _find(args: list[str], cwd: Path, depth: int) -> Decision:
    deleting = "-delete" in args
    starts = []
    for a in args:
        if a.startswith(("-", "(", "!")) or a in (")",):
            break
        starts.append(a)
    for k in [i for i, a in enumerate(args) if a in ("-exec", "-execdir", "-ok", "-okdir")]:
        tail = []
        for a in args[k + 1:]:
            if a in (";", "+", "\\;"):
                break
            tail.append(a)
        if tail:
            head = os.path.basename(tail[0])
            if head in _SHELLS or head == "rm":
                deleting = True
            # {} は外さず、出発点の中のファイル（find . なら ./{}）と見なして行き先を判定する
            for s in starts or ["."]:
                inner = _evaluate_argv([a.replace("{}", os.path.join(s, "{}")) for a in tail], cwd, depth)
                if inner.action != "allow":
                    return inner
    if not deleting:
        return ALLOW
    # 絞り込み（-name / -mtime など）が 1 つも無い削除は「その木を全部消す」形なので止める。
    # 絞り込みがあれば、作業場の中なら通す（git があるので戻せる。2026-09-23、止めすぎの緩和）
    filters = [a for a in args if a.startswith("-") and a not in ("-delete", "-exec", "-execdir", "-ok", "-print", "-print0", "-depth", "-r")]
    if not filters:
        return Decision("deny", "絞り込みの無い find の削除は、その木を全部消します")
    for s in starts or ["."]:
        reason = _unsafe_delete_target(s, cwd, whole_ok=True)
        if reason:
            return _delete_decision(reason)
    return ALLOW


def _git(args: list[str], cwd: Path) -> Decision:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree") else 1
    if i >= len(args):
        return ALLOW
    sub, rest = args[i], args[i + 1:]
    discards = (sub == "checkout" and "--" in rest or
                sub == "restore" and (any(a in rest for a in ("--worktree", "-W")) or
                                      not any(a in rest for a in ("--staged", "-S"))) or
                sub == "stash" and bool(rest) and rest[0] in ("drop", "clear") or
                sub == "branch" and "-D" in rest)
    if discards:
        action = "deny" if os.environ.get("HARNESS_ROLE") == "worker" else "ask"
        return Decision(action, f"git {sub} は変更や履歴を消しうる操作です")
    if sub == "reset" and "--hard" in rest:
        return Decision("deny", "git reset --hard はコミットしていない変更を消します")
    if sub == "clean" and any(re.match(r"^-[a-zA-Z]*f", a) or a == "--force" for a in rest):
        # 予行（-n / --dry-run）は何も消さないので通す（2026-09-23、止めすぎの緩和）
        if any(re.match(r"^-[a-zA-Z]*n", a) or a == "--dry-run" for a in rest):
            return ALLOW
        return Decision("deny", "git clean -f は追跡していないファイルを消します")
    if sub == "push":
        pos = [a for a in rest if not a.startswith("-")]
        refs = pos[1:]
        targets = [r.split(":")[-1].removeprefix("+").removeprefix("refs/heads/") for r in refs]
        if not refs:
            targets = [_current_branch(cwd)]
        if any(t in ("main", "master") for t in targets):
            return Decision("deny", "main / master へ直接 push しません。branch を切って PR にします")
        return Decision("ask", "git push で外へ出します")
    return ALLOW


def _current_branch(cwd: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _gh(args: list[str]) -> Decision:
    pos = [a for a in args if not a.startswith("-")]
    if not pos:
        return ALLOW
    if pos[0] == "api":
        sending = any(
            a in ("-X", "--method", "-f", "-F", "--field", "--raw-field", "--input")
            or a.startswith(("--method=", "--field=", "--raw-field=", "--input=", "-X", "-f", "-F")) and len(a) > 2 and not a.startswith("--")
            for a in args
        )
        return Decision("ask", "gh api で外へ送ります") if sending else ALLOW
    key = (pos[0], pos[1] if len(pos) > 1 else "")
    if key in _GH_READ:
        return ALLOW
    return Decision("ask", f"`gh {' '.join(key).strip()}` は外の状態を変えうる操作です")


def _curl(args: list[str]) -> Decision:
    for i, a in enumerate(args):
        if a.startswith("--data") or a in ("--json", "--form", "--form-string", "--upload-file", "-T", "-F", "-d") \
                or a.startswith(("--json=", "--form=", "--upload-file=")):
            return Decision("ask", "curl で外へ送ります")
        if re.match(r"^-[a-zA-Z]*[dFT]", a) and not a.startswith("--"):
            return Decision("ask", "curl で外へ送ります")
        if a in ("-X", "--request") and i + 1 < len(args) and args[i + 1].upper() not in ("GET", "HEAD", "OPTIONS"):
            return Decision("ask", "curl で外へ送ります")
        m = re.match(r"^(?:-X|--request=)(\w+)$", a)
        if m and m.group(1).upper() not in ("GET", "HEAD", "OPTIONS"):
            return Decision("ask", "curl で外へ送ります")
    return ALLOW


def _pwsh_method(args: list[str]) -> bool:
    for i, a in enumerate(args):
        if a.lower() == "-method" and i + 1 < len(args) and args[i + 1].lower() not in ("get", "head", "options"):
            return True
    return False


# ---------------------------------------------------------------- 道具の呼び出し

# 各 CLI 標準の子エージェントの起動口。止め方が CLI ごとにばらばら（設定 / 旗 / hook だけ）なので、ここ 1 か所で止める。
# 名前は完全一致で見る（TaskCreate のような別の道具を巻き込まないため）。
_SUBAGENT_TOOLS = {"agent", "task", "subagent", "subagent_fork", "invoke_subagent", "define_subagent", "spawn_agent",
                   "subagentstart", "ralph", "workflow"}
SUBAGENT_REASON = "各 CLI 標準の子エージェントは使いません。他の担い手へ渡すときは python3 harness/delegate.py を使います（AGENTS.md）"

# 「手なし」の担い手（依頼書の hands: none）が使えない道具。読む・探す・web は使える。
# お願いの文ではなく起動の仕方で決めるので、CLI が 9 本あっても効き方が変わらない。
_WRITING_TOOLS = {"write", "edit", "multiedit", "notebookedit", "apply_patch", "str_replace_editor", "create_file",
                  "write_file", "edit_file", "replace_file_content", "multi_replace_file_content", "write_to_file",
                  "bash", "shell", "run_command", "run_shell_command", "execute", "exec_command", "shell_command",
                  "terminal", "process", "job_run", "todo_write", "patch"}
HANDS_REASON = "この依頼は「読むだけ」で受けています（依頼書の hands: none）。書く道具と shell は使えません。結果は報告に書いてください"


_COMMAND_KEYS = ("command", "cmd", "CommandLine", "command_line", "script")
_PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "AbsolutePath", "TargetFile", "target_file",
              "DirectoryPath", "SearchPath", "filename", "file", "paths", "files")


def _is_report_write(tool_input: dict | str, cwd: Path) -> bool:
    target = os.environ.get("HARNESS_REPORT")
    if not target or not isinstance(tool_input, dict):
        return False
    want = _resolve(target, cwd)
    for key in _PATH_KEYS:
        v = tool_input.get(key)
        if isinstance(v, str) and v and _resolve(v, cwd) == want:
            return True
    return False


def evaluate(tool: str, tool_input: dict | str, cwd: Path | None = None) -> Decision:
    cwd = cwd or Path.cwd()
    short = tool.rsplit(".", 1)[-1].lower()
    if short in _SUBAGENT_TOOLS:
        return Decision("deny", SUBAGENT_REASON)
    if os.environ.get("HARNESS_HANDS") == "none" and (short in _WRITING_TOOLS or short.startswith(("write", "edit", "create_", "delete_", "move_"))):
        # 例外は報告 1 本だけ。報告も書けないと、読むだけの担い手は結果を返せない
        if not _is_report_write(tool_input, cwd):
            return Decision("deny", HANDS_REASON)
    if isinstance(tool_input, str):
        tool_input = {"command": tool_input}
    if not isinstance(tool_input, dict):
        return Decision("deny", "守りの入力を読めません")
    work = tool_input.get("cwd") or tool_input.get("workdir") or tool_input.get("Cwd")
    if isinstance(work, str) and work:
        cwd = _resolve(work, cwd) or cwd
    decisions: list[Decision] = []
    if tool.rsplit(".", 1)[-1] == "apply_patch":
        # Codex は変更の本文を command に入れてくる。本文は見ず、見出しの path だけ見る
        body = tool_input.get("command") or tool_input.get("input") or ""
        text = body if isinstance(body, str) else " ".join(map(str, body))
        for m in re.finditer(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", text, re.M):
            p = (m.group(1) or m.group(2)).strip()
            if secret_path(p, cwd):
                decisions.append(Decision("deny", f"秘密のファイル `{p}` に触れます"))
            if os.environ.get("HARNESS_ROLE") == "worker":
                decisions.append(_worker_target(p, cwd))
        return _worst(decisions)
    for key in _COMMAND_KEYS:
        value = tool_input.get(key)
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            value = shlex.join(value)
        if isinstance(value, str) and value.strip():
            decisions.append(evaluate_command(value, cwd))
    for key in _PATH_KEYS:
        value = tool_input.get(key)
        for v in value if isinstance(value, list) else [value]:
            if isinstance(v, str) and secret_path(v, cwd):
                decisions.append(Decision("deny", f"秘密のファイル `{v}` に触れます"))
            if isinstance(v, str) and os.environ.get("HARNESS_ROLE") == "worker" and \
                    (short in _WRITING_TOOLS or short.startswith(("write", "edit", "create_", "delete_", "move_"))):
                decisions.append(_worker_target(v, cwd))
    return _worst(decisions)


# ---------------------------------------------------------------- CLI ごとの入出力

def unattended() -> bool:
    """聞く相手がいないか。**既定は「いない」**（2026-09-24、ユーザー:「デフォルトで Hook の承認で勝手にストップしないようにして」。
    承認待ちの画面で気づかないうちに止まるのを防ぐ）。担い手（delegate.py が起動した側）は常にいない。
    指示役は、人が目の前にいる印 HARNESS_ATTENDED=1 を付けたときだけ「いる」（CLI の承認画面が出る）。
    いないときの「聞く」は実行せず止め、書き置く。人が OK したら先頭に HARNESS_APPROVED=1 を付けて 1 回だけ通す。"""
    return os.environ.get("HARNESS_ROLE", "") == "worker" or os.environ.get("HARNESS_ATTENDED", "") != "1"


def unattended_reason(d: Decision) -> Decision:
    if os.environ.get("HARNESS_ROLE", "") == "worker":
        return Decision("deny", "人がいない担い手なので、確認が要る操作はしません。報告の「人の判断が要ること」に書いて指示役へ返してください。" + d.reason)
    return Decision("deny", "確認が要る操作なので実行せず、判断カードを 1 枚書いて次の仕事へ移ります（judgment skill）。"
                    "人が OK したら、その 1 回だけ先頭に HARNESS_APPROVED=1 を付けて打ちます。" + d.reason)


def read_call(payload: dict, dialect: str) -> tuple[str, dict | str]:
    if dialect == "agy":
        call = payload.get("toolCall") or {}
        return str(call.get("name", "")), call.get("args", {})
    if dialect == "cursor":
        if "tool_name" in payload:
            return str(payload["tool_name"]), payload.get("tool_input", {})
        return str(payload.get("hook_event_name", "")), payload
    name = payload.get("tool_name", payload.get("toolName"))
    if not isinstance(name, str):
        raise ValueError("tool name is missing")
    return name, payload.get("tool_input", payload.get("toolInput", {}))


def write_decision(d: Decision, dialect: str) -> int:
    if dialect == "claude":
        # Claude Code / Codex / Grok / DeepSeek Harness の Claude 形式。
        # 止めるときは exit 2 + stderr が、どの CLI でも「止める」と読まれる。
        if d.action == "deny":
            print(d.reason, file=sys.stderr)
            return 2
        if d.action == "ask":
            json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                              "permissionDecisionReason": d.reason}}, sys.stdout, ensure_ascii=False)
        return 0
    if dialect == "agy":
        out = {"decision": "force_ask" if d.action == "ask" else d.action, "reason": d.reason}
    elif dialect == "cursor":
        # Cursor は無出力を失敗と見なすので、許可のときも返す
        out = {"permission": d.action, "userMessage": d.reason, "agentMessage": d.reason}
    else:  # plain: JS 拡張（omp / opencode / Kilo）が読む
        out = {"decision": d.action, "reason": d.reason}
    json.dump(out, sys.stdout, ensure_ascii=False)
    return 0


def main(argv: list[str]) -> int:
    dialect = "claude"
    if len(argv) >= 2 and argv[0] == "--dialect":
        dialect = argv[1]
    if dialect not in ("claude", "cursor", "agy", "plain"):
        print(f"unknown dialect: {dialect}", file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
        tool, tool_input = read_call(payload, dialect)
        cwd = Path(payload["cwd"]) if isinstance(payload.get("cwd"), str) and payload["cwd"] else Path.cwd()
        d = evaluate(tool, tool_input, cwd)
    except (ValueError, TypeError, KeyError, AttributeError):
        d = Decision("deny", "守りの入力を読めません。hook の配線を確かめてください（python3 harness/check.py）")
    if d.action == "ask" and unattended():
        d = unattended_reason(d)
    _trace(dialect, locals().get("tool", "?"), d)
    return write_decision(d, dialect)


def _trace(dialect: str, tool: str, d: Decision) -> None:
    """実測用。HARNESS_GUARD_TRACE にファイルを指したときだけ、hook が本当に呼ばれたかを 1 行ずつ残す（命令の中身は残さない）。"""
    path = os.environ.get("HARNESS_GUARD_TRACE")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"dialect": dialect, "tool": tool, "action": d.action}, ensure_ascii=False) + "\n")
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
