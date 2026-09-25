// 使い捨ての環境の中で、画面操作の MCP サーバーに話しかけ、画面を 1 枚撮って C:\out へ保存する。
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
const OUT = "C:\\out\\";
const log = [];
const say = (s) => { log.push(s); console.log(s); writeFileSync(OUT + "log.txt", log.join("\n"), "utf8"); };

const srv = spawn("npx.cmd", ["-y", "@zavora-ai/computer-use-mcp@7.4.0"], { stdio: ["pipe", "pipe", "pipe"], shell: true });
srv.stderr.on("data", (d) => say("サーバーの stderr: " + d.toString().trim().slice(0, 500)));
srv.on("error", (e) => say("起動できない: " + e.message));
let buf = "", waiting = new Map();
srv.stdout.on("data", (d) => {
  buf += d.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line.startsWith("{")) continue;
    try { const m = JSON.parse(line); if (waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } } catch {}
  }
});
const call = (id, method, params) => new Promise((res) => {
  waiting.set(id, res);
  srv.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  setTimeout(() => { if (waiting.has(id)) { waiting.delete(id); res({ error: { message: "時間切れ" } }); } }, 120000);
});

const init = await call(1, "initialize", { protocolVersion: "2026-07-28", capabilities: {}, clientInfo: { name: "harness", version: "1" } });
say("initialize: " + (init.result ? "ok " + JSON.stringify(init.result.serverInfo) : "失敗 " + JSON.stringify(init)));
srv.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) + "\n");
const tl = await call(2, "tools/list", {});
const tools = (tl.result?.tools || []).map((t) => t.name);
say("道具 " + tools.length + " 個");
const doc = await call(3, "tools/call", { name: "doctor", arguments: {} });
say("doctor: " + JSON.stringify(doc.result?.content?.[0]?.text || doc).slice(0, 600));
const shot = await call(4, "tools/call", { name: "screenshot", arguments: {} });
for (const c of shot.result?.content || []) {
  if (c.type === "image" && c.data) { writeFileSync(OUT + "shot.png", Buffer.from(c.data, "base64")); say("撮影: image を保存（" + c.data.length + " 文字の base64）"); }
  else say("撮影の返事: type=" + c.type + " 本文=" + String(c.text).slice(0, 200));
}
writeFileSync(OUT + "result.json", JSON.stringify({ tools: tools.length, init: !!init.result }, null, 1), "utf8");
srv.kill();
