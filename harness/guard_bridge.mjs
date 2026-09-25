// JS で拡張を書く CLI（oh-my-pi / opencode / Kilo）から、全 CLI 共通の守り harness/guard.py を呼ぶ橋。判定は持たない。
// 返すのは { action: "allow" | "ask" | "deny", reason }。判定を呼べないときは deny（読めないものは通さない）。
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export function findRoot(start) {
  let dir = resolve(start || process.cwd());
  for (let i = 0; i < 30; i += 1) {
    if (existsSync(join(dir, "harness", "guard.py"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

export function judge(toolName, toolInput, cwd) {
  const root = findRoot(cwd);
  if (!root) return { action: "deny", reason: "守り（harness/guard.py）が見つかりません" };
  const r = spawnSync("python3", ["-B", join(root, "harness", "guard.py"), "--dialect", "plain"], {
    input: JSON.stringify({ tool_name: String(toolName ?? ""), tool_input: toolInput ?? {}, cwd: cwd || root }),
    encoding: "utf8",
  });
  try {
    const out = JSON.parse(r.stdout);
    return { action: out.decision, reason: out.reason || "" };
  } catch {
    return { action: "deny", reason: "守りの返事を読めません: " + String(r.stderr || r.error || "").slice(0, 200) };
  }
}
