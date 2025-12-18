# .cursor/rules/40-quality.md
# Quality Bar (Employer-grade Repo)

## Reviewability
- Prefer mechanical refactors over sweeping rewrites.
- Keep diffs tight and intention-revealing.
- Avoid mixing refactors with feature changes unless requested.

## Testing
- If tests exist, keep them passing.
- If adding a small test is high ROI, suggest it as an option.
- Do not introduce new test frameworks without approval.

## Errors & Logging
- Error messages should be actionable.
- Avoid leaking secrets in logs.
- Keep error handling patterns consistent.

## Documentation Boundaries
- Root README.md should remain concise and high-level.
- Detailed architecture, data flow, and security documentation belongs under `docs/architecture/`.
- Avoid duplicating the same explanation across multiple files; prefer linking.

## Commit Hygiene (guidance)
Suggest commit messages in a conventional style:
- `refactor(frontend): ...`
- `refactor(backend): ...`
- `docs(architecture): ...`
- `docs(ai): ...`
- `chore(repo): ...`

## Tone (professional “character”)
- Keep documentation professional.
- Light humor is allowed in chat and commit message suggestions.
- Avoid jokes inside long-lived docs unless extremely subtle.