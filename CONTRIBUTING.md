# Contributing to BlogMarketing

Thanks for your interest in improving BlogMarketing! Contributions of all
sizes are welcome — bug reports, docs, and pull requests.

## Ways to contribute

- **Report a bug** — open an issue with steps to reproduce, what you expected,
  and what happened. Include your OS and Python version.
- **Suggest a feature** — open an issue describing the use case first, so we can
  agree on the approach before you write code.
- **Pick up a `good first issue`** — these are scoped to be approachable for a
  first contribution.
- **Improve the docs** — README, `DOCUMENTATION.md`, and docstrings.

## Development setup

```bash
git clone https://github.com/smitchandarana/BlogMarketing.git
cd BlogMarketing
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
# add your own API keys to .env
```

Run the test suite before opening a PR:

```bash
python -m pytest tests/ -q
```

## Project conventions

This repo follows a few house rules (see `.claude/rules/` and `CLAUDE.md`):

- **One responsibility per module.** Prefer editing an existing module over
  adding a new one.
- **Type hints on all functions**, modern syntax (`list[str]`, `X | None`).
- **Use `logging`, never `print()`**, and never bare `except:`.
- **Never commit secrets.** Keys live in `.env` (gitignored). Only edit
  `.env.example` with placeholder values.
- Keep the validation checklist in `CLAUDE.md` green (imports resolve, DB schema
  matches `init_db()`, tracker fieldnames match).

## Pull request checklist

1. Branch from the default branch.
2. Keep the change focused — one concern per PR.
3. Add or update a test for any behavior change.
4. Make sure `python -m pytest tests/ -q` passes.
5. Update `README.md` / `DOCUMENTATION.md` if behavior or setup changed.
6. Describe *what* and *why* in the PR description.

## Reporting security issues

Please do **not** open a public issue for a security or credential-exposure
problem. Instead, email the maintainer (see the GitHub profile) with details.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE) that covers this project.
