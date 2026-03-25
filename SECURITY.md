# Security Policy

## Current Status

On March 24, 2026, the repository was reviewed for publishability and obvious credential exposure.

Best-effort checks performed:

- regex scanning of the tracked working tree for common API key, token, password, DSN, and private-key patterns,
- filename/history checks for `.env`, `auth.json`, `.pem`, `.key`, and runtime settings artifacts,
- manual review of the current app's runtime secret paths and environment examples.

Result:

- no live secrets were found in the current tracked files,
- no committed runtime auth files were found by filename in git history,
- the active app now ignores `ClauseDev/backend/data/`, which can contain locally saved OpenAI-compatible endpoint credentials.

This is a practical review, not a formal audit. If this repo was ever shared outside trusted environments, rotate credentials anyway.

## Secret Handling Rules

- Commit `.env.example` files, never `.env` or `.env.local`.
- Keep runtime-generated files under `ClauseDev/backend/data/` out of git.
- Treat `backend/data/openai_settings.json` as secret-bearing local state.
- Keep Codex OAuth credentials in `~/.codex/auth.json`; do not copy them into the repo.
- Use a strong `CLAUSEAI_JWT_SECRET` for any environment beyond local development.

## Recommended GitHub Controls

- Enable GitHub secret scanning and push protection.
- Enable branch protection on the default branch.
- Require reviews before merging infra or auth changes.
- Rotate any API key immediately if it was ever committed, pasted into an issue, or stored in a shared machine profile.

## Reporting

If you find a credential leak or auth issue in this repository, remove public exposure first, rotate the affected secret, and then notify the maintainers with:

- the affected file path,
- the secret type,
- whether it reached git history,
- whether the credential was already rotated.
