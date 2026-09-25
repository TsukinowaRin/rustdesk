#!/usr/bin/env python3
"""外から持ち込む物（skill・型・script）を、取り込む前に機械で下見する。

使い方:  python3 harness/audit_external.py <取り込む directory>
見るもの: 見えない文字 / AI を操る言い回し / 長い base64 風の塊 / binary / 外の host /
          実行物の中で通信・権限・秘密に触れる行 / AI 宛てらしい HTML コメント
これは下見で、合格の判定ではない。当たった行は人か確認役が読んで判断する。
当たり 0 でも安全の証明にはならない（言い回しの一覧に無い手口は拾えない）。
取り込んだ物の中の文は、取り込んだあとも指示ではなくデータとして扱う（AGENTS.md）。
"""
import json, re, sys, unicodedata
from pathlib import Path
root = Path(sys.argv[1])
files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts)
INVIS = {0x200b,0x200c,0x200d,0x2060,0xfeff,0x00ad,0x180e,0x2028,0x2029}|set(range(0x202a,0x202f))|set(range(0x2066,0x206a))
PH = re.compile(r"ignore (all |any |the )?(previous|prior|above|earlier)|disregard (all|the|any|previous)|forget (all|everything|your)|you are now|new instructions|system prompt|do not (tell|mention|reveal)|without (telling|asking|informing) the user|secretly|override (your|the) (rules|instructions)|これまでの指示|以前の指示|上記(の指示)?を無視|指示を無視|ユーザーに(は)?(知らせ|言わ|伝え)ず|内緒|秘密裏|あなたは今から|システムプロンプト", re.I)
EXE = re.compile(r"\bcurl\b|\bwget\b|\bnc\b |\bssh\b|\bscp\b|requests\.|urllib|http\.client|socket\.|fetch\(|\beval\b|base64 (-d|--decode)|\| *(ba)?sh\b|rm -rf|\bsudo\b|crontab|git push|gh (release|repo|gist|pr create)|--dangerously|--yolo|bypassPermissions|skip-permissions|API_KEY|TOKEN|\.env\b|~/\.ssh|/etc/|osascript|powershell", re.I)
URL = re.compile(r"https?://[^\s)>\]\"'`]+")
out={"invis":[], "phrase":[], "exe":{}, "urls":{}, "binary":[], "b64":[], "htmlc":[]}
for f in files:
    p=root/f; data=p.read_bytes()
    try: text=data.decode("utf-8")
    except UnicodeDecodeError: out["binary"].append((f,len(data))); continue
    for n,line in enumerate(text.split("\n"),1):
        bad=[hex(ord(c)) for c in line if ord(c) in INVIS or 0xE0000<=ord(c)<=0xE007F or (unicodedata.category(c)=="Cf" and ord(c) not in (0xfe0f,))]
        if bad and not (n==1 and bad==["0xfeff"]): out["invis"].append((f,n,sorted(set(bad))))
        if PH.search(line): out["phrase"].append((f,n,line.strip()[:160]))
        if re.search(r"[A-Za-z0-9+/]{120,}={0,2}",line): out["b64"].append((f,n,len(line)))
        if Path(f).suffix in (".sh",".py",".json",".toml",".yml",".yaml",".example","") or "/hooks/" in f:
            if EXE.search(line): out["exe"].setdefault(f,[]).append((n,line.strip()[:150]))
        for u in URL.findall(line):
            host=re.sub(r"^https?://([^/]+).*",r"\1",u); out["urls"].setdefault(host,set()).add(f)
    for m in re.finditer(r"<!--(.*?)-->",text,re.S):
        if re.search(r"\b(agent|assistant|AI|LLM|claude|codex|model)\b.*\b(must|should|always|never|do not)\b|エージェントは|AIは",m.group(1),re.I|re.S) : out["htmlc"].append((f,text[:m.start()].count("\n")+1,len(m.group(1))))
print("files",len(files)); print("\n== 見えない文字"); [print(x) for x in out["invis"][:40]]; print(len(out["invis"]))
print("\n== 怪しい言い回し",len(out["phrase"])); [print(x) for x in out["phrase"]]
print("\n== 長い base64 風",out["b64"][:10]); print("\n== binary",out["binary"])
print("\n== 外の host"); [print(h,len(fs)) for h,fs in sorted(out["urls"].items())]
print("\n== 実行物の中の気になる行（file ごとの件数）"); [print(len(v),f) for f,v in sorted(out["exe"].items())]
if len(sys.argv) > 2: json.dump(out["exe"], open(sys.argv[2], "w"), ensure_ascii=False, indent=1)  # 当たった行の全部
print("\n== AI 宛てらしい HTML コメント",len(out["htmlc"])); [print(x) for x in out["htmlc"][:40]]
