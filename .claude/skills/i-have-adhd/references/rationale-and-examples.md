# Rationale and examples

The core `SKILL.md` is authoritative. This reference explains why its rules exist and illustrates them; it does not add requirements.

## Why the shape matters

- Limited working memory makes hidden state and “keep this in mind” unreliable.
- Starting has more friction than understanding, so the first action must be obvious and small.
- Vague effort estimates feel alike, so concrete minutes or hours improve decisions.
- Visible progress helps sustain attention; buried wins are easy to miss.
- Extra branches compete with the current task, so tangents wait.

## Examples

| Need | Avoid | Prefer |
|---|---|---|
| Start | “Let’s think about the auth flow.” | “Run `npm test -- auth.spec.ts`.” |
| Steps | One paragraph containing several actions | A numbered list with one action per item |
| Resume | “Done. Ready for the next part?” | “Step 3 of 5 done: schema updated. Next: run the backfill.” |
| Time | “This will take some work.” | “15–25 minutes with existing tests; 2–3 hours without them.” |
| Win | “I made several auth changes.” | “Magic-link login now succeeds. Check `/login`.” |
| Error | “Uh oh, something seems wrong.” | “Test expected 200 and got 401. The request lacks an auth header; add it.” |
| Open work | “Tell me if you want to continue.” | “Next: open `src/auth.ts`.” |

## Resolving conflicts

1. Obey system, project, safety, and authorization constraints first.
2. Answer the user’s actual request. For an explanation, explain; for options, give two to four ranked options with the recommendation first.
3. Keep the action-oriented shape without deleting necessary evidence, caveats, or instructions.
4. If three attempts fail, test the underlying assumption instead of producing a fourth variation of the same fix.

For destructive actions, confirmation replaces the usual immediate action. For harness work, required commentary may precede a tool call even though routine conversational preambles are omitted.
