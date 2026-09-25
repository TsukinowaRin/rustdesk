#!/usr/bin/env python3
"""判断の輪（判断カード → 台帳 → 蒸留 → 原則）を、上流 kagemusha の型と道具のまま使うための薄い包み。

型も蒸留の道具も vendor/kagemusha/ の上流が正本で、ここは自前の型を持たない（9/17 に作り直しを取り消した。
理由は vendor/kagemusha/UPSTREAM.md）。ここがやるのは機械の仕事だけ:
  init    置き場を作り、上流の型を写し（上書きしない）、この repo 用の config.env を書く
  sync    台帳だけを commit し、origin があれば取り込んでから送る
  brief   指示役が始めに読む: 原則と、たまっている物の数
  check   未処理のカードが、上流の型の欄をすべて持つか
  harvest 会話ログから人の訂正を拾う（上流の correction_scan.py。モデルは使わない）
  distill たまっていれば蒸留する（上流の distill.sh。蒸留役に書く手は渡さない）
  seal    原則のファイルを人が手で直したあと、今の中身を正として記録する
  pattern 人の訂正の言い回しを語彙へ足す（語彙は人ごとに違うので配らない。使いながら指示役が育てる）

カードと台帳はエージェントが上流の型どおりに直接書く（作法は judgment skill）。
置き場は .loop/judgment/（作業場とは別の repo）。HARNESS_JUDGMENT_HOME で非公開の別 repo を指せる。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "vendor" / "kagemusha"
TEMPLATES = {  # 上流の型 → 置き場での名前
    "templates/approval_queue.md": "approval_queue.md",
    "templates/decisions_journal.md": "decisions_journal.md",
    "templates/judgment_model.md": "judgment_model.md",
    "templates/promotion_queue.md": "promotion_queue.md",
    "templates/correction_patterns.example.txt": "correction_patterns.txt",
}
BATCH_CARDS = 3  # 上流の決まり: 1 バッチ ≦ 3 枚


def cards_home(loop: Path) -> Path:
    if os.environ.get("HARNESS_JUDGMENT_HOME"):
        return Path(os.environ["HARNESS_JUDGMENT_HOME"])
    p = loop / "setup.json"
    saved = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return Path(saved.get("judgment_home") or loop / "judgment")


def home() -> Path:
    from inbox import loop_dir
    return cards_home(loop_dir())


def need_home() -> Path:
    h = home()
    if not (h / "config.env").exists():
        die("置き場がまだありません。先に: python3 harness/judgment.py init")
    return h


def die(msg: str):
    print(f"judgment: {msg}", file=sys.stderr)
    raise SystemExit(1)


def claude_log_dir(project: Path) -> Path:
    # Claude Code は会話ログを「作業場所の path の英数字以外を - にした名前」で分ける。
    # 担い手は別の作業木で動かすので、ここには指示役と人の会話だけが入る。
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(project))


def git(h: Path, *args: str, check: bool = True, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--literal-pathspecs", "-C", str(h), *args],
                          capture_output=True, text=True, check=check, timeout=timeout,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


def toplevel(h: Path) -> Path | None:
    r = git(h, "rev-parse", "--show-toplevel", check=False)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


def origin(h: Path) -> str:
    r = git(h, "remote", "get-url", "origin", check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def same_repo_key(url: str, base: Path) -> str:
    """同じ repo の書き方違い（末尾 / と .git、file://、scp 形式と https・ssh、host の大小）をそろえる。"""
    u = url.strip()
    u = u[len("file://"):] if u.startswith("file://") else u
    m = (re.match(r"^[A-Za-z][\w+.-]*://(?:[^/@]*@)?([^/:]+)(?::\d*)?(.*)$", u)  # https://, ssh://git@
         or re.match(r"^(?:[^@/]*@)?([^/:]+):(.*)$", u))  # git@host:u/r
    if m:
        host, path = m.group(1).lower() + "/", m.group(2).strip("/")
    else:
        host, path = "", str((base / u).resolve())
    while path.endswith((".git", "/")):
        path = path.removesuffix("/") if path.endswith("/") else path.removesuffix(".git")
    return host + path


def without_login(url: str) -> str:
    # https://user:pass@host や https://token@host の認証情報を落とす。ssh://git@host の利用者名は残す。
    m = re.match(r"^([A-Za-z][\w+.-]*://)([^/@]*)@(.*)$", url)
    if m and (":" in m.group(2) or m.group(1).lower() in ("http://", "https://")):
        return m.group(1) + m.group(3)
    return url


def safe_repo(h: Path) -> None:
    top = toplevel(h)
    if top is not None and top == toplevel(ROOT):
        die("台帳と作業場の repo が同じなので同期しません")
    if top != h.resolve():
        die("置き場そのものが台帳の repo ではありません。init --new で準備してください")
    workspace_urls = set()
    for remote in git(ROOT, "remote", check=False).stdout.splitlines():
        for flag in ((), ("--push",)):
            workspace_urls.update(same_repo_key(u, ROOT) for u in
                                  git(ROOT, "remote", "get-url", "--all", *flag, remote).stdout.splitlines())
    for flag in ((), ("--push",)):
        urls = git(h, "remote", "get-url", "--all", *flag, "origin", check=False).stdout.splitlines()
        if workspace_urls.intersection(same_repo_key(u, h) for u in urls):
            die("台帳と作業場の remote URL が同じなので同期しません")


def ensure_ignore(h: Path) -> None:
    p = h / ".gitignore"
    if p.is_symlink():
        die("台帳の .gitignore が symlink なので同期しません")
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    rules = "config.env\n*.env\nlogs/\n"
    if not old.endswith(rules):
        p.write_text(old + ("\n" if old and not old.endswith("\n") else "") + rules, encoding="utf-8")


def ledger_path(name: str, h: Path) -> bool:
    from guard import secret_path
    p = Path(name)
    if any(part == "logs" or part.endswith(".env") for part in p.parts) or secret_path(name, h):
        return False
    return (name in {*TEMPLATES.values(), "distill_state.json", "harness_state.json", ".gitignore"}
            or (len(p.parts) == 1 and name.startswith("correction_material.md"))
            or (len(p.parts) > 1 and p.parts[0] == "journal_archive"))


UNTRACK_HINT = "追跡中の一覧外は、台帳の repo で `git rm --cached <ファイル>` して追跡から外してください（ファイルは消えません）"


def check_contents(h: Path, branch: str) -> None:
    # add の対象だけでなく、既に stage された物と、push で届く履歴も確かめる。
    entries = git(h, "ls-files", "--stage", "-z").stdout.split("\0")
    head = git(h, "rev-parse", "--verify", "HEAD", check=False)
    if head.returncode == 0:
        upstream = f"refs/remotes/origin/{branch}"
        known = git(h, "rev-parse", "--verify", upstream, check=False).returncode == 0
        commits = git(h, "rev-list", "HEAD", *(["^" + upstream] if known else [])).stdout.splitlines()
        # 現在の木は upstream と同じ場合も点検する。
        for commit in ["HEAD", *commits]:
            entries.extend(git(h, "ls-tree", "-r", "-z", commit).stdout.split("\0"))
    for entry in filter(None, entries):
        meta, name = entry.split("\t", 1)
        if meta.split()[0] not in ("100644", "100755") or not ledger_path(name, h):
            die("台帳の一覧外・秘密・symlink が追跡ファイルか未送信の履歴にあるので同期しません\n" + UNTRACK_HINT)


def cmd_sync(a) -> int:
    h = need_home()
    safe_repo(h)
    branch = git(h, "symbolic-ref", "--short", "HEAD").stdout.strip()
    check_contents(h, branch)
    remote = origin(h)
    # 作ったばかりの空の remote には、まだ pull する branch がない。
    if remote and git(h, "ls-remote", "--heads", "origin").stdout:
        # 未 commit の台帳を一時退避してから取り込む。復元の衝突も送信前に止める。
        git(h, "pull", "--rebase", "--autostash", "origin", branch)
        if git(h, "ls-files", "--unmerged").stdout:
            die("台帳の取り込みで衝突しました。解決してから sync をやり直してください")
        check_contents(h, branch)
    ensure_ignore(h)
    names = git(h, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout.split("\0")
    allowed = sorted({name for name in names if name and ledger_path(name, h)})
    for name in allowed:
        if (h / name).is_symlink():
            die("台帳の一覧に symlink があるので同期しません")
    if allowed:
        git(h, "add", "--", *allowed)
    check_contents(h, branch)
    if git(h, "diff", "--cached", "--quiet", check=False).returncode:
        git(h, "commit", "-m", f"judgment: {datetime.now().astimezone():%Y-%m-%d} {ROOT.name}")
    if remote:
        safe_repo(h)
        check_contents(h, branch)
        if git(h, "config", "--get-all", "remote.origin.pushurl", check=False).stdout.strip():
            die("origin に pushurl があるので送りません（commit は済み）。外すなら: git config --unset-all remote.origin.pushurl")
        # 送り先は origin の fetch URL だけ。pushDefault、origin.push、followTags、mirror で先や範囲を広げない。
        url = git(h, "config", "--get", "remote.origin.url").stdout.strip()
        git(h, "push", "--no-follow-tags", url, f"HEAD:refs/heads/{branch}")
    print("台帳を同期しました" if remote else "台帳を commit しました（origin は未設定）")
    return 0


def pull_brief(h: Path) -> None:
    try:
        # 旧形式の置き場から親の作業場 repo を pull しない。
        if not h.exists() or toplevel(h) != h.resolve() or toplevel(h) == toplevel(ROOT) or not origin(h):
            return
        branch = git(h, "symbolic-ref", "--short", "HEAD").stdout.strip()
        git(h, "pull", "--ff-only", "origin", branch, timeout=5)
    except (OSError, subprocess.SubprocessError):
        print("judgment: 台帳の最新取得に失敗しました。手元の内容で続けます", file=sys.stderr)


def cmd_init(a) -> int:
    h = home().resolve()
    if a.source:
        h.parent.mkdir(parents=True, exist_ok=True)
        git(h.parent, "clone", "--", a.source, str(h))
    else:
        h.mkdir(parents=True, exist_ok=True)
        git(h, "init")
    ensure_ignore(h)
    (h / "logs").mkdir(parents=True, exist_ok=True)
    for src, name in TEMPLATES.items():
        if not (h / name).exists():  # 人の判断が入ったファイルは上書きしない
            (h / name).write_bytes((KIT / src).read_bytes())
    cfg = h / "config.env"
    if a.source and cfg.is_symlink():
        cfg.unlink()
    if a.source or not cfg.exists():
        q = shlex.quote
        cfg.write_text(f"""# kagemusha の設定（この repo 用。harness/judgment.py init が作った）。上流の説明は vendor/kagemusha/config.env.example。
PROJECT_ROOT={q(str(ROOT))}
LOG_DIR={q(str(h / 'logs'))}
DISTILL_MATERIAL_FILE={q(str(h / 'correction_material.md'))}
DISTILL_STATE_FILE={q(str(h / 'distill_state.json'))}
DISTILL_QUEUE_FILE={q(str(h / 'promotion_queue.md'))}
DISTILL_PATTERNS_FILE={q(str(h / 'correction_patterns.txt'))}
DISTILL_LOG_DIRS={q(str(claude_log_dir(ROOT)))}
DISTILL_THRESHOLD=5
DISTILL_RULES_FILE={q(str(ROOT / 'AGENTS.md'))}
DISTILL_PRINCIPLES_FILE={q(str(h / 'judgment_model.md'))}
# 蒸留役に書く手を渡さない（上流の設計）。権限を外す旗をここに入れない。
DISTILL_AGENT_FLAGS=""
# スマホへの通知は既定で切。上流の見本の題目（誰でも同じ名前になる）は使わない。
# 使うと決めた人の設定は harness/setup.py notify が下のファイルに書く。
NTFY_ENABLED=0
NTFY_TOPIC=""
if [ -f {q(str(ROOT / '.loop' / 'notify.env'))} ]; then . {q(str(ROOT / '.loop' / 'notify.env'))}; fi
""", encoding="utf-8")
    from setup import save
    if a.source and any(not ledger_path(n, h) for n in git(h, "ls-files", "-z").stdout.split("\0") if n):
        print(UNTRACK_HINT)
    # insteadOf で書き換える前の、人が渡した URL を残す（認証情報は落とす）。
    raw = git(h, "config", "--get", "remote.origin.url", check=False).stdout.strip()
    save(judgment_home=str(h), judgment_remote=without_login(raw))
    if _state().get("model_sha") is None:
        _seal()
    print(f"置き場: {h}")
    if not _patterns(h):
        print("訂正の語彙は空で始まります（人ごとに違うので配りません）。人に直されたら、その言い回しを "
              "`judgment.py pattern` で足してください。語彙が育つまで、採取は拾えません。")
    return 0


def cmd_pattern(a) -> int:
    """語彙を 1 行足す。壊れた正規表現が 1 行入ると上流の採取が止まるので、足す前に確かめる。"""
    h = need_home()
    if not a.regex:
        for l in _patterns(h):
            print(l)
        return 0
    try:
        rx = re.compile(a.regex, re.I)
    except re.error as e:
        die(f"正規表現として読めません: {e}")
    if rx.search(""):
        die("空の文字列に当たる語彙は、すべての発言を拾ってしまいます")
    if a.regex in _patterns(h):
        print("もうあります")
        return 0
    if a.heard and not rx.search(a.heard):
        die("その語彙は、--heard に渡した人の言葉に当たりません。言い回しそのもの（意味ではなく語）を語彙にします")
    with (h / "correction_patterns.txt").open("a", encoding="utf-8") as f:
        f.write(a.regex + "\n")
    print(f"語彙に足しました（{len(_patterns(h))} 個）。広めに始めて、あとで絞ります（上流の勧め）。")
    return 0


def _patterns(h: Path) -> list[str]:
    p = h / "correction_patterns.txt"
    return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []


# ---------------------------------------------------------------- カードの点検（欄は上流の型から読む）

def card_fields() -> list[str]:
    text = (KIT / "templates" / "approval_queue.md").read_text(encoding="utf-8")
    block = re.search(r"```markdown\n## Q-.*?\n(.*?)```", text, re.S)
    return re.findall(r"^- ([^:\[\n]+):", block.group(1), re.M) if block else []


def open_cards(h: Path) -> list[tuple[str, str]]:
    text = (h / "approval_queue.md").read_text(encoding="utf-8")
    m = re.search(r"^## 未処理\s*\n(.*?)(?=^---\s*$|^## 処理済み)", text, re.S | re.M)
    body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S) if m else ""
    cards = re.split(r"(?m)^(?=#{2,3} Q-)", body)
    out = []
    for c in cards:
        head = re.match(r"#{2,3} (Q-\S+)(.*)", c)
        if head:
            out.append((head.group(1) + head.group(2), c))
    return sorted(out, key=lambda c: "🔴" not in c[0])


def cmd_check(a) -> int:
    h = need_home()
    fields, bad = card_fields(), 0
    cards = open_cards(h)
    for title, body in cards:
        if "🔴" not in title and "🟡" not in title:
            print(f"NG  {title}: 見出しに重み（🔴 か 🟡）が無い"); bad += 1
        for f in fields:
            m = re.search(rf"^- {re.escape(f)}: *(.*)$", body, re.M)
            if not m or not m.group(1).strip():
                print(f"NG  {title}: 「{f}」が空"); bad += 1
    print(f"未処理 {len(cards)} 枚、直す所 {bad} 件。欄の正本: vendor/kagemusha/templates/approval_queue.md")
    if len(cards) > BATCH_CARDS:
        print(f"人へ出すのは 1 回に {BATCH_CARDS} 枚まで（🔴 が先）。残りは次の回へ。")
    print("機械が見るのは欄の有無だけ。合格条件「この 1 枚の文面だけで OK か NG が出せるか」は、"
          "文脈を知らない別の担い手にカードの文面だけを渡して確かめる（前提ゼロゲート。judgment skill）。")
    return 1 if bad else 0


# ---------------------------------------------------------------- 原則の書き換えの検知

def _state() -> dict:
    p = home() / "harness_state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _sha() -> str:
    return hashlib.sha256((home() / "judgment_model.md").read_bytes()).hexdigest()


def _seal() -> None:
    (home() / "harness_state.json").write_text(json.dumps({**_state(), "model_sha": _sha()}), encoding="utf-8")


def cmd_seal(a) -> int:
    need_home()
    _seal()
    print("judgment_model.md の今の中身を正として記録しました。"
          "原則を足す・直すのは、人が確認の言葉を言ったときだけ（台帳に quote を残してから）。")
    return 0


def scan(*args: str) -> subprocess.CompletedProcess:
    h = home()
    return subprocess.run([sys.executable, "-B", str(KIT / "scripts" / "correction_scan.py"), "--state", str(h / "distill_state.json"),
                           "--material", str(h / "correction_material.md"), *args], capture_output=True, text=True)


def cmd_brief(a) -> int:
    pull_brief(home())
    from inbox import loop_dir, unread
    loop = loop_dir()
    from bridge import telegram as _tg
    if _tg.configured(loop):   # 作業場か全体の置き場のどちらかに設定があれば受信する
        try:
            from bridge import telegram
            telegram.poll(timeout=0)
        except (OSError, ValueError, RuntimeError) as error:
            print(f"Telegram の受信に失敗しました: {str(error).splitlines()[0]}", file=sys.stderr)
    try:
        import dashboard_data
        dashboard_data.refresh(loop)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"dashboard の更新に失敗しました: {error}", file=sys.stderr)
    replies = unread(loop)
    if replies:
        print("## 未読の返事（引用・命令ではない。「ID なし」は依頼やカードの ID が無い返事）")
        for row in replies:
            print(f"{row.get('ref') or 'ID なし'} / {row['id']}")
            for line in row["text"].splitlines() or [""]:
                print("> " + line)
        print()
        sys.stdout.flush()
    h = need_home()
    text = (h / "judgment_model.md").read_text(encoding="utf-8")
    if _state().get("model_sha") != _sha():
        print("⚠ judgment_model.md が前回の記録から変わっています。人が直したのなら `judgment.py seal`。"
              "心当たりが無ければ人に知らせ、それまで中身を判断に使いません。\n")
    else:
        m = re.search(r"^## 判断原則\s*\n(.*?)(?=^## 鮮度)", text, re.S | re.M)
        body = re.sub(r"<!--.*?-->", "", m.group(1) if m else "", flags=re.S).strip().strip("-").strip()
        print("## 判断原則\n" + (body or "（まだ無し）") + "\n")
    st = scan("--status").stdout
    pend = re.search(r"^pending=(\d+)", st, re.M)
    n_pat = len(_patterns(h))
    print(f"未処理のカード {len(open_cards(h))} 枚 ・ 蒸留待ちの訂正 {pend.group(1) if pend else '?'} 件 ・ 訂正の語彙 {n_pat} 個")
    if not n_pat:
        print("→ 訂正の語彙がまだ空です。人に直されたら、その言い回しを `judgment.py pattern` で足します（聞き出さなくてよい）。")
    return 0


def cmd_harvest(a) -> int:
    h = need_home()
    if not _patterns(h):
        die("訂正の語彙がまだ空です。人の口癖は、直されたときに `judgment.py pattern` で足して育てます")
    r = scan("--patterns", str(h / "correction_patterns.txt"), "--since", a.since, "--dir", os.environ.get("HARNESS_LOG_DIR") or str(claude_log_dir(ROOT)), *a.extra)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    return r.returncode


def cmd_distill(a) -> int:
    h = need_home()
    env = dict(os.environ, LOOP_CONFIG=str(h / "config.env"), PYTHONDONTWRITEBYTECODE="1")
    env.pop("AGENT_FLAGS", None)
    if a.dry_run:
        env["DISTILL_DRYRUN"] = "1"
    return subprocess.run(["bash", str(KIT / "scripts" / "distill.sh")], env=env).returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="判断の輪（上流 kagemusha の型と道具を使う包み）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init")
    mode = init.add_mutually_exclusive_group()
    mode.add_argument("--new", action="store_true")
    mode.add_argument("--from", dest="source", metavar="URL_OR_PATH")
    for name in ("brief", "check", "seal", "sync"):
        sub.add_parser(name)
    hv = sub.add_parser("harvest"); hv.add_argument("--since", default="1d"); hv.add_argument("extra", nargs="*")
    ds = sub.add_parser("distill"); ds.add_argument("--dry-run", action="store_true")
    pt = sub.add_parser("pattern"); pt.add_argument("regex", nargs="?"); pt.add_argument("--heard", default="", help="実際に言われた言葉。語彙がそれに当たるか確かめる")
    a = ap.parse_args(argv)
    try:
        return {"init": cmd_init, "brief": cmd_brief, "check": cmd_check, "seal": cmd_seal, "sync": cmd_sync,
                "harvest": cmd_harvest, "distill": cmd_distill, "pattern": cmd_pattern}[a.cmd](a)
    except (OSError, subprocess.SubprocessError):
        # Git の出力には認証付き URL や秘密のファイル名が出ることがある。
        die("Git またはファイル操作に失敗しました（衝突・接続・設定を確認してください）。自動では解決しません")


if __name__ == "__main__":
    raise SystemExit(main())
