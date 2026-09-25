#!/usr/bin/env python3
"""MCP サーバーを標準入出力で叩く最小の client。何の道具があるかを見て、1 つ呼んでみる。
使い方: mcp_probe.py <サーバーを起動する命令...>"""
import json, subprocess, sys, time

def send(p, obj):
    p.stdin.write(json.dumps(obj) + "\n"); p.stdin.flush()

def recv(p, want_id, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        line = p.stdout.readline()
        if not line:
            break
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("id") == want_id:
            return m
    return None

p = subprocess.Popen(sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
init = None
for i, ver in enumerate(("2026-07-28", "2025-06-18", "2025-03-26"), start=1):
    send(p, {"jsonrpc":"2.0","id":i,"method":"initialize","params":{
        "protocolVersion":ver,"capabilities":{"roots":{"listChanged":False}},
        "clientInfo":{"name":"harness-probe","version":"0.1.0"}}})
    r = recv(p, i, timeout=30)
    print(f"initialize({ver}):", "ok" if r and "result" in r else f"失敗 {json.dumps(r, ensure_ascii=False)[:220]}")
    if r and "result" in r:
        init = r
        break
if init and "result" in init:
    info = init["result"].get("serverInfo", {})
    print("  サーバー:", info.get("name"), info.get("version"), "/ 約束の版:", init["result"].get("protocolVersion"))
send(p, {"jsonrpc":"2.0","method":"notifications/initialized"})
send(p, {"jsonrpc":"2.0","id":2,"method":"tools/list"})
tl = recv(p, 2)
tools = [t["name"] for t in (tl or {}).get("result", {}).get("tools", [])]
print(f"道具 {len(tools)} 個:", ", ".join(tools[:24]) + (" ..." if len(tools) > 24 else ""))
if "doctor" in tools:
    send(p, {"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"doctor","arguments":{}}})
    d = recv(p, 9, timeout=60)
    for c in (d or {}).get("result", {}).get("content", []):
        print("doctor:", str(c.get("text"))[:700])
shot = next((t for t in tools if "screenshot" in t or "screen_capture" in t), None)
if shot:
    send(p, {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":shot,"arguments":{}}})
    r = recv(p, 3, timeout=120)
    res = (r or {}).get("result", {})
    content = res.get("content", [])
    for c in content:
        print(f"{shot} の返事: type={c.get('type')} 長さ={len(c.get('data') or c.get('text') or '')} 本文={str(c.get('text'))[:160]}")
    # 画像で返させる指定も試す
    send(p, {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":shot,"arguments":{"format":"image"}}})
    r2 = recv(p, 4, timeout=120)
    for c in (r2 or {}).get("result", {}).get("content", []):
        print(f"  もう一度（image 指定）: type={c.get('type')} 長さ={len(c.get('data') or c.get('text') or '')}")
p.terminate()
