// opencode の守り。判定は harness/guard.py（全 CLI 共通）で、ここは渡して返すだけ。
// tool.execute.before で例外を投げると、その道具の実行が止まる。「聞く」は出せないので止める側へ倒す。
import { judge } from "../../harness/guard_bridge.mjs";
import { execFile } from "node:child_process";

export const HarnessGuard = async ({ directory }) => {
  let setupStarted = false;
  return {
  event: async ({ event }) => {
    if (event?.type !== "session.created" || setupStarted) return;
    setupStarted = true;
    try {
      await new Promise((resolve) => execFile("python3", ["harness/setup.py", "auto"], { cwd: directory }, resolve));
    } catch {}
  },
  "tool.execute.before": async (input, output) => {
    const d = judge(input?.tool, output?.args, directory);
    if (d.action !== "allow") throw new Error(d.reason + (d.action === "ask" ? "（確認が要る操作です。人に頼んでください）" : ""));
  },
  };
};
