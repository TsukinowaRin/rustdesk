---
name: local-skill-bootstrap
description: 再利用可能な workflow を新しく頼まれたとき、または繰り返し出てくる repo 固有の指示を ad-hoc な prompt や第三者 skill の download ではなく repo-local な skill にすべきとき、`.agents/skills/` 配下の shared skill を新規作成または更新する。
---

# Local Skill Bootstrap

繰り返し使う workflow を `.agents/skills/` 配下の repo-local skill にするときに使う。

次の用途には使わない:

- `docs/REQS.md` に書けば足りる単発のタスクメモ
- インターネットからの第三者 skill の download / install
- 再利用 workflow にする価値のない小さな単発 prompt

## 手順

1. 既存 skill で足りないかを先に確認する。
2. hyphen-case の skill 名と、発動条件が正確に伝わる description を決める。
3. この skill の `scripts/init_skill.py` で新しい shared skill を scaffold する。
4. 生成された `SKILL.md` と、必要なら `scripts/` / `references/` / `assets/` を編集する。
5. `python3 scripts/sync_shared_skills.py` を実行して `.claude/skills/` を同期する。
6. 新 skill が repo の workflow を変えるなら、関連する最小限の docs を更新する。

## コマンド

最小構成の skill を作る:

```bash
python3 .agents/skills/local-skill-bootstrap/scripts/init_skill.py \
  --name my-skill \
  --description "この skill がいつ発動すべきかを正確に書く。"
```

同梱フォルダ付きの skill を作る:

```bash
python3 .agents/skills/local-skill-bootstrap/scripts/init_skill.py \
  --name my-skill \
  --description "この skill がいつ発動すべきかを正確に書く。" \
  --with-scripts \
  --with-references
```

## 作成ルール

- `SKILL.md` は簡潔に保ち、使う場面と使わない場面を明示する。
- 再利用コードを `scripts/` に置くのは、決定性や繰り返しがそれを正当化するときだけ。
- 詳細な参照資料は `SKILL.md` を肥大化させず `references/` に置く。
- skill 内に余計な README や changelog を作らない。
- ほぼ重複した新 skill を作るより、既存 skill の更新を優先する。

## 検証

- `find .agents/skills/<skill-name> -maxdepth 3 -type f | sort`
- `find .claude/skills/<skill-name> -maxdepth 3 -type f | sort`
- `python3 scripts/sync_shared_skills.py`
