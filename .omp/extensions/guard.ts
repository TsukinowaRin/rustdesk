// oh-my-pi（omp）の守り。判定は harness/guard.py（全 CLI 共通）で、ここは渡して返すだけ。
// <cwd>/.omp/extensions/*.ts は自動で読み込まれ、tool_call が { block: true, reason } を返すと実行が止まる。
import { judge } from "../../harness/guard_bridge.mjs";
import { execFile } from "node:child_process";

export default function (pi: any) {
  pi.on("session_start", async (_event: any, ctx: any) => {
    try {
      await new Promise((resolve) => execFile("python3", ["harness/setup.py", "auto"], { cwd: ctx?.cwd ?? process.cwd() }, resolve));
    } catch {}
  });
  pi.on("tool_call", async (event: any, ctx: any) => {
    const d = judge(event?.toolName, event?.input, ctx?.cwd ?? process.cwd());
    if (d.action === "allow") return;
    if (d.action === "ask") {
      // tool_call の戻り値に「聞く」は無い。確認を出せる場では人に聞き、出せない場（omp -p）では止める。
      try {
        if ((await ctx?.ui?.confirm?.(d.reason + "\n実行してよいですか？")) === true) return;
      } catch {}
    }
    return { block: true, reason: d.reason };
  });
}
