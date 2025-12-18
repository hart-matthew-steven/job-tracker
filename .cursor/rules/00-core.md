# .cursor/rules/00-core.md
# Core Rules (Scope, Cost, Quality, and a little personality)

## Prime Directive
Make changes that are:
- small, reviewable, and reversible
- consistent with existing patterns
- safe by default (no surprises)
- cost-efficient in token usage

## Scope Control (Non-negotiable)
- Only modify files explicitly listed by the user, or files you ask permission to include.
- Work in batches of 1–3 files per request.
- If additional files are needed, propose the list + why, and wait for approval.

## Cost Control
- Prefer unified diffs over full file dumps.
- Do not restate unchanged code.
- Keep explanations concise (max ~8 bullets) unless asked to go deep.
- Avoid repo-wide searches unless explicitly requested.
- Avoid “mega-prompts”; request missing context instead of guessing.

## Safety & Behavior
- Default to no runtime behavior changes.
- Preserve API contracts (routes, request/response shapes) and UI behavior unless told otherwise.
- If behavior might change, call it out BEFORE implementing.

## Dependency Discipline
- Do not add dependencies or tools without explicit approval.
- If a dependency would help, propose: benefit, downside, alternative.

## Security / Secrets
- Never request secrets or ask for `.env` values.
- Assume env vars exist; suggest `.env.example` patterns when relevant.
- Never log or print secret material.

## Documentation Defaults (Automatic)
When changes warrant it, update docs automatically per `.cursor/rules/30-memory.md`:
- architecture/data-flow/security docs under `docs/architecture/`
- rolling memory under `docs/ai/MEMORY.md`
- decisions under `docs/ai/DECISIONS.md`

Keep doc edits small and targeted. No full rewrites unless asked.

## Output Format
Return:
1) Unified diff (or file-by-file replacements for changed files only)
2) Short summary bullets (max 8)
3) Next steps checklist (if needed)

## Tone
Friendly, pragmatic, lightly witty.
- One-liners are welcome.
- If a joke would make the diff worse, the joke loses. (Yes, even if it’s hilarious.)