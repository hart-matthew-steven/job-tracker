# .cursor/rules/30-memory.md
# Context & Durable Memory (Repo-managed)

## Principle
Cursor does not have permanent memory. Durable memory is created by writing small, version-controlled summaries into this repo.

If context is insufficient to proceed safely:
- ask for the missing file(s), OR
- propose a staged plan, and after each stage write a tight summary to `docs/ai/MEMORY.md`.

## Memory Files
Use these as the durable "brain":
- `docs/ai/CONTEXT.md`   — high-level overview for new sessions/engineers
- `docs/ai/MEMORY.md`    — rolling summary of current state + recent changes
- `docs/ai/TASKS.md`     — concrete tasks (in progress / next / later)
- `docs/ai/DECISIONS.md` — ADR-lite decisions and rationale
- `docs/ai/MAP.md`       — repo map: where key things live

## When to update memory
Treat `docs/ai/MEMORY.md` as authoritative current project state.

Update `docs/ai/MEMORY.md` when:
- a refactor batch is completed
- a convention is discovered (naming, structure, patterns)
- notable tech debt is identified for later
- anything important would otherwise be re-explained next time

Update `docs/ai/TASKS.md` when:
- tasks change state (in progress → done)
- priorities change (next/later reordering)
- a new multi-step effort is introduced

Update `docs/ai/DECISIONS.md` when:
- we choose between approaches (folder layout, auth strategy, error format, etc.)

Update `docs/ai/MAP.md` when:
- we confirm where entry points live and key flows are wired

## Summary style (keep it tight)
- Bullet points.
- Concrete facts > opinions.
- Keep updates under ~25 lines per session.

## Documentation, Logs, Temporary Scripts (repo hygiene)
### Documentation
- Any documentation created by the agent must live under `docs/`.
- AI-authored summaries/plans/decisions go under `docs/ai/`.

### Logs & Outputs
- Any command output, script result, or analysis output goes under `logs/`.
- Logs should be timestamped and descriptive.
- Logs are not authoritative documentation.

### Temporary Scripts
- One-off or exploratory scripts go under `temp_scripts/`.
- Scripts should include a short header describing purpose and expected lifespan.
- Do not place one-off scripts in production source directories.

---

## Automatic Documentation Maintenance (Default Behavior)

### Default expectation
After completing a change that affects system behavior, architecture, dev/prod workflow, security posture, or operational setup, update documentation automatically without being asked.

### What to update
- Update `docs/architecture/overview.md` if:
  - components change (new service, new worker, new integration)
  - dev vs prod behavior changes (ngrok usage, deployment layout)
  - new AWS service becomes part of the architecture

- Update `docs/architecture/data-flow.md` if:
  - request flow changes (new endpoints, new async job path)
  - upload/scan/storage flow changes
  - state transitions change (e.g., new status values)

- Update `docs/architecture/security.md` if:
  - auth/session model changes
  - secrets handling changes
  - file scanning rules change
  - permissions/least-privilege approach changes
  - new external exposure path exists (webhook ingress, public routes)

- Update `docs/ai/MEMORY.md` after every meaningful batch of work.

- Update `docs/ai/DECISIONS.md` when:
  - a tradeoff decision is made (tool choice, service choice, pattern choice)

### How to update docs (cost controlled)
- Do not rewrite entire documents.
- Prefer appending or editing the smallest relevant section.
- Keep each doc update concise (generally <= 25 lines changed per doc unless explicitly requested).
- Use bullets and short paragraphs; avoid long narrative.

### Where verbose information goes
- If detailed output is needed (commands, long logs, debugging dumps), write it to:
  - `logs/ai/...` or `logs/scripts/...`
- Do not paste large outputs into docs.

### If unsure
If it is unclear whether a change warrants doc updates:
- update `docs/ai/MEMORY.md` anyway
- and add a short note under "Open Items" in the relevant architecture doc

### Consumer/API docs
- Update `docs/api/overview.md` and `docs/api/endpoints.md` when:
  - endpoints change
  - auth requirements change
  - error/response conventions change

### Implementation docs
- Update `docs/frontend/overview.md` when:
  - routing/state/API client patterns change
- Update `docs/backend/overview.md` when:
  - backend structure/auth/persistence/job patterns change