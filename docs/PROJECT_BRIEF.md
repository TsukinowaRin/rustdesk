# プロジェクト概要

この文書は fast path で最初に読む RustDesk fork の概要。詳細な platform build は `README.md` と `.github/workflows/` を一次情報とする。

## この repo について

- プロダクト / ライブラリ / サービス:
  - Rust と Flutter で実装されたクロスプラットフォームのリモートデスクトップアプリケーション（RustDesk fork）
- 主目的:
  - セルフホスト可能なリモート接続、画面・音声転送、入力制御、クリップボード、ファイル転送を提供する
- 主な利用者:
  - デスクトップ／モバイル利用者、セルフホスト運用者、RustDesk開発者

## 入口

- 最初に読むもの:
  - `AGENTS.md`, `docs/PROJECT_BRIEF.md`, `docs/REQS.md`
- 主要ディレクトリ:
  - `src/`: Rustアプリ本体、`src/server/`: audio / clipboard / input / video / network
  - `src/platform/`: platform固有処理、`libs/`: capture / input / clipboard / shared utilities
  - `flutter/`: 現行UI（desktop / mobile / common / models）、`src/ui/`: deprecated Sciter UI
  - `src/lang/`: ローカライズ、`.github/workflows/`: platform別CIとrelease build
- ハーネス構成の正本:
  - `docs/HARNESS.md`

## Build / Test / Run

- Build:
  - platform別の正式入口: `python3 build.py --flutter`（必要なfeatureはplatformと成果物に合わせる）
  - Rust workspaceの基本確認: `cargo check --locked`
- Test / Smoke:
  - Rust: `cargo test --locked`
  - Flutter: `(cd flutter && flutter test)`
  - ハーネス構造の点検: `bash scripts/smoke_template.sh` / `bash scripts/security_smoke.sh`
- Lint / Format:
  - Rust format check: `cargo fmt --all -- --check`
  - Flutter analysis: `(cd flutter && flutter analyze)`

## 制約

- 許可する変更:
  - 現在の `docs/REQS.md` に明記された範囲だけ
  - skill 編集は `.agents/skills/` のみ、mirror は `python3 scripts/sync_shared_skills.py` 経由
- 禁止する変更:
  - `.claude/settings.local.json` などユーザーローカル設定の変更
  - task外のrefactor、既存の非empty翻訳、translation taskでの`src/lang/template.rs`
- プラットフォーム制約:
  - platform固有コードは `src/platform/` に置き、共有call siteは薄いhookにする
  - WSL↔Windows相互運用は `scripts/win_*.sh` / `scripts/wsl_exec.*` 経由

## 環境メモ

- 必要なランタイム:
  - python3 (3.11+), bash, git（ハーネス script 用）
  - Rust 1.75+、Cargo、Flutter/Dart（`flutter/pubspec.yaml` は Dart `^3.1.0`）
- パッケージマネージャ:
  - Cargo、Flutter pub、platformによりvcpkgとsystem package manager
- 外部サービス:
  - build/testにはgit依存の取得が必要。runtimeはRustDesk rendezvous/relayまたはセルフホストserverを利用可能
